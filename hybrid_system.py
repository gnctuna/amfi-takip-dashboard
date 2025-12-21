import cv2
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from ultralytics import YOLO
from datetime import datetime
import time
import sys

# 1. GOOGLE SHEETS AYARI (Service Account JSON dosyanın adını buraya yaz)
SERVICE_ACCOUNT_FILE = 'secrets.json' 
SHEET_ID = '1YgVkVyMa_TbhgccfUMsfFtbtKrS5glorha1rGHMK1Kk' # Paylaştığın linkten aldım

def connect_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1

def save_to_cloud(sheet, count, status, mode_name):
    try:
        new_row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            int(count),
            status,
            mode_name
        ]
        sheet.append_row(new_row)
        print(f"✅ Buluta Kaydedildi: {count} kişi ({status})")
    except Exception as e:
        print(f"❌ Kayıt Hatası: {e}")

def run_system(mode):
    # Google bağlantısını başlat
    sheet = connect_gsheets()
    
    model = YOLO('yolov8x.pt') 
    cap = cv2.VideoCapture(0)
    last_save_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret: break

        results = model(frame, classes=[0], conf=0.4, verbose=False)
        boxes = results[0].boxes
        count = len(boxes)
        status = "Dolu" if count > 0 else "Bos"

        # MAVİ KUTU ÇİZİMİ
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
            cv2.putText(frame, "Kisi", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        cv2.imshow("PrivacyOccupancyAI", frame)

        # Veri Gönderim Periyodu
        current_time = time.time()
        wait_time = 30 if mode == "SINIF" else 300
        if current_time - last_save_time > wait_time:
            save_to_cloud(sheet, count, status, mode)
            last_save_time = current_time

        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    selected_mode = sys.argv[1] if len(sys.argv) > 1 else "SINIF"
    run_system(selected_mode)