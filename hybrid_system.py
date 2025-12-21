import cv2
import pandas as pd
import streamlit as st
from ultralytics import YOLO
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import time
import sys

# 1. BAĞLANTI AYARLARI
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. MODEL VE KAMERA AYARLARI
# Not: Eğer bilgisayarın çok kasarsa burayı 'yolov8n.pt' yapabilirsin
model = YOLO('yolov8x.pt') 
CAMERA_INDEX = 0 # Eğer kamera açılmazsa burayı 1 yapmayı dene

def save_to_cloud(count, status, mode_name):
    try:
        existing_df = conn.read(worksheet="Sheet1")
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": int(count),
            "status": status,
            "mode": mode_name
        }])
        updated_df = pd.concat([existing_df, new_row], ignore_index=True).tail(1000)
        conn.update(worksheet="Sheet1", data=updated_df)
        print(f"✅ Buluta Kaydedildi: {count} kişi")
    except Exception as e:
        print(f"❌ Bulut Kayıt Hatası (Secrets linkini kontrol et!): {e}")

def run_system(mode):
    cap = cv2.VideoCapture(CAMERA_INDEX)
    
    # KAMERA KONTROLÜ
    if not cap.isOpened():
        print(f"⚠️ HATA: Kamera (Index {CAMERA_INDEX}) açılmadı! Başka uygulama kamerayı kullanıyor olabilir.")
        return

    print(f"Sistem Başlatıldı: {mode} modunda çalışıyor...")
    last_save_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠️ Kameradan görüntü alınamıyor, işlem durduruldu.")
                break

            results = model(frame, classes=[0], conf=0.4, verbose=False)
            boxes = results[0].boxes
            count = len(boxes)
            status = "Dolu" if count > 0 else "Bos"

            # Mavi Kutuları Çiz (İsteğin üzerine geri geldi)
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                cv2.putText(frame, "Kisi", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

            cv2.putText(frame, f"Mod: {mode} | Kişi: {count}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("PrivacyOccupancyAI - Monitor", frame)

            # Kayıt periyotları (Test için SINIF modunda 10 saniye yaptım)
            current_time = time.time()
            wait_time = 10 if mode == "SINIF" else 300 
            if current_time - last_save_time > wait_time:
                save_to_cloud(count, status, mode)
                last_save_time = current_time

            if cv2.waitKey(1) & 0xFF == ord('q'): break
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    selected_mode = sys.argv[1] if len(sys.argv) > 1 else "SINIF"
    run_system(selected_mode)