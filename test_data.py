import paho.mqtt.client as mqtt
import json
import time
import random

# --- AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"
GENDERME_HIZI = 3  # <-- ÖNEMLİ: Veri gönderme sıklığı (Saniye)

def main():
    print(f"🧪 SİMÜLATÖR BAŞLATILDI (Hız: Her {GENDERME_HIZI} saniyede bir)")
    
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        print("✅ Buluta Bağlandı!")
    except:
        print("❌ HATA: İnternet bağlantısı yok!")
        return

    current_count = 10
    current_mode = "SINIF_LIVE" 
    
    while True:
        # --- 1. SENARYO DEĞİŞİMİ (%20 Şans) ---
        if random.random() < 0.20:
            scenario_roll = random.random()
            
            if scenario_roll < 0.33:
                current_count = random.randint(0, 15)
                current_mode = "SINIF_LIVE"
                print("\n📉 SENARYO: Teneffüs")
                
            elif scenario_roll < 0.66:
                current_count = random.randint(25, 45)
                current_mode = "SINIF_LIVE"
                print("\n🏫 SENARYO: Sınıf Dersi")
                
            else:
                current_count = random.randint(120, 200)
                current_mode = "AMFI_SNAPSHOT"
                print("\n🚀 SENARYO: Amfi Konferansı")

        # --- 2. UFAK DALGALANMALAR ---
        change = random.randint(-3, 3)
        current_count += change
        if current_count < 0: current_count = 0
        
        # --- 3. VERİ PAKETLEME ---
        limit = 50 if current_mode == "AMFI_SNAPSHOT" else 20
        status = "Crowded" if current_count > limit else "Normal"
        
        payload = {
            "occupancy": current_count,
            "status": status,
            "mode": current_mode,
            "timestamp": time.time()
        }
        
        client.publish(MQTT_TOPIC, json.dumps(payload))
        print(f"📤 Giden: {current_count} Kişi | {status} | Bekleniyor...")
        
        # YENİ AYAR: Burada 3 saniye bekliyoruz
        time.sleep(GENDERME_HIZI)

if __name__ == "__main__":
    main()