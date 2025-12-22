import cv2
from ultralytics import YOLO
import paho.mqtt.client as mqtt
import json
import time

# --- AYARLAR ---
IMAGE_PATH = "test_foto.jpg"  # Test edilecek fotoğraf
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"

def main():
    print("🚀 SİSTEM BAŞLATILIYOR (Akıllı Filtre Modu)...")

    # 1. MQTT (İnternet) Bağlantısı
    print("📡 Buluta bağlanılıyor...")
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        print(f"✅ Bağlantı Başarılı! Kanal: {MQTT_TOPIC}")
    except Exception as e:
        print(f"❌ HATA: İnternet bağlantısı yok! ({e})")
        return

    # 2. Yapay Zeka Modelini Yükle
    print("🧠 YOLOv8 X-Large Modeli yükleniyor...")
    model = YOLO('yolov8x.pt')

    # 3. Fotoğrafı Oku
    frame = cv2.imread(IMAGE_PATH)
    if frame is None:
        print("❌ Fotoğraf bulunamadı!")
        return

    # 4. Analiz Et 
    # conf=0.40: %40'ın altındakileri baştan ele
    # iou=0.45: Standart çakışma ayarı
    print("👀 Analiz yapılıyor...")
    results = model(frame, classes=0, imgsz=1600, conf=0.40, iou=0.45, verbose=False)

    person_count = 0
    h_img, w_img, _ = frame.shape # Resmin boyutlarını al (Filtre için lazım)

    # 5. Sonuçları Say ve Çiz (BURASI DEĞİŞTİ - FİLTRELER EKLENDİ)
    for r in results:
        boxes = r.boxes
        for box in boxes:
            # Koordinatları al
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            
            # Kutunun genişliğini ve yüksekliğini hesapla
            w_box = x2 - x1
            h_box = y2 - y1
            
            # --- FİLTRE 1: MİNİK KUTULARI AT ---
            # Eğer kutu resmin %1.5'inden küçükse gürültüdür (poster lekesi vb.)
            if w_box < w_img * 0.015 or h_box < h_img * 0.015:
                continue 

            # --- FİLTRE 2: ŞEKİL FİLTRESİ ---
            # İnsan dikeydir. Eğer kutu çok yatay ve basıksa (Masa gibi), insan değildir.
            aspect_ratio = w_box / h_box
            if aspect_ratio > 1.8: # Eni boyunun 1.8 katından fazlaysa at
                continue

            # Filtreleri geçenleri SAY
            person_count += 1
            
            # Mavi kutu çiz
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 1)
            # Kırmızı nokta koy
            center_x = x1 + (x2-x1)//2
            center_y = y1 + (y2-y1)//5
            cv2.circle(frame, (center_x, center_y), 3, (0, 0, 255), -1)

    print(f"✅ TESPİT TAMAMLANDI: {person_count} Kişi")

    # 6. Veriyi Paketle ve Gönder
    payload = {
        "room_id": "Amfi-101",
        "occupancy": person_count,
        "status": "Crowded" if person_count > 20 else "Normal",
        "timestamp": time.time()
    }
    
    try:
        client.publish(MQTT_TOPIC, json.dumps(payload))
        print(f"📨 MESAJ BULUTA GÖNDERİLDİ: {payload}")
    except:
        print("❌ Mesaj gönderilemedi.")

    # 7. Ekranda Göster
    h, w = frame.shape[:2]
    # Ekrana sığacak kadar küçült
    scale = 1200 / w 
    display_frame = cv2.resize(frame, (int(w*scale), int(h*scale)))

    cv2.putText(display_frame, f"Buluta Giden Sayi: {person_count}", (30, 60), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)

    cv2.imshow('Final IoT System - Filtered', display_frame)
    print("Kapatmak için pencereye tıkla ve bir tuşa bas.")
    
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    client.disconnect()

if __name__ == "__main__":
    main()