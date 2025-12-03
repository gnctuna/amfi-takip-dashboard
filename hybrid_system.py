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

# YENİ AYAR: Stabilite Filtresi
# Yapay zeka kaç kare boyunca aynı sayıyı görmeli?
STABILITY_FRAMES = 5 

# Veri Gönderme Sıklığı (Saniye)
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
    elif SCENARIO == "SINIF":
        model_name = "yolov8n.pt"
        print(f"🎥 Mod: CANLI TAKİP (Stabilite: {STABILITY_FRAMES} kare)")
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
        interval = 300 # 5 Dakika
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

    # --- SINIF MODU (STABİLİTE FİLTRESİ EKLENDİ) ---
    elif SCENARIO == "SINIF":
        cap = cv2.VideoCapture(0)
        cap.set(3, 640)
        cap.set(4, 480)
        
        print("🎥 Canlı yayın başladı.")
        
        last_upload_time = 0 
        
        # --- FİLTRE DEĞİŞKENLERİ ---
        official_count = 0      # Ekrana yansıyan ve gönderilen KESİN sayı
        candidate_count = -1    # Şu an test ettiğimiz "aday" sayı
        frame_streak = 0        # Aday sayı kaç karedir değişmedi?

        while True:
            success, frame = cap.read()
            if not success: break
            
            # 1. Takip işlemi
            results = model.track(frame, persist=True, classes=0, conf=MIN_CONFIDENCE, verbose=False)
            
            # O anki HAM (Raw) sayı
            raw_count = 0
            if results[0].boxes.id is not None:
                raw_count = len(results[0].boxes.id)
            
            # --- 2. STABİLİTE MANTIĞI (Burayı Ekledik) ---
            if raw_count == candidate_count:
                # Eğer sayı değişmediyse sayacı artır
                frame_streak += 1
            else:
                # Sayı değiştiyse (titreme olduysa), yeni sayıyı aday yap ve sayacı sıfırla
                candidate_count = raw_count
                frame_streak = 0
            
            # Eğer aday sayı 5 kare boyunca (STABILITY_FRAMES) aynı kaldıysa, onu RESMİ sayı yap
            if frame_streak >= STABILITY_FRAMES:
                official_count = candidate_count
                # Sayacı taşmasın diye sınırlayabiliriz (Opsiyonel)
                if frame_streak > 100: frame_streak = 100

            # --- EKRAN GÖSTERİMİ ---
            annotated_frame = results[0].plot()
            
            # Ekranda "Resmi" sayıyı göster (Ham sayıyı değil)
            cv2.putText(annotated_frame, f"Kisi: {official_count}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
            
            # Debug için sağ alta ufak bilgi (Ham sayı ne, ne kadar emin?)
            debug_info = f"Raw: {raw_count} | Streak: {frame_streak}/{STABILITY_FRAMES}"
            cv2.putText(annotated_frame, debug_info, (10, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)

            cv2.imshow("SINIF MODU (Stabilize)", annotated_frame)
            
            # --- 3. VERİ GÖNDERİMİ ---
            current_time = time.time()
            if current_time - last_upload_time > DATA_UPLOAD_INTERVAL:
                
                payload = {
                    "mode": "SINIF_LIVE",
                    "occupancy": official_count, # Artık titrek sayı değil, emin olduğumuz sayı gidiyor
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