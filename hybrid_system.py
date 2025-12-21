import cv2
from ultralytics import YOLO
import gspread
from google.oauth2.service_account import Credentials
import time
import sys
from datetime import datetime

# --- GENEL AYARLAR ---
SERVICE_ACCOUNT_FILE = 'secrets.json'
SHEET_ID = '1YgVkVyMa_TbhgccfUMsfFtbtKrS5glorha1rGHMK1Kk' 

MIN_CONFIDENCE = 0.50  
STABILITY_FRAMES = 5       
DATA_UPLOAD_INTERVAL = 10  
AMFI_INTERVAL = 300        

def connect_gsheets():
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
    if sheet is None: return
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, int(count), status, mode])
        print(f"☁️  Buluta Yazıldı: {count} Kişi | Mod: {mode}")
    except Exception as e:
        print(f"⚠️ Bulut Yazma Hatası: {e}")

def open_camera():
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
    if len(sys.argv) > 1:
        SCENARIO = sys.argv[1].upper()
    else:
        SCENARIO = "SINIF"

    print(f"🚀 SİSTEM BAŞLATILIYOR: {SCENARIO} MODU")
    
    sheet = connect_gsheets()
    
    # --- HAFIZA DEĞİŞKENİ ---
    # İlk başta imkansız bir sayı (-1) veriyoruz ki ilk veriyi kesin göndersin.
    last_sent_count = -1 

    if SCENARIO == "AMFI":
        model_name = "yolov8x.pt" 
        print(f"📸 Mod: SNAPSHOT (Her {AMFI_INTERVAL} saniyede bir foto)")
    elif SCENARIO == "SINIF":
        model_name = "yolov8n.pt" 
        print(f"🎥 Mod: CANLI TAKİP (Sadece değişimde veri gider)")
    else:
        return

    print("⏳ Model yükleniyor...")
    model = YOLO(model_name)
    
    # ==========================================
    # SENARYO 1: AMFİ (SNAPSHOT / ARALIKLI)
    # ==========================================
    if SCENARIO == "AMFI":
        while True:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Kamera açılıyor...")
            cap = open_camera()
            if cap is None: break 
            
            cap.set(3, 1280)
            cap.set(4, 720)
            for _ in range(15): cap.read()
                
            success, frame = cap.read()
            cap.release()
            
            if success:
                results = model.predict(frame, classes=0, conf=MIN_CONFIDENCE, verbose=False)
                count = len(results[0].boxes)
                status = "Kalabalik" if count > 20 else "Normal"
                
                print(f"✅ Tespit: {count} Kişi")
                
                # --- SADECE DEĞİŞİRSE GÖNDER ---
                if count != last_sent_count:
                    save_to_cloud(sheet, count, status, "AMFI_SNAPSHOT")
                    last_sent_count = count # Hafızayı güncelle
                else:
                    print("💤 Sayı değişmedi, veri gönderilmedi.")

                # Görselleştirme
                annotated_frame = results[0].plot()
                cv2.imshow("AMFI MODU", annotated_frame)
            
            print(f"Bekleniyor ({AMFI_INTERVAL}s)...")
            start_wait = time.time()
            while (time.time() - start_wait) < AMFI_INTERVAL:
                if cv2.waitKey(100) & 0xFF == ord('q'):
                    sys.exit()

    # ==========================================
    # SENARYO 2: SINIF (CANLI / STABİLİTE)
    # ==========================================
    elif SCENARIO == "SINIF":
        cap = open_camera()
        if cap is None: return

        cap.set(3, 640)
        cap.set(4, 480)
        
        last_upload_time = 0 
        official_count = 0       
        candidate_count = -1     
        frame_streak = 0        

        while True:
            success, frame = cap.read()
            if not success: break
            
            results = model.track(frame, persist=True, classes=0, conf=MIN_CONFIDENCE, verbose=False)
            
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

            annotated_frame = results[0].plot()
            cv2.rectangle(annotated_frame, (10, 10), (350, 60), (0,0,0), -1)
            cv2.putText(annotated_frame, f"Kisi: {official_count}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,255,0), 2)
            
            cv2.imshow("SINIF MODU", annotated_frame)
            
            # --- ZAMANLAYICI + DEĞİŞİM KONTROLÜ ---
            current_time = time.time()
            if current_time - last_upload_time > DATA_UPLOAD_INTERVAL:
                
                # SADECE SAYI FARKLIYSA GÖNDER
                if official_count != last_sent_count:
                    status = "Kalabalik" if official_count > 10 else "Normal"
                    save_to_cloud(sheet, official_count, status, "SINIF_LIVE")
                    
                    last_sent_count = official_count # Yeni sayıyı hafızaya al
                    last_upload_time = current_time  # Süreyi sıfırla
                else:
                    # Değişiklik yoksa sadece ekrana bilgi ver, buluta gitme
                    print(f"💤 [{datetime.now().strftime('%H:%M:%S')}] Değişim yok ({official_count}), pas geçildi.")
                    last_upload_time = current_time # Süreyi yine de sıfırla ki 10sn sonra tekrar kontrol etsin

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()