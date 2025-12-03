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

# SINIF MODU AYARLARI
STABILITY_FRAMES = 5       
DATA_UPLOAD_INTERVAL = 2.0 

# AMFİ MODU AYARLARI
AMFI_INTERVAL = 300        # 5 Dakika (Test için 10-20 yapabilirsin)

def open_camera():
    """Mac için Akıllı Kamera Açıcı"""
    print("📷 Kamera aranıyor...")
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        print("✅ Kamera (Index 0) başarıyla açıldı.")
        return cap
    
    print("⚠️ Index 0 başarısız, Index 1 deneniyor...")
    cap = cv2.VideoCapture(1)
    if cap.isOpened():
        print("✅ Kamera (Index 1) başarıyla açıldı.")
        return cap
        
    print("❌ HATA: Hiçbir kamera açılamadı!")
    return None

def main():
    if len(sys.argv) > 1:
        SCENARIO = sys.argv[1].upper()
    else:
        SCENARIO = "SINIF"

    print(f"🚀 SİSTEM BAŞLATILIYOR: {SCENARIO} MODU")
    
    if SCENARIO == "AMFI":
        model_name = "yolov8x.pt" 
        print(f"📸 Mod: SNAPSHOT (Her {AMFI_INTERVAL} saniyede bir foto)")
    elif SCENARIO == "SINIF":
        model_name = "yolov8n.pt"
        print(f"🎥 Mod: CANLI TAKİP")
    else:
        return

    print("⏳ Model yükleniyor...")
    model = YOLO(model_name)
    
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.connect(MQTT_BROKER, 1883, 60)
        print("✅ Buluta Bağlandı!")
    except:
        client = mqtt.Client()

    # ==========================================
    # SENARYO 1: AMFİ (SNAPSHOT / ARALIKLI)
    # ==========================================
    if SCENARIO == "AMFI":
        while True:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Kamera açılıyor (Snapshot)...")
            
            cap = open_camera()
            if cap is None: break 
            
            # Isınma turları
            cap.set(3, 1280)
            cap.set(4, 720)
            for _ in range(10): cap.read()
                
            success, frame = cap.read()
            cap.release() # Fotoğrafı aldık, kamerayı hemen kapat (Privacy)
            
            if success:
                print("🧠 Analiz ediliyor...")
                results = model.predict(frame, classes=0, conf=MIN_CONFIDENCE, verbose=False)
                count = len(results[0].boxes)
                print(f"✅ Sonuç: {count} Kişi")
                
                # --- GÖRSELLEŞTİRME ---
                annotated_frame = results[0].plot()
                
                timestamp = datetime.now().strftime('%H:%M:%S')
                cv2.putText(annotated_frame, f"SON DURUM: {timestamp}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(annotated_frame, f"Kisi Sayisi: {count}", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.putText(annotated_frame, f"Siradaki cekim: {AMFI_INTERVAL}s sonra...", (10, 680), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                
                # Görüntüyü ekrana bas
                cv2.imshow("AMFI MODU - SON DURUM (Kapatmak icin 'q')", annotated_frame)
                
                # MQTT Gönderimi
                payload = {
                    "mode": "AMFI_SNAPSHOT",
                    "occupancy": count,
                    "status": "Crowded" if count > 20 else "Normal",
                    "timestamp": time.time()
                }
                client.publish(MQTT_TOPIC, json.dumps(payload))
            else:
                print("❌ Görüntü alınamadı!")
            
            # --- AKILLI BEKLEME DÖNGÜSÜ ---
            # time.sleep() kullanmıyoruz, çünkü o pencereyi dondurur.
            # Onun yerine döngü içinde bekliyoruz ki pencere canlı kalsın.
            print(f"💤 Bekleme modu ({AMFI_INTERVAL}s)...")
            start_wait = time.time()
            
            while (time.time() - start_wait) < AMFI_INTERVAL:
                # Her 100ms'de bir tuşa basıldı mı diye kontrol et
                # Bu sayede pencere donmaz ("Not Responding" hatası vermez)
                if cv2.waitKey(100) & 0xFF == ord('q'):
                    print("Program kapatılıyor...")
                    sys.exit()

    # ==========================================
    # SENARYO 2: SINIF (CANLI / STABİLİTE)
    # ==========================================
    elif SCENARIO == "SINIF":
        cap = open_camera()
        if cap is None: return

        cap.set(3, 640)
        cap.set(4, 480)
        print("🎥 Canlı yayın başladı.")
        
        last_upload_time = 0 
        official_count = 0      
        candidate_count = -1    
        frame_streak = 0        

        while True:
            success, frame = cap.read()
            if not success: break
            
            results = model.track(frame, persist=True, classes=0, conf=MIN_CONFIDENCE, verbose=False)
            
            raw_count = 0
            if results[0].boxes.id is not None:
                raw_count = len(results[0].boxes.id)
            
            if raw_count == candidate_count:
                frame_streak += 1
            else:
                candidate_count = raw_count
                frame_streak = 0
            
            if frame_streak >= STABILITY_FRAMES:
                official_count = candidate_count
                if frame_streak > 20: frame_streak = 20

            annotated_frame = results[0].plot()
            cv2.putText(annotated_frame, f"Kisi: {official_count}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
            cv2.putText(annotated_frame, f"Raw: {raw_count} | Confirmed: {frame_streak >= STABILITY_FRAMES}", (10, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)

            cv2.imshow("SINIF MODU (Stabilize)", annotated_frame)
            
            current_time = time.time()
            if current_time - last_upload_time > DATA_UPLOAD_INTERVAL:
                payload = {
                    "mode": "SINIF_LIVE",
                    "occupancy": official_count,
                    "status": "Crowded" if official_count > 10 else "Normal",
                    "timestamp": current_time
                }
                client.publish(MQTT_TOPIC, json.dumps(payload))
                last_upload_time = current_time
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()