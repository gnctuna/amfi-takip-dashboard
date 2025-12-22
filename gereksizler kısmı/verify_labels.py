import cv2
import os

# --- AYARLAR ---
IMAGE_DIR = "dataset/images"
LABEL_DIR = "dataset/labels"

# classes.txt dosyasını oku, yoksa varsayılanı kullan
CLASSES = []
if os.path.exists(f"{LABEL_DIR}/classes.txt"):
    with open(f"{LABEL_DIR}/classes.txt", "r") as f:
        CLASSES = [line.strip() for line in f.readlines()]
else:
    CLASSES = ["person"] 

def draw_yolo_labels(img, label_path):
    if not os.path.exists(label_path):
        return img

    height, width, _ = img.shape

    with open(label_path, "r") as f:
        lines = f.readlines()
        
    for line in lines:
        parts = line.strip().split()
        
        # YOLO formatı: class_id center_x center_y w h
        class_id = int(parts[0])
        x_center = float(parts[1]) * width
        y_center = float(parts[2]) * height
        box_width = float(parts[3]) * width
        box_height = float(parts[4]) * height
        
        # Koordinat hesapla
        x_start = int(x_center - (box_width / 2))
        y_start = int(y_center - (box_height / 2))
        x_end = int(x_start + box_width)
        y_end = int(y_start + box_height)

        # Kutuyu Çiz (Mavi)
        cv2.rectangle(img, (x_start, y_start), (x_end, y_end), (255, 0, 0), 2)
        
        # Etiket İsmini Yaz
        label_text = CLASSES[class_id] if class_id < len(CLASSES) else f"Class {class_id}"
        cv2.putText(img, label_text, (x_start, y_start - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
    
    return img

def main():
    print("--- VERI DOGRULAMA MODU ---")
    print("Pencere açıldığında:")
    print(" -> Sonraki resim için herhangi bir TUŞA bas.")
    print(" -> Çıkmak için 'q' tuşuna bas.")

    image_files = [f for f in os.listdir(IMAGE_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    
    if not image_files:
        print("HATA: 'dataset/images' klasöründe resim bulunamadı!")
        return

    for img_file in image_files:
        img_path = os.path.join(IMAGE_DIR, img_file)
        # Resmin uzantısını atıp .txt ekle (Örn: test1.jpg -> test1.txt)
        txt_name = os.path.splitext(img_file)[0] + ".txt"
        label_path = os.path.join(LABEL_DIR, txt_name)
        
        frame = cv2.imread(img_path)
        if frame is None:
            print(f"Uyarı: {img_file} okunamadı.")
            continue
            
        # Çizim Yap
        processed_frame = draw_yolo_labels(frame, label_path)
        
        # Ekrana Sığdır (Büyük resimler için)
        display_frame = cv2.resize(processed_frame, (800, 600))
        
        cv2.imshow("Label Verification", display_frame)
        
        # Bekle
        key = cv2.waitKey(0)
        if key & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
    print("Doğrulama tamamlandı.")

if __name__ == "__main__":
    main()