import cv2
from ultralytics import YOLO

# --- AYARLAR ---
IMAGE_PATH = "test_foto.jpg"

def main():
    print(f"☢️ ULTRA MOD BAŞLATILIYOR: {IMAGE_PATH}")

    # 1. EN BÜYÜK MODELİ YÜKLE (Extra Large)
    # Bu model çok ağırdır ama detayları kaçırmaz.
    print("⬇️ YOLOv8 X-Large modeli hazırlanıyor...")
    model = YOLO('yolov8x.pt') 

    # 2. Fotoğrafı Oku
    frame = cv2.imread(IMAGE_PATH)
    if frame is None:
        print("❌ HATA: Fotoğraf bulunamadı!")
        return

    # 3. Analiz Et (Limitleri Zorluyoruz)
    print("👀 Piksel piksel taranıyor...")
    
    # imgsz=1600: Resmi devasa boyuta getirip bakar (Arka sıralar için)
    # conf=0.15: %15 ihtimal görsen bile insan kabul et (Cesur ol)
    # iou=0.45: İnsanlar birbirine yapışıksa silme, ayrı kabul et
    results = model(frame, classes=0, imgsz=1600, conf=0.15, iou=0.45, verbose=False)

    person_count = 0

    # 4. Sonuçları Çiz
    for r in results:
        boxes = r.boxes
        for box in boxes:
            person_count += 1
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # İnce Mavi Kutu
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 1)
            
            # Sadece bir nokta koy (Kutular görüntüyü boğmasın)
            center_x = x1 + (x2-x1)//2
            center_y = y1 + (y2-y1)//5 # Kafaya yakın bir yere nokta koy
            cv2.circle(frame, (center_x, center_y), 3, (0, 0, 255), -1)

    # 5. Sonucu Göster
    print(f"✅ BİTTİ! Toplam İnsan Sayısı: {person_count}")
    
    cv2.putText(frame, f"Toplam: {person_count}", (30, 100), 
                cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 5)

    # Resmi ekrana sığacak şekilde küçültüp göster
    h, w = frame.shape[:2]
    scale = 1400 / w 
    display_frame = cv2.resize(frame, (int(w*scale), int(h*scale)))

    cv2.imshow(f'YOLOv8 X-Large - {person_count} Kisi', display_frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()