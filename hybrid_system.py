import cv2
from ultralytics import YOLO
import gspread
from google.oauth2.service_account import Credentials
import time
import sys
from datetime import datetime

# --- GENEL AYARLAR ---
# Google Sheets Kimlik Dosyası
SERVICE_ACCOUNT_FILE = 'secrets.json'
SHEET_ID = '1YgVkVyMa_TbhgccfUMsfFtbtKrS5glorha1rGHMK1Kk' # Senin Sheet ID'n

MIN_CONFIDENCE = 0.50  # %50 Güven Eşiği

# SINIF MODU AYARLARI (Canlı Yayın)
STABILITY_FRAMES = 5       # Sayının değişmesi için kaç kare aynı kalmalı?
DATA_UPLOAD_INTERVAL = 10  # Google Sheets'e kaç saniyede bir yazsın? (Çok sık yazarsa Google engeller)

# AMFİ MODU AYARLARI (Snapshot)
AMFI_INTERVAL = 300        # 5 Dakika (Test için bunu düşürebilirsin)

def connect_gsheets():
    """Google Sheets Bağlantısını Kurar"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        print("✅ Google Sheets Bağlantısı Başarılı!")
        return sheet
    except Exception as e:
        print(f"❌ Google Sheets Bağlantı Hatası: {e}")
        return None

def save_to_cloud(sheet, count, status, mode):
    """Veriyi Google Sheets'e Ekler"""
    if sheet is None: return
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, int(count), status, mode])
        print(f"☁️  Buluta Yazıldı: {count} Kişi | Mod: {mode}")
    except Exception as e:
        print(f"⚠️ Bulut Yazma Hatası: {e}")

def open_camera():
    """Mac için Akıllı Kamera Açıcı"""
    print("📷 Kamera aranıyor...")
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        print("✅ Kamera (Index 0) başarıyla açıldı.")
        return cap
    
    print("⚠️ Index 0 başarısız, Index 1 deneniyor...")
    cap = cv2.VideoCapture(1)
    if cap.isOpened():
        print("✅ Kamera (Index 1) başarıyla açıldı.")
        return cap
        
    print("❌ HATA: Hiçbir kamera açılamadı!")
    return None

def main():
    # Mod Seçimi (Komut satırından veya varsayılan)
    if len(sys.argv) > 1:
        SCENARIO = sys.argv[1].upper()
    else:
        SCENARIO = "SINIF"

    print(f"🚀 SİSTEM BAŞLATILIYOR: {SCENARIO} MODU")
    
    # Google Bağlantısını Başlat
    sheet = connect_gsheets()

    if SCENARIO == "AMFI":
        model_name = "yolov8x.pt" 
        print(f"📸 Mod: SNAPSHOT (Her {AMFI_INTERVAL} saniyede bir foto)")
    elif SCENARIO == "SINIF":
        model_name = "yolov8n.pt" # Hız için Nano model
        print(f"🎥 Mod: CANLI TAKİP (Stabilizasyon Aktif)")
    else:
        return

    print("⏳ Model yükleniyor...")
    model = YOLO(model_name)
    
    # ==========================================
    # SENARYO 1: AMFİ (SNAPSHOT / ARALIKLI)
    # ==========================================
    if SCENARIO == "AMFI":
        while True:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Kamera açılıyor (Snapshot)...")
            
            cap = open_camera()
            if cap is None: break 
            
            # Isınma turları (Kamera ışık ayarını yapsın diye)
            cap.set(3, 1280)
            cap.set(4, 720)
            for _ in range(15): cap.read()
                
            success, frame = cap.read()
            cap.release() # Fotoğrafı aldık, kamerayı hemen kapat (Privacy)
            
            if success:
                print("🧠 Analiz ediliyor...")
                results = model.predict(frame, classes=0, conf=MIN_CONFIDENCE, verbose=False)
                count = len(results[0].boxes)
                status = "Kalabalik" if count > 20 else "Normal"
                
                print(f"✅ Sonuç: {count} Kişi")
                
                # --- BULUTA GÖNDER ---
                save_to_cloud(sheet, count, status, "AMFI_SNAPSHOT")

                # --- GÖRSELLEŞTİRME (Ekranda gösterip bekletme) ---
                annotated_frame = results[0].plot()
                timestamp = datetime.now().strftime('%H:%M:%S')
                cv2.putText(annotated_frame, f"SON DURUM: {timestamp}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(annotated_frame, f"Kisi Sayisi: {count}", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.putText(annotated_frame, f"Siradaki cekim: {AMFI_INTERVAL}s sonra...", (20, 680), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                
                cv2.imshow("PrivacyOccupancyAI - AMFI MODU", annotated_frame)
            else:
                print("❌ Görüntü alınamadı!")
            
            # --- AKILLI BEKLEME DÖNGÜSÜ ---
            # Ekranın donmaması için cv2.waitKey ile bekliyoruz
            print(f"💤 Bekleme modu ({AMFI_INTERVAL}s)...")
            start_wait = time.time()
            while (time.time() - start_wait) < AMFI_INTERVAL:
                if cv2.waitKey(100) & 0xFF == ord('q'):
                    print("Program kapatılıyor...")
                    sys.exit()

    # ==========================================
    # SENARYO 2: SINIF (CANLI / STABİLİTE)
    # ==========================================
    elif SCENARIO == "SINIF":
        cap = open_camera()
        if cap is None: return

        cap.set(3, 640)
        cap.set(4, 480)
        print("🎥 Canlı yayın başladı.")
        
        last_upload_time = 0 
        official_count = 0       
        candidate_count = -1     
        frame_streak = 0        

        while True:
            success, frame = cap.read()
            if not success: break
            
            # Takip Modu (Track) - İnsanları ID ile takip eder
            results = model.track(frame, persist=True, classes=0, conf=MIN_CONFIDENCE, verbose=False)
            
            # --- STABİLİTE ALGORİTMASI ---
            # Anlık titremeleri (bir görünüp bir kaybolanları) engeller
            raw_count = 0
            if results[0].boxes.id is not None:
                raw_count = len(results[0].boxes.id)
            
            if raw_count == candidate_count:
                frame_streak += 1
            else:
                candidate_count = raw_count
                frame_streak = 0
            
            if frame_streak >= STABILITY_FRAMES:
                official_count = candidate_count
                if frame_streak > 20: frame_streak = 20

            # --- GÖRSELLEŞTİRME ---
            annotated_frame = results[0].plot()
            cv2.rectangle(annotated_frame, (10, 10), (300, 80), (0,0,0), -1) # Arka plan siyah kutu
            cv2.putText(annotated_frame, f"Kisi: {official_count}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,255,0), 3)
            
            cv2.imshow("PrivacyOccupancyAI - SINIF MODU", annotated_frame)
            
            # --- BULUTA GÖNDERİM ---
            current_time = time.time()
            if current_time - last_upload_time > DATA_UPLOAD_INTERVAL:
                status = "Kalabalik" if official_count > 10 else "Normal"
                save_to_cloud(sheet, official_count, status, "SINIF_LIVE")
                last_upload_time = current_time
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()