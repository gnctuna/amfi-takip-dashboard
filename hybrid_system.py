import cv2
import pandas as pd
import streamlit as st
from ultralytics import YOLO
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import time
import sys

# 1. BULUT BAĞLANTISI
# Bu satır .streamlit/secrets.toml dosyasındaki linki kullanır
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. MODEL VE KAMERA AYARLARI
# İsteğin üzerine YOLOv8x (en hassas model) kullanıyoruz
model = YOLO('yolov8x.pt') 
CAMERA_INDEX = 0 

def save_to_cloud(count, status, mode_name):
    """Veriyi Google Sheets'e ekler."""
    try:
        # Mevcut veriyi oku (Sekme adı: Sheet1)
        existing_df = conn.read(worksheet="Sheet1")
        
        # Yeni satırı hazırla
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": int(count),
            "status": status,
            "mode": mode_name
        }])
        
        # Verileri birleştir ve en güncel 1000 kaydı tut
        updated_df = pd.concat([existing_df, new_row], ignore_index=True).tail(1000)
        
        # Tabloyu güncelle
        conn.update(worksheet="Sheet1", data=updated_df)
        print(f"✅ Buluta Kaydedildi: {count} kişi ({status})")
    except Exception as e:
        print(f"❌ Kayıt Hatası (Link veya Yetki Sorunu): {e}")

def run_system(mode):
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("⚠️ HATA: Kamera açılamadı!")
        return

    print(f"🚀 Sistem Başlatıldı: {mode} modunda çalışıyor...")
    last_save_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret: break

            # AI Tespiti (Sadece insan sınıfı: 0)
            results = model(frame, classes=[0], conf=0.4, verbose=False)
            boxes = results[0].boxes
            count = len(boxes)
            status = "Dolu" if count > 0 else "Bos"

            # MAVİ KUTU ÇİZİMİ (İsteğin üzerine)
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2) # Mavi: (255,0,0)
                cv2.putText(frame, "Kisi", (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

            # Ekran Bilgileri
            cv2.putText(frame, f"Mod: {mode} | Kisi: {count}", (20, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("PrivacyOccupancyAI - Canli Takip", frame)

            # Veri Gönderim Periyodu (SINIF modu: 30 sn, AMFI modu: 5 dk)
            current_time = time.time()
            wait_time = 30 if mode == "SINIF" else 300
            if current_time - last_save_time > wait_time:
                save_to_cloud(count, status, mode)
                last_save_time = current_time

            if cv2.waitKey(1) & 0xFF == ord('q'): break
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # Komut satırı argümanı (Varsayılan: SINIF)
    selected_mode = sys.argv[1] if len(sys.argv) > 1 else "SINIF"
    run_system(selected_mode)