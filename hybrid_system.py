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

def main():
    # 1. MODU SEÇ (Konsoldan)
    if len(sys.argv) > 1:
        SCENARIO = sys.argv[1].upper()
    else:
        SCENARIO = "SINIF" # Varsayılan

    print(f"🚀 SİSTEM BAŞLATILIYOR: {SCENARIO} MODU")

    # --- SENARYOYA GÖRE MODEL VE STRATEJİ SEÇİMİ ---
    if SCENARIO == "AMFI":
        # AMFİ: En güçlü model, ama yavaş çalışsa da olur (Snapshot)
        model_name = "yolov8x.pt" 
        print(f"📸 Mod: SNAPSHOT (Her 5 dakikada bir analiz)")
        print(f"🧠 Model: {model_name} (Extra Large - Maksimum Detay)")
        interval = 300 # 300 saniye = 5 Dakika (Test için bunu 10 yapabilirsin)
        
    elif SCENARIO == "SINIF":
        # SINIF: En hızlı model, sürekli akış (Real-time Tracking)
        model_name = "yolov8n.pt"
        print(f"🎥 Mod: CANLI TAKİP (Real-time Tracking)")
        print(f"🧠 Model: {model_name} (Nano - Yüksek FPS)")
    else:
        print("❌ HATA: Geçersiz mod. 'AMFI' veya 'SINIF' yazın.")
        return

    # Modeli Yükle
    print("⏳ Model yükleniyor...")
    model = YOLO(model_name)
    
    # MQTT Bağlantısı
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        print("✅ Buluta Bağlandı!")
    except:
        print("⚠️ İnternet yok, yerel modda çalışıyor.")

    # ==========================================
    # SENARYO 1: AMFİ (SNAPSHOT / ARALIKLI)
    # ==========================================
    if SCENARIO == "AMFI":
        while True:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Kamera açılıyor...")
            
            # Kamerayı Aç
            cap = cv2.VideoCapture(0)
            cap.set(3, 1280) # Yüksek çözünürlük
            cap.set(4, 720)
            
            # Işık ayarı için ısınma turları (5 kare boşa çek)
            for _ in range(5):
                cap.read()
                
            success, frame = cap.read()
            
            # Fotoğrafı alır almaz kamerayı kapat (Gizlilik + Enerji Tasarrufu)
            cap.release()
            
            if success:
                print("🧠 Görüntü analiz ediliyor (Extra Large Model)...")
                # Tracking değil Predict kullanıyoruz (Tek kare olduğu için)
                results = model.predict(frame, classes=0, conf=0.25, verbose=False)
                
                count = len(results[0].boxes)
                print(f"✅ Sayım Sonucu: {count} Kişi")
                
                # Veriyi Gönder
                payload = {
                    "mode": "AMFI_SNAPSHOT",
                    "occupancy": count,
                    "status": "Crowded" if count > 20 else "Normal",
                    "timestamp": time.time()
                }
                client.publish(MQTT_TOPIC, json.dumps(payload))
            
            else:
                print("❌ Kamera hatası!")

            # 5 Dakika Uyu
            print(f"💤 Sistem {interval} saniye uykuya geçiyor...")
            time.sleep(interval)

    # ==========================================
    # SENARYO 2: SINIF (CANLI / TRACKING)
    # ==========================================
    elif SCENARIO == "SINIF":
        # Kamerayı bir kere aç ve hep açık tut
        cap = cv2.VideoCapture(0)
        cap.set(3, 640) # Hız için daha düşük çözünürlük yeterli
        cap.set(4, 480)
        
        print("🎥 Canlı yayın başladı. Çıkmak için 'q'ya basın.")
        
        while True:
            success, frame = cap.read()
            if not success: break
            
            # CANLI TAKİP (Tracking)
            # persist=True -> Kişi ID'lerini hatırla
            results = model.track(frame, persist=True, classes=0, verbose=False)
            
            # ID sayısını al (Kutu sayısı yerine ID sayısı daha stabildir)
            current_count = 0
            if results[0].boxes.id is not None:
                current_count = len(results[0].boxes.id)
            
            # Görselleştirme (Ekrana çiz)
            annotated_frame = results[0].plot()
            cv2.putText(annotated_frame, f"Canli: {current_count}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
            cv2.imshow("SINIF MODU - Canli Takip", annotated_frame)
            
            # Veriyi sürekli göndermek yerine sadece değişim olduğunda 
            # veya belli aralıklarla göndermek daha iyidir ama şimdilik gönderiyoruz:
            payload = {
                "mode": "SINIF_LIVE",
                "occupancy": current_count,
                "status": "Crowded" if current_count > 10 else "Normal",
                "timestamp": time.time()
            }
            client.publish(MQTT_TOPIC, json.dumps(payload))
            
            # Çıkış kontrolü
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()