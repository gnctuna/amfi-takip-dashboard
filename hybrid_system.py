import cv2
import pandas as pd
import streamlit as st
from ultralytics import YOLO
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import time
import sys

# 1. BAĞLANTI AYARLARI
# .streamlit/secrets.toml dosyasındaki linki kullanır
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. MODEL VE KAMERA AYARLARI
# Sabancı'daki projen için gizlilik odaklı YOLOv8n (en hafif) modelini kullanıyoruz
model = YOLO('yolov8n.pt') 

# Windows laptop kamerası genelde 0'dır. Mac'te 1 kullanmıştık.
# Eğer görüntü gelmezse aşağıdaki 0'ı 1 yapabilirsin.
CAMERA_INDEX = 0 

def save_to_cloud(count, status, mode_name):
    """Veriyi Google Sheets'e kaydeder ve 1000 satır limitini korur."""
    try:
        # Mevcut veriyi çek (Sheet1 sayfasından)
        existing_df = conn.read(worksheet="Sheet1")
        
        # Yeni veri satırını hazırla
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": int(count),
            "status": status,
            "mode": mode_name
        }])
        
        # Verileri birleştir ve son 1000 tanesini tut (Hafıza yönetimi)
        updated_df = pd.concat([existing_df, new_row], ignore_index=True)
        if len(updated_df) > 1000:
            updated_df = updated_df.tail(1000)
            
        # Google Sheets'e yaz
        conn.update(worksheet="Sheet1", data=updated_df)
        print(f"✅ Buluta Kaydedildi: {count} kişi ({mode_name} modu)")
    except Exception as e:
        print(f"❌ Kayıt Hatası: {e}")

def run_system(mode):
    cap = cv2.VideoCapture(CAMERA_INDEX)
    
    if not cap.isOpened():
        print("Hata: Kamera açılamadı! CAMERA_INDEX değerini 0 veya 1 olarak değiştirin.")
        return

    print(f"Sistem Başlatıldı: {mode} modunda çalışıyor...")
    last_save_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # AI Tespiti (Sadece 'person' sınıfı: id=0)
            results = model(frame, classes=[0], conf=0.4, verbose=False)
            count = len(results[0].boxes)
            status = "Dolu" if count > 0 else "Bos"

            # Görüntü üzerine bilgi yaz (Gizlilik için sadece sayı gösteriyoruz)
            cv2.putText(frame, f"Mod: {mode} | Kisi: {count}", (20, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Görüntüyü göster
            cv2.imshow("PrivacyOccupancyAI - Monitor", frame)

            # KAYIT MANTIĞI
            current_time = time.time()
            
            if mode == "SINIF":
                # Sınıf modunda her 30 saniyede bir buluta veri gönder
                if current_time - last_save_time > 30:
                    save_to_cloud(count, status, "SINIF")
                    last_save_time = current_time
            
            elif mode == "AMFI":
                # Amfi modunda her 5 dakikada bir (300 sn) kontrol et
                if current_time - last_save_time > 300:
                    save_to_cloud(count, status, "AMFI")
                    last_save_time = current_time

            # 'q' tuşuna basınca kapat
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # Terminalden gelen modu oku (SINIF veya AMFI)
    selected_mode = sys.argv[1] if len(sys.argv) > 1 else "SINIF"
    run_system(selected_mode)