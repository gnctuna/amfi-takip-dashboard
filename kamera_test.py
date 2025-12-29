import cv2
import time

print("Kamera başlatılıyor (V4L2 - Pi 5 Modu)...")
# Pi 5 için özel V4L2 ayarı
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)

# Çözünürlüğü sabitle
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# Kameranın ışık ayarı yapması için 2 saniye bekle
time.sleep(2)

if not cap.isOpened():
    print("HATA: Kamera açılamadı!")
else:
    ret, frame = cap.read()
    if ret:
        print("BAŞARILI: Görüntü yakalandı!")
        cv2.imwrite("son_kontrol.jpg", frame)
        print("Resim 'son_kontrol.jpg' olarak kaydedildi.")
    else:
        print("HATA: Kamera açık ama görüntü simsiyah/boş geldi.")

cap.release()
