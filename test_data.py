import paho.mqtt.client as mqtt
import json
import time
import random

# --- AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"

def main():
    print("📡 Sahte Veri Simülatörü Başlatıldı...")
    
    client = mqtt.Client()
    client.connect(MQTT_BROKER, 1883, 60)

    while True:
        # Rastgele bir insan sayısı uydur (5 ile 20 arası)
        fake_count = random.randint(5, 20)
        
        # Veri paketini hazırla
        payload = {
            "room_id": "Amfi-101",
            "occupancy": fake_count,
            "status": "Crowded" if fake_count > 15 else "Normal",
            "timestamp": time.time()
        }
        
        # Gönder
        client.publish(MQTT_TOPIC, json.dumps(payload))
        print(f"📤 Gönderildi: {fake_count} Kişi")
        
        # 2 saniye bekle
        time.sleep(2)

if __name__ == "__main__":
    main()