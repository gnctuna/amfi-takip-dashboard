import paho.mqtt.client as mqtt
import json
import time
import random

# --- AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"

def main():
    print("⚡️ HİPERAKTİF Test Simülatörü Başlatıldı...")
    
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        print("✅ Buluta Bağlandı!")
    except:
        print("❌ HATA: İnternet bağlantısı yok!")
        return

    # Başlangıç değeri
    last_count = 10

    while True:
        # Önceki sayıdan FARKLI bir sayı üretmeyi garanti et
        # Eğer eskisi küçükse büyük yap, büyükse küçük yap (Zig-Zag taktiği)
        if last_count < 15:
            fake_count = random.randint(16, 25)
        else:
            fake_count = random.randint(5, 14)
            
        last_count = fake_count
        
        # Veri paketini hazırla
        payload = {
            "room_id": "Test-Oda",
            "occupancy": fake_count,
            "status": "Crowded" if fake_count > 15 else "Normal",
            "timestamp": time.time()
        }
        
        # Gönder
        client.publish(MQTT_TOPIC, json.dumps(payload))
        print(f"🚀 Veri Fırlatıldı: {fake_count} Kişi")
        
        # Bekleme süresini azalttık (Daha seri veri aksın)
        time.sleep(1.0) 

if __name__ == "__main__":
    main()