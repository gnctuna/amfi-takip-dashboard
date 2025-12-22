import cv2
from ultralytics import YOLO
import gspread
from google.oauth2.service_account import Credentials
import time
import sys
import numpy as np
from datetime import datetime

# --- AYARLAR ---
SERVICE_ACCOUNT_FILE = 'secrets.json'
SHEET_ID = '1YgVkVyMa_TbhgccfUMsfFtbtKrS5glorha1rGHMK1Kk' 

# Raspberry Pi 4/5 için modeller (Mac'te de çalışır)
MODEL_AMFI = "yolov8l.pt"  
MODEL_SINIF = "yolov8m.pt" 

CONFIDENCE_THRESHOLD = 0.40  
IOU_THRESHOLD = 0.50         

# ZAMANLAMA
INTERVAL_AMFI = 60   
INTERVAL_SINIF = 30  

def connect_gsheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        return sheet
    except Exception as e:
        print(f"❌ Sheet Hatası: {e}")
        return None

def save_to_cloud(sheet, count, status, mode):
    if sheet is None: return
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, int(count), status, mode])
        print(f"☁️  Buluta Gönderildi: {count} Kişi")
    except Exception as e:
        print(f"⚠️ Bulut Yazma Hatası: {e}")

def get_accurate_count(cap, model, num_samples=3):
    """
    Hem sayım yapar hem de Mac ekranında sonucu gösterir.
    """
    counts = []
    print("👀 Analiz yapılıyor (Ekrana bak)...")
    
    for i in range(num_samples):
        # Buffer temizle
        for _ in range(5): cap.read()
        success, frame = cap.read()
        
        if not success: continue

        # Tahmin yap
        results = model.predict(
            frame, 
            classes=0, 
            conf=CONFIDENCE_THRESHOLD, 
            iou=IOU_THRESHOLD, 
            verbose=False
        )
        
        # --- GÖRSELLEŞTİRME KISMI (BURAYI EKLEDIK) ---
        annotated_frame = results[0].plot() # Kutuları çiz
        
        # Ekrana bilgi yazısı ekle
        cnt = len(results[0].boxes)
        cv2.putText(annotated_frame, f"Ornek {i+1}/{num_samples} - Sayi: {cnt}", (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow("KAMERA TESTI (Kapatmak icin 'q' basma)", annotated_frame)
        
        # Fotoğrafı 2 saniye (2000ms) ekranda tut ki görebil
        cv2.waitKey(2000) 
        # ---------------------------------------------

        counts.append(cnt)
        print(f"   📸 Örnek {i+1}: {cnt} Kişi")
        
    # İşlem bitince pencereyi kapat
    cv2.destroyAllWindows() 

    if not counts: return 0
    return int(np.median(counts))

def main():
    if len(sys.argv) > 1:
        SCENARIO = sys.argv[1].upper()
    else:
        SCENARIO = "SINIF"

    print(f"🖥️ GÖRSEL TEST MODU: {SCENARIO}")
    
    sheet = connect_gsheets()
    last_sent_count = -1

    if SCENARIO == "AMFI":
        model_name = MODEL_AMFI
        sleep_time = INTERVAL_AMFI
    else:
        model_name = MODEL_SINIF
        sleep_time = INTERVAL_SINIF

    print(f"⏳ Model Yükleniyor ({model_name})...")
    try:
        model = YOLO(model_name)
    except Exception as e:
        print(f"❌ Hata: {e}")
        return

    while True:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Kamera açılıyor...")
        
        cap = cv2.VideoCapture(0)
        # Mac'te bazen Index 1 gerekebilir
        if not cap.isOpened(): cap = cv2.VideoCapture(1)
            
        if cap and cap.isOpened():
            cap.set(3, 1280)
            cap.set(4, 720)
            
            final_count = get_accurate_count(cap, model, num_samples=3)
            
            cap.release()
            
            status = "Kalabalik" if final_count > 20 else "Normal"
            mode_label = f"{SCENARIO}_ACCURATE"
            
            print(f"✅ SONUÇ (Medyan): {final_count} Kişi")

            if final_count != last_sent_count:
                save_to_cloud(sheet, final_count, status, mode_label)
                last_sent_count = final_count
            else:
                print("💤 Sayı değişmedi, veri gitmiyor.")
                
        else:
            print("❌ Kamera bulunamadı!")

        print(f"⏳ Bekleniyor ({sleep_time} saniye)...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()