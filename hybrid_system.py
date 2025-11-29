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
TIME_THRESHOLD = 0.5 # Sınıf modunda stabilite filtresi (saniye cinsinden)

def main():
    # 1. MODU SEÇ (sys.argv)
    if len(sys.argv) > 1:
        SCENARIO = sys.argv[1].upper()
    else:
        SCENARIO = DEFAULT_MODE
    
    # 2. Senaryoya Göre Ayarları Yükle
    if SCENARIO == "AMFI":
        model_name = 'yolov8x.pt' # En Güçlü Model
        img_size = 1280
        sleep_time = 60           # 1 Dakika bekle
        conf_thres = 0.40
        
    elif SCENARIO == "SINIF":
        model_name = 'yolov8m.pt' # Medium Model (Daha Zeki ve Stabil)
        img_size = 640
        sleep_time = 0.05         # Canlı akış hızı
        conf_thres = 0.50         # Güven eşiği
        
    else:
        print("❌ HATA: Geçersiz Mod! Lütfen 'AMFI' veya 'SINIF' yazın.")
        return

    print(f"🚀 KAMERA BAŞLATILIYOR: MOD -> {SCENARIO}")
    
    # 3. Model ve MQTT Yükleme
    model = YOLO(model_name)
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        print("✅ Buluta Bağlandı!")
    except:
        print("⚠️ İnternet yok, yerel modda çalışıyor.")

    # Kamerayı Başlat (0 = Webcam)
    cap = cv2.VideoCapture(0)
    cap.set(3, 1280)
    cap.set(4, 720)

    if not cap.isOpened():
        print("❌ HATA: Kamera açılamadı! İzinleri kontrol et.")
        return

    # --- FİLTRE DEĞİŞKENLERİ ---
    official_count = 0 
    candidate_count = 0
    first_seen_time = time.time() 

    print("🎥 Kayıt Başladı! Çıkmak için 'q' tuşuna bas.")

    while True:
        success, frame = cap.read()
        if not success: break

        # 4. ANALİZ VE SAYIM
        results = model(frame, classes=0, imgsz=img_size, conf=conf_thres, iou=0.45, verbose=False)
        instant_count = 0
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                instant_count += 1
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # --- ZAMAN TABANLI AKILLI FİLTRELEME (Sadece SINIF modunda) ---
        if SCENARIO == "SINIF":
            if instant_count == candidate_count:
                duration = time.time() - first_seen_time
                if duration >= TIME_THRESHOLD:
                    official_count = candidate_count
            else:
                candidate_count = instant_count
                first_seen_time = time.time()
        else:
            # AMFİ modunda filtreye gerek yok, gördüğümüzü kabul ederiz.
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

        # 6. EKRANDA GÖSTER
        cv2.putText(frame, f"Giden Veri: {official_count}", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow('Akilli Kamera (Cikmak icin q)', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'): break
            
        # Uyku Süresi
        if SCENARIO == "AMFI":
            if cv2.waitKey(int(sleep_time * 1000)) & 0xFF == ord('q'): break
        else:
            time.sleep(sleep_time)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()