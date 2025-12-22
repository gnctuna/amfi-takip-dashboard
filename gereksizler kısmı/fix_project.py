import os

# 1. LABELMAP DÜZELTME (??? yerine person yazıyoruz)
LABEL_PATH = "models/labelmap.txt"

# COCO Veri setinin doğru sıralaması (Person en başta)
correct_labels = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "???", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
    "cow", "elephant", "bear", "zebra", "giraffe", "???", "backpack", "umbrella", "???", "???", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "???", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut",
    "cake", "chair", "couch", "potted plant", "bed", "???", "dining table", "???", "???", "toilet",
    "???", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster",
    "sink", "refrigerator", "???", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]

print("1. Etiket dosyası düzeltiliyor...")
with open(LABEL_PATH, "w") as f:
    for label in correct_labels:
        f.write(label + "\n")
print("✅ labelmap.txt güncellendi (Artık '???' yerine 'person' yazacak).")

# 2. MAIN.PY GÜNCELLEME (Temiz Mod)
MAIN_CODE = """import cv2
import numpy as np
import tensorflow as tf

# Modellerin Yeri
MODEL_PATH = "models/detect.tflite"
LABEL_PATH = "models/labelmap.txt"
MIN_CONFIDENCE = 0.5  # %50 altını gösterme (Kedileri engelle)

def main():
    # 1. Modeli Yükle
    interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    height = input_details[0]['shape'][1]
    width = input_details[0]['shape'][2]

    # Etiketleri oku
    with open(LABEL_PATH, 'r') as f:
        labels = [line.strip() for line in f.readlines()]

    cap = cv2.VideoCapture(0)

    print("✅ Yapay Zeka Hazır! Sadece insanları arıyor...")

    while True:
        ret, frame = cap.read()
        if not ret: break

        # Görüntüyü hazırla
        frame_resized = cv2.resize(frame, (width, height))
        input_data = np.expand_dims(frame_resized, axis=0)

        # Tahmin et
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()

        boxes = interpreter.get_tensor(output_details[0]['index'])[0]
        classes = interpreter.get_tensor(output_details[1]['index'])[0]
        scores = interpreter.get_tensor(output_details[2]['index'])[0]

        person_count = 0

        for i in range(len(scores)):
            # Sadece %50'den eminse VE nesne "person" ise
            if scores[i] > MIN_CONFIDENCE:
                class_id = int(classes[i])
                
                # Liste dışına çıkma hatası önlemi
                if class_id < len(labels):
                    object_name = labels[class_id]
                else:
                    continue 

                if object_name == "person":
                    person_count += 1
                    
                    # Koordinatları al
                    ymin, xmin, ymax, xmax = boxes[i]
                    im_height, im_width, _ = frame.shape
                    
                    left = int(xmin * im_width)
                    top = int(ymin * im_height)
                    right = int(xmax * im_width)
                    bottom = int(ymax * im_height)

                    # YEŞİL KUTU
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    
                    # Etiket
                    label = f"Insan: {int(scores[i]*100)}%"
                    label_size, base_line = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                    top = max(top, label_size[1])
                    cv2.rectangle(frame, (left, top - label_size[1]), (left + label_size[0], top + base_line), (255, 255, 255), cv2.FILLED)
                    cv2.putText(frame, label, (left, top), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        # Bilgi Paneli
        cv2.rectangle(frame, (0, 0), (250, 50), (0, 0, 0), cv2.FILLED)
        cv2.putText(frame, f"Odadaki Kisi: {person_count}", (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        cv2.imshow("Privacy Occupancy AI", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
"""

print("2. main.py dosyası güncelleniyor...")
with open("main.py", "w") as f:
    f.write(MAIN_CODE)
print("✅ main.py güncellendi.")
print("\n🎉 HAZIR! Şimdi 'python main.py' yazıp sonucu gör!")