import paho.mqtt.client as mqtt
import json
import time
import random

# --- AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"

def main():
    print("🧪 YÜKSEK KAPASİTE Test Simülatörü Başlatıldı...")
    
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        print("✅ Buluta Bağlandı!")
    except:
        print("❌ HATA: İnternet bağlantısı yok!")
        return

    # Başlangıç değeri (Ortalardan başlasın)
    current_count = 180
    
    while True:
        # %30 ihtimalle sayı değişir (Biraz daha hareketli olsun diye %30 yaptım)
        if random.random() > 0.7:
            old_count = current_count
            
            # Değişim Miktarı: 5 ile 15 kişi arası girsin/çıksın
            change = random.randint(5, 15)
            
            # Artır veya Azalt
            if random.random() > 0.5:
                current_count += change
            else:
                current_count -= change
            
            # --- SINIRLARI ZORLA (150 - 250 Arası) ---
            if current_count > 250: 
                current_count = 250
            if current_count < 150: 
                current_count = 150

            # Eğer sınırlar yüzünden sayı değişmediyse yazdırma
            if current_count != old_count:
                print(f"🔀 DEĞİŞİM: {old_count} -> {current_count}")
        else:
            print(f"zzz Sabit: {current_count} (Grafiğe yansımaz)")

        # Veri Paketi
        payload = {
            "occupancy": current_count,
            "status": "Crowded" if current_count > 200 else "Normal", # 200'ü geçerse Crowded desin
            "timestamp": time.time()
        }
        
        client.publish(MQTT_TOPIC, json.dumps(payload))
        
        # 1 saniye bekle
        time.sleep(1)

if __name__ == "__main__":
    main()