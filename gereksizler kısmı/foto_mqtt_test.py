import cv2
from ultralytics import YOLO
import paho.mqtt.client as mqtt
import json
import time # Zaman damgası için

# --- AYARLAR ---
IMAGE_PATH = "test_foto.jpg" # Test edilecek fotoğrafın adı (Burayı değiştir!)

# --- MQTT BULUT AYARLARI ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "tunagenc/occupancy"

def main():
    print(f"🖼 FOTOĞRAF + MQTT TEST MODU: {IMAGE_PATH} işleniyor...")

    # 1. MQTT Bağlantısı
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        print(f"✅ Buluta Bağlandı! Kanal: {MQTT_TOPIC}")
    except:
        print("❌ HATA: İnternet bağlantını kontrol et!")
        return

    # 2. YOLO Modelini Yükle
    # verbose=False terminali temiz tutar
    model = YOLO('yolov8n.pt')

    # 3. Fotoğrafı Oku
    frame = cv2.imread(IMAGE_PATH)
    if frame is None:
        print(f"HATA: {IMAGE_PATH} bulunamadı! İsmi doğru yazdın mı?")
        client.disconnect()
        return

    # 4. Tek Seferlik Tespit Yap
    print("🧠 YOLOv8 düşünüyor...")
    results = model(frame, verbose=False)
    person_count = 0

    # Sonuçları işle
    for r in results:
        boxes = r.boxes
        for box in boxes:
            cls = int(box.cls[0])
            # YOLO'nun sınıf listesinden ismi al
            currentClass = model.names[cls]

            if currentClass == "person":
                conf = float(box.conf[0])
                if conf > 0.4: # %40 üzeri güven
                    person_count += 1
                    # Çizim yap
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                    
                    # Etiket yaz (Opsiyonel)
                    label = f"{int(conf*100)}%"
                    cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,0), 2)

    # 5. Sonucu Buluta Gönder (Anında)
    payload = {
        "room": "Foto Test Odasi",
        "count": person_count,
        "status": "Test",
        "timestamp": time.time()
    }
    # json.dumps veriyi pakete çevirir
    client.publish(MQTT_TOPIC, json.dumps(payload))
    print(f"📡 BULUTA GÖNDERİLDİ: {person_count} Kişi tespit edildi.")

    # 6. Resmi Ekranda Göster
    cv2.putText(frame, f"Toplam: {person_count}", (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
    cv2.imshow('Foto + MQTT Test Sonucu', frame)

    print("Programı kapatmak için resim penceresindeyken bir tuşa bas...")
    # waitKey(0) sonsuza kadar tuş basılmasını bekler
    cv2.waitKey(0) 
    cv2.destroyAllWindows()
    client.disconnect()

if __name__ == "__main__":
    main()