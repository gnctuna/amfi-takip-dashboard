import cv2
from ultralytics import YOLO
import paho.mqtt.client as mqtt
import json
import time
import sys

# --- VARSAYILAN AYARLAR ---
DEFAULT_MODE = "SINIF" 

# --- AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"

# --- FİLTRE AYARI ---
# Sınıf modunda kaç saniye boyunca sayının aynı kalması gerektiğini belirler.
# 0.5 saniye gecikme, titremeleri ve anlık hataları (battaniye vb.) önler.
TIME_THRESHOLD = 0.5 

def main():
    if len(sys.argv) > 1:
        SCENARIO = sys.argv[1].upper()
    else:
        SCENARIO = DEFAULT_MODE

    print(f"🚀 KAMERA BAŞLATILIYOR: MOD -> {SCENARIO}")

    if SCENARIO == "AMFI":
        model_name = 'yolov8x.pt' # En Güçlü Model
        img_size = 1280
        sleep_time = 60           # 1 Dakika bekle
        conf_thres = 0.40
        print("ℹ️  Amfi Modu: Filtreleme kapalı (Tek kare analiz).")
        
    elif SCENARIO == "SINIF":
        model_name = 'yolov8m.pt' # Medium Model (Daha Zeki)
        img_size = 640
        sleep_time = 0.05         # Hızlı akış
        conf_thres = 0.50         # Zeki olduğu için eşiği normal tutuyoruz
        print(f"ℹ️  Sınıf Modu: Akıllı Model (Medium) + Zaman Filtresi ({TIME_THRESHOLD}sn).")
        
    else:
        print("❌ HATA: Geçersiz Mod!")
        return

    # Modeli Yükle
    model = YOLO(model_name)

    # MQTT Bağlantısı
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        print("✅ Buluta Bağlandı!")
    except:
        print("⚠️ İnternet yok, yerel modda çalışıyor.")

    # Kamerayı Başlat
    cap = cv2.VideoCapture(0)
    cap.set(3, 1280)
    cap.set(4, 720)

    if not cap.isOpened():
        print("❌ HATA: Kamera açılamadı!")
        return

    # --- FİLTRE DEĞİŞKENLERİ ---
    official_count = 0          # Resmileşmiş sayı (Buluta giden)
    candidate_count = 0         # Aday sayı
    first_seen_time = 0         # Adayı ilk gördüğümüz zaman

    print("🎥 Kayıt Başladı! Çıkmak için 'q' tuşuna bas.")

    while True:
        success, frame = cap.read()
        if not success: break

        # --- ANALİZ ---
        results = model(frame, classes=0, imgsz=img_size, conf=conf_thres, iou=0.45, verbose=False)
        
        # Anlık olarak bu karede kaç kişi var?
        instant_count = 0
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                instant_count += 1
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                # Çizim
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # --- ZAMAN TABANLI AKILLI FİLTRELEME (Sadece SINIF modunda) ---
        if SCENARIO == "SINIF":
            # Eğer anlık sayı, aday sayı ile aynıysa
            if instant_count == candidate_count:
                # Ne kadar süredir bu sayıyı görüyoruz?
                duration = time.time() - first_seen_time
                
                # Eğer süre eşiği aşıldıysa (0.5 saniye), bunu RESMİ yap
                if duration >= TIME_THRESHOLD:
                    official_count = candidate_count
            else:
                # Sayı değişti! Kronometreyi sıfırla
                candidate_count = instant_count
                first_seen_time = time.time()

        else:
            # AMFİ modunda filtre yok, ne gördüysek odur.
            official_count = instant_count

        # --- BİLGİ PANELİ ---
        cv2.rectangle(frame, (0,0), (350, 100), (0,0,0), -1)
        
        if SCENARIO == "SINIF":
            # Yeşil: Buluta Giden (Kararlı), Gri: Anlık (Titreşen)
            cv2.putText(frame, f"Giden Veri: {official_count}", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Anlik Gorulen: {instant_count}", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        else:
            cv2.putText(frame, f"Sayi: {official_count}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)

        # --- BULUTA GÖNDER ---
        payload = {
            "room_id": "Mac-Kamera",
            "mode": SCENARIO,
            "occupancy": official_count, # Filtrelenmiş sayı
            "status": "Crowded" if official_count > 5 else "Normal",
            "timestamp": time.time()
        }
        
        try:
            client.publish(MQTT_TOPIC, json.dumps(payload))
        except:
            pass

        cv2.imshow('Akilli Kamera (Cikmak icin q)', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break
            
        if SCENARIO == "AMFI":
            if cv2.waitKey(60000) & 0xFF == ord('q'): break
        else:
            time.sleep(sleep_time)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()