import paho.mqtt.client as mqtt
import json
import time
import random

# --- AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"

def main():
    print("🧪 GELİŞMİŞ Test Simülatörü Başlatıldı...")
    print("Senaryolar arasında rastgele geçiş yapılacak (Ders / Teneffüs / Amfi)...")
    
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        print("✅ Buluta Bağlandı!")
    except:
        print("❌ HATA: İnternet bağlantısı yok!")
        return

    # Başlangıç değeri
    current_count = 10
    current_mode = "SINIF_LIVE" # Başlangıç modu
    
    while True:
        # --- 1. SENARYO DEĞİŞİMİ (%10 Şans) ---
        # Her döngüde %10 ihtimalle radikal bir değişiklik olsun
        if random.random() < 0.10:
            scenario_roll = random.random()
            
            if scenario_roll < 0.33:
                # DURUM 1: TENEFFÜS / BOŞ ODA (Az Kişi)
                current_count = random.randint(0, 15)
                current_mode = "SINIF_LIVE"
                print("\n📉 SENARYO: Teneffüs (Oda Boşaldı)")
                
            elif scenario_roll < 0.66:
                # DURUM 2: NORMAL SINIF DERSİ (Orta Kişi)
                current_count = random.randint(25, 45)
                current_mode = "SINIF_LIVE"
                print("\n🏫 SENARYO: Sınıf Dersi (Orta Kalabalık)")
                
            else:
                # DURUM 3: AMFİ KONFERANSI (Çok Kişi)
                current_count = random.randint(120, 200)
                current_mode = "AMFI_SNAPSHOT"
                print("\n🚀 SENARYO: Amfi Konferansı (Aşırı Kalabalık)")

        # --- 2. UFAK DALGALANMALAR ---
        # Sayı sabit kalmasın, yaşayan bir veri gibi +-3 oynasın
        change = random.randint(-3, 3)
        current_count += change
        
        # Eksiye düşmeyi engelle
        if current_count < 0: current_count = 0
        
        # --- 3. VERİ PAKETLEME ---
        # Kalabalık sınırı duruma göre değişsin
        limit = 50 if current_mode == "AMFI_SNAPSHOT" else 20
        status = "Crowded" if current_count > limit else "Normal"
        
        payload = {
            "occupancy": current_count,
            "status": status,
            "mode": current_mode, # Dashboard rengi buna göre değişecek
            "timestamp": time.time()
        }
        
        client.publish(MQTT_TOPIC, json.dumps(payload))
        
        print(f"📤 Giden: {current_count} Kişi | Mod: {current_mode}")
        
        # Dashboard'un hızını test etmek için 1 saniye bekle
        time.sleep(1)

if __name__ == "__main__":
    main()