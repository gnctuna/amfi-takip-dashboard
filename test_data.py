import paho.mqtt.client as mqtt
import json
import time
import random

MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"

def main():
    print("🧪 Akıllı Test Simülatörü Başlatıldı...")
    
    client = mqtt.Client()
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        print("✅ Bağlandı!")
    except:
        return

    # Başlangıç
    current_count = 10
    
    while True:
        # %20 ihtimalle sayı değişir (Grafikte yeni nokta oluşmalı)
        # %80 ihtimalle sayı AYNI kalır (Grafikte yeni nokta OLUŞMAMALI)
        if random.random() > 0.8:
            old_count = current_count
            # Sayıyı değiştir (Artır veya azalt)
            if random.random() > 0.5:
                current_count += random.randint(1, 3)
            else:
                current_count -= random.randint(1, 3)
            
            print(f"🔀 DEĞİŞİM: {old_count} -> {current_count}")
        else:
            print(f"zzz Sabit: {current_count} (Grafiğe yansımamalı)")

        payload = {
            "occupancy": current_count,
            "status": "Crowded" if current_count > 15 else "Normal",
            "timestamp": time.time()
        }
        
        client.publish(MQTT_TOPIC, json.dumps(payload))
        time.sleep(1)

if __name__ == "__main__":
    main()