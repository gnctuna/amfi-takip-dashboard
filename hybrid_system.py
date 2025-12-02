import cv2
from ultralytics import YOLO
import paho.mqtt.client as mqtt
import json
import time
import sys
from datetime import datetime

# --- GENEL AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"
MIN_CONFIDENCE = 0.65  # %65 Güven Eşiği

# YENİ AYAR: Veri Gönderme Sıklığı (Saniye)
# Kamera 30 FPS çalışsa bile veri 2 saniyede 1 gider.
DATA_UPLOAD_INTERVAL = 2.0 

def main():
    if len(sys.argv) > 1:
        SCENARIO = sys.argv[1].upper()
    else:
        SCENARIO = "SINIF"

    print(f"🚀 SİSTEM BAŞLATILIYOR: {SCENARIO} MODU")
    print(f"🛡️ Güven Eşiği: %{int(MIN_CONFIDENCE*100)}")

    if SCENARIO == "AMFI":
        model_name = "yolov8x.pt" 
        print(f"📸 Mod: SNAPSHOT (Her 5 dakikada bir analiz)")
        interval = 300
    elif SCENARIO == "SINIF":
        model_name = "yolov8n.pt"
        print(f"🎥 Mod: CANLI TAKİP (Veri hızı: {DATA_UPLOAD_INTERVAL}s)")
    else:
        print("❌ HATA: Geçersiz mod.")
        return

    print("⏳ Model yükleniyor...")
    model = YOLO(model_name)
    
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        print("✅ Buluta Bağlandı!")
    except:
        print("⚠️ İnternet yok, yerel modda çalışıyor.")

    # --- AMFİ MODU (Değişiklik Yok) ---
    if SCENARIO == "AMFI":
        while True:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Kamera açılıyor...")
            cap = cv2.VideoCapture(0)
            cap.set(3, 1280)
            cap.set(4, 720)
            for _ in range(5): cap.read()
            success, frame = cap.read()
            cap.release()
            
            if success:
                print("🧠 Analiz ediliyor...")
                results = model.predict(frame, classes=0, conf=MIN_CONFIDENCE, verbose=False)
                count = len(results[0].boxes)
                print(f"✅ Sonuç: {count} Kişi")
                
                payload = {
                    "mode": "AMFI_SNAPSHOT",
                    "occupancy": count,
                    "status": "Crowded" if count > 20 else "Normal",
                    "timestamp": time.time()
                }
                client.publish(MQTT_TOPIC, json.dumps(payload))
            
            print(f"💤 Uyku modu: {interval} saniye...")
            time.sleep(interval)

    # --- SINIF MODU (HIZ SINIRLAMASI EKLENDİ) ---
    elif SCENARIO == "SINIF":
        cap = cv2.VideoCapture(0)
        cap.set(3, 640)
        cap.set(4, 480)
        
        print("🎥 Canlı yayın başladı.")
        
        # Zamanlayıcı değişkeni
        last_upload_time = 0 
        
        while True:
            success, frame = cap.read()
            if not success: break
            
            # 1. Takip işlemi (Her karede çalışır, görüntü akıcı olur)
            results = model.track(frame, persist=True, classes=0, conf=MIN_CONFIDENCE, verbose=False)
            
            current_count = 0
            if results[0].boxes.id is not None:
                current_count = len(results[0].boxes.id)
            
            # Ekrana Çizim
            annotated_frame = results[0].plot()
            cv2.putText(annotated_frame, f"Canli: {current_count}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
            
            # Geri sayımı göster (Opsiyonel)
            time_left = DATA_UPLOAD_INTERVAL - (time.time() - last_upload_time)
            if time_left < 0: time_left = 0
            cv2.putText(annotated_frame, f"Gonderim: {time_left:.1f}s", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2)
            
            cv2.imshow("SINIF MODU", annotated_frame)
            
            # 2. VERİ GÖNDERİMİ (Sadece süre dolunca çalışır)
            # Bu kısım grafiğin "birbirine girmesini" engeller.
            current_time = time.time()
            if current_time - last_upload_time > DATA_UPLOAD_INTERVAL:
                
                payload = {
                    "mode": "SINIF_LIVE",
                    "occupancy": current_count,
                    "status": "Crowded" if current_count > 10 else "Normal",
                    "timestamp": current_time
                }
                client.publish(MQTT_TOPIC, json.dumps(payload))
                # Sayacı sıfırla
                last_upload_time = current_time
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()