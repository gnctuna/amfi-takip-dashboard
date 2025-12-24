import cv2
from ultralytics import YOLO
import gspread
from google.oauth2.service_account import Credentials
import time
import sys
import numpy as np
import os
from datetime import datetime

# ==========================================
#      AYARLAR (YÜKSEK DOĞRULUK MODU)
# ==========================================
SERVICE_ACCOUNT_FILE = 'secrets.json'
SHEET_ID = '1YgVkVyMa_TbhgccfUMsfFtbtKrS5glorha1rGHMK1Kk'
BACKUP_FILE = 'offline_backup.csv'

# 🔥 MODEL SEÇİMİ (YOLO11)
# Raspberry Pi 5 için optimize edilmiş en yeni modeller
MODEL_AMFI = "yolo11l.pt"  # Large (Amfi için maksimum detay)
MODEL_SINIF = "yolo11m.pt" # Medium (Sınıf için ideal denge)

# 🎯 HASSASİYET AYARLARI
# %60 altındaki tahminleri "İnsan" sayma (Yanlış alarmları önler)
CONFIDENCE_THRESHOLD = 0.60  
# Kutucukların birbirine karışmasını engeller (Daha iyi ayırır)
IOU_THRESHOLD = 0.45
# Analiz Çözünürlüğü (Yüksek kalite = Uzaktakileri daha iyi görür)
IMAGE_SIZE = 1280

# Bekleme Süreleri (Saniye)
INTERVAL_AMFI = 60
INTERVAL_SINIF = 30
# ==========================================

def connect_gsheets():
    """Google Sheets bağlantısını kurar. İnternet yoksa None döner."""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        return sheet
    except Exception:
        return None

def save_local_backup(timestamp, count, status, mode):
    """İnternet yoksa veriyi CSV dosyasına kaydeder."""
    try:
        with open(BACKUP_FILE, 'a') as f:
            line = f"{timestamp},{count},{status},{mode}\n"
            f.write(line)
        print(f"💾 İnternet Yok! Veri yerel dosyaya yedeklendi: {count} Kişi")
    except Exception as e:
        print(f"❌ Yedekleme Hatası: {e}")

def process_offline_queue(sheet):
    """İnternet geri geldiğinde, birikmiş yedek dosyasını buluta yükler."""
    if not os.path.exists(BACKUP_FILE):
        return

    print("🔄 İnternet geri geldi! Geçmiş yedekler yükleniyor...")
    try:
        with open(BACKUP_FILE, 'r') as f:
            lines = f.readlines()
        
        for line in lines:
            data = line.strip().split(',')
            if len(data) == 4:
                row = [data[0], int(data[1]), data[2], data[3]]
                sheet.append_row(row)
                print(f"   ⬆️ Eski veri yüklendi: {row[0]}")
                time.sleep(1) # API limitine takılmamak için bekle
        
        os.remove(BACKUP_FILE)
        print("✅ Tüm yedekler başarıyla yüklendi ve temizlendi.")
        
    except Exception as e:
        print(f"⚠️ Yedek yükleme sırasında hata: {e}")

