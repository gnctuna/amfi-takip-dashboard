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
#               AYARLAR
# ==========================================
SERVICE_ACCOUNT_FILE = 'secrets.json'
SHEET_ID = '1YgVkVyMa_TbhgccfUMsfFtbtKrS5glorha1rGHMK1Kk'
BACKUP_FILE = 'offline_backup.csv'

# Raspberry Pi için Optimize Edilmiş Modeller
MODEL_AMFI = "yolov8l.pt"  # Large (Çok Hassas)
MODEL_SINIF = "yolov8m.pt" # Medium (Dengeli)

# Algılama Hassasiyeti
CONFIDENCE_THRESHOLD = 0.40
IOU_THRESHOLD = 0.50

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
                # Veriyi hazırla ve gönder
                row = [data[0], int(data[1]), data[2], data[3]]
                sheet.append_row(row)
                print(f"   ⬆️ Eski veri yüklendi: {row[0]} - {row[1]} Kişi")
                time.sleep(1) # API limitine takılmamak için bekle
        
        # İşlem bitince dosyayı sil
        os.remove(BACKUP_FILE)
        print("✅ Tüm yedekler başarıyla yüklendi ve temizlendi.")
        
    except Exception as e:
        print(f"⚠️ Yedek yükleme sırasında hata: {e}")

def save_to_cloud(sheet, count, status, mode):
    """Veriyi buluta atmayı dener, olmazsa yedeğe atar."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Eğer sheet bağlantısı kopuksa direkt yedekle
    if sheet is None:
        save_local_backup(timestamp, count, status, mode)
        return

    try:
        sheet.append_row([timestamp, int(count), status, mode])
        print(f"☁️  Buluta Gönderildi: {count} Kişi")
    except Exception as e:
        print(f"⚠️ Bulut Yazma Hatası: {e}")
        save_local_backup(timestamp, count, status, mode)

def get_accurate_count(cap, model, num_samples=3):
    """
    3 kez fotoğraf çeker, analiz eder ve medyanını alır.
    Mac'te pencere açar, Pi'de (Headless) hata vermeden devam eder.
    """
    counts = []
    print("👀 Analiz yapılıyor (3 Örnek)...")
    
    for i in range(num_samples):
        # Buffer temizle (Eski kare kalmasın)
        for _ in range(5): cap.read()
        success, frame = cap.read()
        
        if not success: continue

        # Tahmin Yap
        results = model.predict(frame, classes=0, conf=CONFIDENCE_THRESHOLD, iou=IOU_THRESHOLD, verbose=False)
        cnt = len(results[0].boxes)
        
        # --- GÖRSELLEŞTİRME (OPSİYONEL PENCERE) ---
        try:
            annotated_frame = results[0].plot()
            cv2.putText(annotated_frame, f"Ornek {i+1}/{num_samples} - Sayi: {cnt}", (20, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("KAMERA TESTI (Mac/PC)", annotated_frame)
            cv2.waitKey(2000) # 2 saniye ekranda tut
        except:
            # Raspberry Pi monitörsüz çalışıyorsa burayı sessizce geç
            pass
        # ------------------------------------------

        counts.append(cnt)
        print(f"   📸 Örnek {i+1}: {cnt} Kişi")
        
    # Pencereleri kapat (Hata verirse geç)
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

    print(f"🚀 SİSTEM BAŞLATILIYOR: {SCENARIO} MODU")
    print(f"🛡️  Offline Yedekleme: AKTİF")

    # Ayarları Yükle
    if SCENARIO == "AMFI":
        model_name = MODEL_AMFI
        sleep_time = INTERVAL_AMFI
    else:
        model_name = MODEL_SINIF
        sleep_time = INTERVAL_SINIF

    # Modeli Hazırla
    print(f"⏳ Yapay Zeka Modeli Yükleniyor ({model_name})...")
    try:
        model = YOLO(model_name)
    except Exception as e:
        print(f"❌ Kritik Hata (Model Yüklenemedi): {e}")
        return

    # Başlangıç Bağlantısı
    sheet = connect_gsheets()
    last_sent_count = -1

    while True:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Yeni Döngü Başlıyor...")

        # 1. BAĞLANTI KONTROLÜ VE ESKİ YEDEKLER
        if sheet is None:
            print("🔄 İnternet bağlantısı tekrar deneniyor...")
            sheet = connect_gsheets()
        
        # Bağlantı varsa, önce birikmiş borçları öde (Dosyaları yükle)
        if sheet is not None:
            process_offline_queue(sheet)

        # 2. KAMERA VE SAYIM İŞLEMİ
        cap = cv2.VideoCapture(0)
        if not cap.isOpened(): cap = cv2.VideoCapture(1) # Mac için alternatif port

        if cap and cap.isOpened():
            # Yüksek çözünürlük ayarla
            cap.set(3, 1280)
            cap.set(4, 720)
            
            # 3 Fotoğraflı Hassas Sayım
            final_count = get_accurate_count(cap, model, num_samples=3)
            cap.release() # Kamerayı kapat (Isınmayı önle)
            
            status = "Kalabalik" if final_count > 20 else "Normal"
            mode_label = f"{SCENARIO}_AUTO"
            
            print(f"✅ FİNAL SONUÇ: {final_count} Kişi")

            # 3. VERİ GÖNDERİM KARARI
            if final_count != last_sent_count:
                save_to_cloud(sheet, final_count, status, mode_label)
                last_sent_count = final_count
            else:
                print("💤 Sayı değişmedi, veri gönderilmiyor.")

        else:
            print("❌ Kamera açılamadı! Kabloyu kontrol et.")

        # 4. BEKLEME (SOĞUMA) SÜRESİ
        print(f"⏳ Bekleniyor ({sleep_time} saniye)...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()