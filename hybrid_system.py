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
STABILITY_FRAMES = 5       # Kaç kare boyunca sayı değişmemeli?
DATA_UPLOAD_INTERVAL = 2.0 # Veri kaç saniyede bir gönderilsin?

# AMFİ MODU AYARLARI
AMFI_INTERVAL = 300        # 5 Dakika (Test için 10 yapabilirsin)

def open_camera():
    """
    Mac için Akıllı Kamera Açıcı:
    Önce 0'ı dener, açılmazsa 1'i dener.
    """
    print("📷 Kamera aranıyor...")
    
    # 1. Deneme: Varsayılan Kamera (0)
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        print("✅ Kamera (Index 0) başarıyla açıldı.")
        return cap
    
    # 2. Deneme: İkinci Kamera (1) - Mac'te bazen bu gerekir
    print("⚠️ Index 0 başarısız, Index 1 deneniyor...")
    cap = cv2.VideoCapture(1)
    if cap.isOpened():
        print("✅ Kamera (Index 1) başarıyla açıldı.")
        return cap
        
    print("❌ HATA: Hiçbir kamera açılamadı! İzinleri kontrol edin.")
    return None

def main():
    # 1. MODU SEÇ
    if len(sys.argv) > 1:
        SCENARIO = sys.argv[1].upper()
    else:
        SCENARIO = "SINIF"

    print(f"🚀 SİSTEM BAŞLATILIYOR: {SCENARIO} MODU")
    print(f"🛡️ Güven Eşiği: %{int(MIN_CONFIDENCE*100)}")

    # 2. SENARYO AYARLARI
    if SCENARIO == "AMFI":
        model_name = "yolov8x.pt" 
        print(f"📸 Mod: SNAPSHOT (Her {AMFI_INTERVAL} saniyede bir analiz)")
    elif SCENARIO == "SINIF":
        model_name = "yolov8n.pt"
        print(f"🎥 Mod: CANLI TAKİP (Stabilite: {STABILITY_FRAMES} kare)")
    else:
        print("❌ HATA: Geçersiz mod. 'AMFI' veya 'SINIF' yazın.")
        return

    print("⏳ Model yükleniyor...")
    model = YOLO(model_name)
    
    # MQTT Bağlantısı (Callback API Hatası Düzeltildi)
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.connect(MQTT_BROKER, 1883, 60)
        print("✅ Buluta Bağlandı!")
    except Exception as e:
        print(f"⚠️ İnternet veya MQTT Hatası: {e}")
        client = mqtt.Client() # Fallback

    # ==========================================
    # SENARYO 1: AMFİ (SNAPSHOT / ARALIKLI)
    # ==========================================
    if SCENARIO == "AMFI":
        while True:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Kamera açılıyor...")
            
            cap = open_camera()
            if cap is None: break # Kamera yoksa çık
            
            # Mac kameraları bazen geç uyanır, ısınma turları atalım
            cap.set(3, 1280)
            cap.set(4, 720)
            for _ in range(10): 
                cap.read()
                
            success, frame = cap.read()
            cap.release() # İşi bitince hemen kapat (Gizlilik)
            
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
            else:
                print("❌ Görüntü alınamadı!")
            
            print(f"💤 Sistem {AMFI_INTERVAL} saniye uykuya geçiyor...")
            time.sleep(AMFI_INTERVAL)

    # ==========================================
    # SENARYO 2: SINIF (CANLI / STABİLİTE)
    # ==========================================
    elif SCENARIO == "SINIF":
        cap = open_camera()
        if cap is None: return

        cap.set(3, 640)
        cap.set(4, 480)
        
        print("🎥 Canlı yayın başladı. Çıkmak için 'q'ya basın.")
        
        last_upload_time = 0 
        
        # Filtre Değişkenleri
        official_count = 0      
        candidate_count = -1    
        frame_streak = 0        

        while True:
            success, frame = cap.read()
            if not success:
                print("❌ Kamera akışı koptu!")
                break
            
            # 1. Takip işlemi
            results = model.track(frame, persist=True, classes=0, conf=MIN_CONFIDENCE, verbose=False)
            
            # Ham Sayı
            raw_count = 0
            if results[0].boxes.id is not None:
                raw_count = len(results[0].boxes.id)
            
            # 2. Stabilite Filtresi (Debouncing)
            if raw_count == candidate_count:
                frame_streak += 1
            else:
                candidate_count = raw_count
                frame_streak = 0
            
            # 5 kare boyunca değişmediyse onayla
            if frame_streak >= STABILITY_FRAMES:
                official_count = candidate_count
                if frame_streak > 20: frame_streak = 20 # Sayaç taşmasın

            # 3. Ekran Gösterimi
            annotated_frame = results[0].plot()
            cv2.putText(annotated_frame, f"Kisi: {official_count}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
            cv2.putText(annotated_frame, f"Raw: {raw_count} | Confirmed: {frame_streak >= STABILITY_FRAMES}", (10, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)

            cv2.imshow("SINIF MODU (Stabilize)", annotated_frame)
            
            # 4. Hız Sınırlı Gönderim (2 Saniyede 1)
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