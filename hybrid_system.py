import cv2
from ultralytics import YOLO
import paho.mqtt.client as mqtt
import json
import time
import sys

# --- VARSAYILAN VE ORTAK AYARLAR ---
DEFAULT_MODE = "SINIF" 
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"
TIME_THRESHOLD = 0.5 # Stabilite filtresi (saniye)

def main():
    # 1. MODU SEÇ (Konsoldan argüman alma)
    if len(sys.argv) > 1:
        SCENARIO = sys.argv[1].upper()
    else:
        SCENARIO = DEFAULT_MODE
    
    # 2. Senaryoya Göre Ayarları Yükle
    # NOT: Tracking için daha hafif modeller seçildi (FPS artışı için)
    if SCENARIO == "AMFI":
        model_name = 'yolov8s.pt' # Small Model (Hız ve Başarı Dengesi)
        img_size = 1280
        sleep_time = 60           
        conf_thres = 0.35
        
    elif SCENARIO == "SINIF":
        model_name = 'yolov8n.pt' # Nano Model (En Hızlısı)
        img_size = 640
        sleep_time = 0.01         # Canlı akış için bekleme süresini kıstık
        conf_thres = 0.50         
        
    else:
        print("❌ HATA: Geçersiz Mod! Lütfen 'AMFI' veya 'SINIF' yazın.")
        return

    print(f"🚀 TRACKING SİSTEMİ BAŞLATILIYOR: MOD -> {SCENARIO}")
    print(f"🧠 Model Yükleniyor: {model_name}...")
    
    # 3. Model ve MQTT Yükleme
    model = YOLO(model_name)
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        print("✅ Buluta Bağlandı!")
    except:
        print("⚠️ İnternet yok, yerel modda çalışıyor.")

    # Kamerayı Başlat
    cap = cv2.VideoCapture(0)
    
    # Mac/PC Kamera Çözünürlüğü Ayarı
    cap.set(3, 1280)
    cap.set(4, 720)

    if not cap.isOpened():
        print("❌ HATA: Kamera açılamadı!")
        return

    # --- FİLTRE DEĞİŞKENLERİ ---
    official_count = 0 
    candidate_count = 0
    first_seen_time = time.time() 

    print("🎥 Kayıt Başladı! Çıkmak için 'q' tuşuna bas.")

    while True:
        success, frame = cap.read()
        if not success: break

        # [cite_start]4. TRACKING (TAKİP) İŞLEMİ [cite: 1]
        # persist=True -> Bir önceki karedeki kişileri hatırla demektir.
        # tracker="bytetrack.yaml" -> Hızlı ve stabil bir takip algoritmasıdır.
        results = model.track(frame, persist=True, classes=0, imgsz=img_size, conf=conf_thres, verbose=False, tracker="bytetrack.yaml")
        
        # Anlık tespit edilen kişi sayısı (Takip edilen ID sayısı)
        instant_count = 0
        
        # Sonuçları Görselleştirme
        for r in results:
            boxes = r.boxes
            for box in boxes:
                instant_count += 1
                
                # Koordinatları al
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                # Takip ID'sini al (Eğer ID atanmışsa)
                track_id = int(box.id[0]) if box.id is not None else 0
                
                # Kutuyu çiz
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                # ID numarasını kafasının üstüne yaz
                cv2.putText(frame, f"ID: {track_id}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # --- SINIF MODU FİLTRESİ ---
        if SCENARIO == "SINIF":
            if instant_count == candidate_count:
                duration = time.time() - first_seen_time
                if duration >= TIME_THRESHOLD:
                    official_count = candidate_count
            else:
                candidate_count = instant_count
                first_seen_time = time.time()
        else:
            official_count = instant_count

        # 5. BULUTA GÖNDER
        payload = {
            "room_id": "Mac-Kamera",
            "mode": SCENARIO,
            "occupancy": official_count,
            "status": "Crowded" if official_count > 5 else "Normal",
            "timestamp": time.time()
        }
        
        try:
            client.publish(MQTT_TOPIC, json.dumps(payload))
        except:
            pass

        # 6. BİLGİ EKRANI
        cv2.putText(frame, f"Mode: {SCENARIO}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        cv2.putText(frame, f"Count: {official_count}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        cv2.imshow('YOLOv8 Live Tracking', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'): break
            
        # Uyku Süresi (AMFI modunda gereksiz işlem yapmamak için)
        if SCENARIO == "AMFI":
            # Bekleme sırasında tuşa basılırsa çık
            if cv2.waitKey(int(sleep_time * 1000)) & 0xFF == ord('q'): break
        else:
            time.sleep(sleep_time)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()