def save_to_cloud(sheet, count, status, mode):
    """Veriyi buluta atmayı dener, olmazsa yedeğe atar."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if sheet is None:
        save_local_backup(timestamp, count, status, mode)
        return

    try:
        sheet.append_row([timestamp, int(count), status, mode])
        print(f"☁️  Buluta Gönderildi: {count} Kişi")
    except Exception as e:
        print(f"⚠️ Bulut Yazma Hatası: {e}")
        save_local_backup(timestamp, count, status, mode)

def get_accurate_count(cap, model, mode_name, num_samples=3):
    """
    TTA (Augmentation) açık, yüksek çözünürlüklü analiz yapar.
    Pi 5'te biraz daha yavaş çalışır ama çok daha doğru sonuç verir.
    """
    counts = []
    print(f"👀 {mode_name} Modu: Derinlemesine Analiz (TTA Aktif - %{int(CONFIDENCE_THRESHOLD*100)}+)...")
    
    for i in range(num_samples):
        # Buffer temizle (Kameradaki eski görüntüyü at)
        for _ in range(5): cap.read()
        success, frame = cap.read()
        
        if not success: continue

        # --- YÜKSEK DOĞRULUK TAHMİNİ ---
        # augment=True: Fotoğrafı çevirip tekrar bakar.
        # imgsz=IMAGE_SIZE: Büyük boyutta işler.
        results = model.predict(
            frame, 
            classes=0, 
            conf=CONFIDENCE_THRESHOLD, 
            iou=IOU_THRESHOLD, 
            imgsz=IMAGE_SIZE, 
            augment=True, 
            verbose=False
        )
        # -------------------------------
        
        cnt = len(results[0].boxes)
        
        # Görselleştirme (Pi'de ekran yoksa hata vermez)
        try:
            annotated_frame = results[0].plot()
            info_text = f"MOD: {mode_name} (v11-Pro) | Ornek {i+1}/{num_samples} | Sayi: {cnt}"
            
            # Yazıyı ekrana bas
            cv2.putText(annotated_frame, info_text, (20, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Pencereyi göster
            cv2.imshow(f"KAMERA - {mode_name}", annotated_frame)
            cv2.waitKey(2000) 
        except:
            pass

        counts.append(cnt)
        print(f"   📸 Örnek {i+1}: {cnt} Kişi")
        
    # Pencereleri temizle
    try:
        cv2.destroyAllWindows()
    except:
        pass

    if not counts: return 0
    return int(np.median(counts))

def main():
    # Komut satırından mod seçimi (Varsayılan: SINIF)
    if len(sys.argv) > 1:
        SCENARIO = sys.argv[1].upper()
    else:
        SCENARIO = "SINIF"

    print(f"🚀 SİSTEM BAŞLATILIYOR: {SCENARIO} MODU (PRO VERSİYON)")
    print(f"🛡️  Offline Yedekleme: AKTİF")
    print(f"🧠  Yapay Zeka: YOLO11 (Confidence > {CONFIDENCE_THRESHOLD})")

    # Ayarları Yükle
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
        print(f"❌ Model Hatası: {e}")
        print("💡 İPUCU: 'pip install ultralytics --upgrade' komutunu çalıştırdın mı?")
        return

    # Başlangıç Bağlantısı
    sheet = connect_gsheets()
    last_sent_count = -1

    while True:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Döngü Başlıyor...")

        # 1. BAĞLANTI KONTROLÜ
        if sheet is None:
            print("🔄 İnternet bağlantısı tekrar deneniyor...")
            sheet = connect_gsheets()
        
        if sheet is not None:
            process_offline_queue(sheet)

        # 2. KAMERA VE SAYIM
        cap = cv2.VideoCapture(0)
        # Kamera 0 açılmazsa 1'i dene (Mac veya Harici Kamera için)
        if not cap.isOpened(): cap = cv2.VideoCapture(1) 

        if cap and cap.isOpened():
            # Kamerayı maksimum çözünürlüğe zorla
            cap.set(3, 1280)
            cap.set(4, 720)
            
            final_count = get_accurate_count(cap, model, SCENARIO, num_samples=3)
            cap.release()
            
            status = "Kalabalik" if final_count > 20 else "Normal"
            mode_label = f"{SCENARIO}_PRO" # Google Sheet'te 'PRO' etiketiyle göreceksin
            
            print(f"✅ FİNAL SONUÇ: {final_count} Kişi")

            # 3. VERİ GÖNDERİMİ
            if final_count != last_sent_count:
                save_to_cloud(sheet, final_count, status, mode_label)
                last_sent_count = final_count
            else:
                print("💤 Sayı değişmedi, veri gönderilmiyor.")

        else:
            print("❌ Kamera açılamadı! Kabloyu kontrol et.")

        print(f"⏳ Bekleniyor ({sleep_time} saniye)...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()