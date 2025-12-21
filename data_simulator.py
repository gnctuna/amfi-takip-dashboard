import gspread
from google.oauth2.service_account import Credentials
import time
import random
from datetime import datetime

# --- AYARLAR ---
SERVICE_ACCOUNT_FILE = 'secrets.json'
SHEET_ID = '1YgVkVyMa_TbhgccfUMsfFtbtKrS5glorha1rGHMK1Kk' # Senin Sheet ID'n

# DİKKAT: Google Sheets'in dakikalık yazma sınırı vardır. 
# Çok hızlı gönderirsen "Quota Exceeded" hatası alırsın. 
# İdeal hız: 5 saniye ve üzeri.
GONDERME_HIZI = 5 

def connect_gsheets():
    """Google Sheets'e Bağlan"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        print("✅ Google Sheets'e Bağlanıldı!")
        return sheet
    except Exception as e:
        print(f"❌ Bağlantı Hatası: {e}")
        return None

def main():
    print(f"🧪 SİMÜLATÖR BAŞLATILDI (Hız: Her {GONDERME_HIZI} saniyede bir veri)")
    
    sheet = connect_gsheets()
    if sheet is None: return

    current_count = 10
    current_mode = "SINIF_LIVE" 
    
    while True:
        try:
            # --- 1. SENARYO DEĞİŞİMİ (%20 Şans) ---
            if random.random() < 0.20:
                scenario_roll = random.random()
                
                if scenario_roll < 0.33:
                    current_count = random.randint(0, 5)
                    current_mode = "SINIF_LIVE"
                    print("\n☕ SENARYO: Teneffüs / Boş Sınıf")
                    
                elif scenario_roll < 0.66:
                    current_count = random.randint(25, 45)
                    current_mode = "SINIF_LIVE"
                    print("\n🏫 SENARYO: Sınıf Dersi")
                    
                else:
                    current_count = random.randint(80, 150)
                    current_mode = "AMFI_SNAPSHOT"
                    print("\n🚀 SENARYO: Amfi Konferansı")

            # --- 2. UFAK DALGALANMALAR ---
            # Sayı sabit kalmasın, canlı gibi 1-2 kişi girip çıksın
            change = random.randint(-2, 2)
            current_count += change
            if current_count < 0: current_count = 0
            
            # --- 3. DURUM BELİRLEME ---
            limit = 50 if current_mode == "AMFI_SNAPSHOT" else 20
            status = "Kalabalik" if current_count > limit else "Normal"
            
            # --- 4. GOOGLE SHEETS'E YAZMA ---
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row = [timestamp, current_count, status, current_mode]
            
            sheet.append_row(row)
            print(f"📤 [Simülasyon] Yazıldı: {current_count} Kişi | {status} | Mod: {current_mode}")
            
            # Bekleme
            time.sleep(GONDERME_HIZI)

        except Exception as e:
            print(f"⚠️ Bir hata oldu (Muhtemelen internet kesildi): {e}")
            print("🔄 Tekrar bağlanılıyor...")
            time.sleep(5)
            sheet = connect_gsheets() # Bağlantıyı tazele

if __name__ == "__main__":
    main()