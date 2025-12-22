import cv2
from ultralytics import YOLO
import math

# --- AYARLAR ---
# Videodan test yapıyorsan buraya "video1.mp4" yaz
# Kameradan yapıyorsan 0 yaz
VIDEO_SOURCE = "video1.mp4" 

def main():
    print("🧠 YOLOv8 Modeli Yükleniyor (Arkası dönükleri de görür)...")
    
    # YOLOv8 Nano modelini yükle (İlk çalışmada otomatik indirir)
    model = YOLO('yolov8n.pt')

    # Kamerayı/Videoyu Başlat
    cap = cv2.VideoCapture(VIDEO_SOURCE)

    # İnsan sınıfının ID'si genelde 0'dır ama biz yine de isimleri alalım
    classNames = ["person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train", "truck", "boat",
                  "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
                  "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
                  "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat",
                  "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
                  "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli",
                  "carrot", "hot dog", "pizza", "donut", "cake", "chair", "sofa", "pottedplant", "bed",
                  "diningtable", "toilet", "tvmonitor", "laptop", "mouse", "remote", "keyboard", "cell phone",
                  "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors",
                  "teddy bear", "hair drier", "toothbrush"
                  ]

    print("✅ Sistem Başlatıldı!")

    while True:
        ret, frame = cap.read()
        if not ret: break

        # Yapay Zeka Tahmini Yap (Stream=True daha hızlıdır)
        results = model(frame, stream=True, verbose=False)

        person_count = 0

        for r in results:
            boxes = r.boxes
            for box in boxes:
                # Sınıfı kontrol et (Sadece "person" yani ID 0)
                cls = int(box.cls[0])
                
                if classNames[cls] == "person":
                    # Güven skoru (0.4 üstü olsun)
                    conf = math.ceil((box.conf[0] * 100)) / 100
                    if conf > 0.4:
                        person_count += 1
                        
                        # Koordinatları al
                        x1, y1, x2, y2 = box.xyxy[0]
                        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

                        # KUTU ÇİZ (Mavi Renk - YOLO Tarzı)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                        
                        # Yazı Yaz
                        label = f"Insan {int(conf*100)}%"
                        t_size = cv2.getTextSize(label, 0, fontScale=0.5, thickness=1)[0]
                        c2 = x1 + t_size[0], y1 - t_size[1] - 3
                        cv2.rectangle(frame, (x1, y1), c2, (255, 0, 0), -1, cv2.LINE_AA)  # Yazı arka planı
                        cv2.putText(frame, label, (x1, y1 - 2), 0, 0.5, [255, 255, 255], thickness=1, lineType=cv2.LINE_AA)

        # Bilgi Paneli
        cv2.rectangle(frame, (0, 0), (250, 60), (0, 0, 0), cv2.FILLED)
        cv2.putText(frame, f"Kisi Sayisi: {person_count}", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow('YOLOv8 - Gelismis Tespit', frame)

        # 'q' ile çıkış
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()