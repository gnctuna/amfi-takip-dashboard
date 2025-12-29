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

# --- BU FONKSİYONU MAIN'İN ÜSTÜNE EKLEMEN GEREKİYORDU ---
def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = int(f.read()) / 1000.0
        return temp
    except:
        return 0.0
# --------------------------------------------------------

def main():
    # ==========================================
    # 🛠️ GENEL AYARLAR
    # ==========================================
    TEST_MODU = True   # True = Kaydeder, False = Siler
    # ==========================================

    print("🚀 Sistem Hazırlanıyor...")

    # 1. SENARYO VE MOD AYARLARI
    try:
        SCENARIO = sys.argv[1].upper()
    except:
        SCENARIO = "SINIF"

    # --- MODLARA GÖRE AYARLAR ---
    if SCENARIO == "AMFI":
        # AMFİ MODU: Large Model, Az Fotoğraf, Çok Bekleme
        model_name = 'yolo11l.pt'  # Large Model
        num_samples = 3            # 3 Fotoğraf
        sleep_time = 60            # 60 Saniye Dinlenme
        conf_rate = 0.50           # Geniş açı hassasiyeti
        print(f"🏟️ MOD: AMFİ (Model: LARGE | 3 Foto | 60sn | Geniş Açı)")
    
    else:
        # SINIF MODU: Medium Model, Çok Fotoğraf, Hızlı Bekleme
        model_name = 'yolo11m.pt'  # Medium Model
        num_samples = 5            # 5 Fotoğraf
        sleep_time = 30            # 30 Saniye Dinlenme
        conf_rate = 0.60           # Standart hassasiyet
        print(f"🏫 MOD: SINIF (Model: MEDIUM | 5 Foto | 30sn | Standart)")

    # ----------------------------------------------------

    if TEST_MODU and not os.path.exists("fotograflar"):
        os.makedirs("fotograflar")
    elif not TEST_MODU:
        print("🛡️ GİZLİLİK MODU AÇIK: Fotoğraflar silinecek.")

    print(f"🧠 Yapay Zeka Yükleniyor: {model_name} ...")
    model = YOLO(model_name)

    sheet = connect_gsheets()
    last_sent_count = -1

    print(f"✅ Sistem Hazır. Başlıyoruz...")

    while True:
        # CPU Sıcaklığı (Artık bu fonksiyon tanımlı olduğu için hata vermez)
        cpu_temp = get_cpu_temp()
        temp_icon = "🔥" if cpu_temp > 75 else "🌡️"
        temp_status = f"{temp_icon} {cpu_temp:.1f}°C"
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Döngü Başlıyor... ({temp_status})")

        # A) BAĞLANTI
        if sheet is None:
            print("🔄 İnternet bağlantısı tekrar deneniyor...")
            sheet = connect_gsheets()
        
        if sheet is not None:
            process_offline_queue(sheet)

        # B) FOTOĞRAF VE SAYIM
        samples = []
        
        print(f"📸 {num_samples} fotoğraf çekiliyor...")

        for i in range(num_samples):
            if TEST_MODU:
                dosya_adi = f"foto_{i+1}.jpg"
                foto_yolu = os.path.join("fotograflar", dosya_adi)
            else:
                foto_yolu = "gecici_foto.jpg"
            
            # Fotoğraf Çek
            os.system(f"rpicam-still -o {foto_yolu} -t 200 --width 1920 --height 1080 -n")
            
            frame = cv2.imread(foto_yolu)
            
            # Gizlilik: Okur okumaz sil (Test kapalıysa)
            if not TEST_MODU and os.path.exists(foto_yolu):
                os.remove(foto_yolu)
            
            if frame is not None:
                results = model.predict(frame, conf=conf_rate, classes=[0], verbose=False)
                count = len(results[0].boxes)
                
                # Test Modu: Kaydet
                if TEST_MODU:
                    cizimli_kare = results[0].plot()
                    cv2.imwrite(foto_yolu, cizimli_kare)
                    print(f"   ├─ [Kaydedildi]: {count} Kişi")
                else:
                    print(f"   ├─ [Gizli Analiz]: {count} Kişi")

                samples.append((count, results[0]))
            else:
                print(f"   ├─ ❌ Okunamadı")

        # C) SONUÇ
        if samples:
            samples.sort(key=lambda x: x[0])
            median_index = len(samples) // 2
            final_count, final_results = samples[median_index]
            
            cpu_temp_final = get_cpu_temp()
            status = "Kalabalik" if final_count > 20 else "Normal"
            mode_label = f"{SCENARIO}_DETAYLI"

            print(f"✅ SONUÇ: {final_count} Kişi | {status} | CPU: {cpu_temp_final:.1f}°C")

            # D) VERİ GÖNDERİMİ
            if final_count != last_sent_count:
                save_to_cloud(sheet, final_count, status, mode_label)
                last_sent_count = final_count
            else:
                print(f"💤 Sayı değişmedi.")
        
        else:
            print("❌ Hiçbir fotoğraf analiz edilemedi!")

        # E) BEKLEME
        print(f"⏳ Bekleniyor ({sleep_time} saniye)...")
        time.sleep(sleep_time)
if __name__ == "__main__":
    main()
