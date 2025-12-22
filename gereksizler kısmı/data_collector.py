import cv2
import time
import os

# Kayıt Yeri
IMAGE_PATH = "dataset/images"

def main():
    cap = cv2.VideoCapture(0) # Mac kamerası
    
    print(f"--- VERI TOPLAYICI BASLATILDI ---")
    print(f"Resimler '{IMAGE_PATH}' klasorune kaydedilecek.")
    print("Mod: Her 3 saniyede bir otomatik ceker.")
    print("Cikis icin 'q' tusuna bas.")
    
    last_time = time.time()
    count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        # Görüntüyü göster
        cv2.imshow("Veri Toplama Ekrani", frame)
        
        # 3 saniye geçti mi kontrol et
        if time.time() - last_time > 3:
            # Dosya ismini benzersiz yap (zaman damgası ile)
            filename = f"{IMAGE_PATH}/img_{int(time.time())}.jpg"
            cv2.imwrite(filename, frame)
            
            print(f"Kaydedildi [{count+1}]: {filename}")
            last_time = time.time()
            count += 1
            
        # Çıkış
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()