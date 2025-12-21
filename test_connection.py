import gspread
from google.oauth2.service_account import Credentials

# AYARLAR
SERVICE_ACCOUNT_FILE = 'secrets.json'
# Buraya kendi Sheet ID'ni yazdığından emin ol
SHEET_ID = '1YgVkVyMa_TbhgccfUMsfFtbtKrS5glorha1rGHMK1Kk' 

def test_connection():
    print("1. Kimlik dosyası okunuyor...")
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
        client = gspread.authorize(creds)
        print("✅ Kimlik doğrulama başarılı!")
    except Exception as e:
        print(f"❌ Kimlik Hatası: {e}")
        return

    print("2. Tabloya erişilmeye çalışılıyor...")
    try:
        sheet = client.open_by_key(SHEET_ID).sheet1
        print(f"✅ Tabloya erişildi: {sheet.title}")
    except Exception as e:
        print(f"❌ Erişim Hatası (Muhtemelen Paylaşım İzni Yok): {e}")
        print("İPUCU: 'secrets.json' içindeki 'client_email' adresine Editör yetkisi verdin mi?")
        return

    print("3. Test verisi yazılıyor...")
    try:
        sheet.append_row(["TEST", "Baglanti", "Basarili", "✅"])
        print("✅ YAZMA BAŞARILI! Google Sheet'ini kontrol et.")
    except Exception as e:
        print(f"❌ Yazma Hatası: {e}")

if __name__ == "__main__":
    test_connection()