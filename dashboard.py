import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime
import queue
import os # Dosya işlemleri için

# --- AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"
CSV_FILE = "history.csv" # Verilerin saklanacağı dosya

st.set_page_config(page_title="Canlı Amfi Paneli", layout="wide")
st.title("🏫 Akıllı Amfi Takip Sistemi (Kalıcı Hafıza)")

# --- 1. GEÇMİŞ VERİLERİ YÜKLE ---
# Site açılır açılmaz CSV dosyasını okur ve grafiği çizer.
# MQTT bağlı olmasa bile burası çalışır.
def load_data():
    if os.path.exists(CSV_FILE):
        try:
            return pd.read_csv(CSV_FILE)
        except:
            return pd.DataFrame(columns=['Saat', 'Tarih', 'Kişi', 'Durum'])
    else:
        return pd.DataFrame(columns=['Saat', 'Tarih', 'Kişi', 'Durum'])

# Veriyi RAM'e al
if 'history_df' not in st.session_state:
    st.session_state.history_df = load_data()

# --- GLOBAL POSTA KUTUSU ---
@st.cache_resource
def get_message_queue():
    return queue.Queue()

data_queue = get_message_queue()

# --- MQTT AYARLARI ---
def on_message(client, userdata, message):
    try:
        payload = json.loads(message.payload.decode())
        q = get_message_queue()
        q.put(payload)
    except Exception as e:
        print(f"Hata: {e}")

@st.cache_resource
def start_mqtt():
    client = mqtt.Client()
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.subscribe(MQTT_TOPIC)
    client.loop_start()
    return client

# MQTT Başlat
start_mqtt()

# --- ARAYÜZ YER TUTUCULARI ---
metric_col = st.empty()
chart_col = st.empty()
info_box = st.empty()

# --- İLK ÇİZİM (MQTT BEKLEMEDEN) ---
# Eğer geçmiş veri varsa hemen ekrana bas
if not st.session_state.history_df.empty:
    last_row = st.session_state.history_df.iloc[-1]
    
    with metric_col.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("Son Bilinen Kişi", last_row['Kişi'])
        c2.metric("Tarih", f"{last_row['Tarih']} {last_row['Saat']}")
        status_icon = "🔴" if last_row['Kişi'] > 15 else "🟢"
        c3.metric("Son Durum", f"{last_row['Durum']} {status_icon}")
    
    # Grafiği çiz (Sadece Kişi sayısı)
    st.subheader("📊 Değişim Grafiği")
    chart_col.line_chart(st.session_state.history_df.set_index("Saat")['Kişi'])
else:
    info_box.info("Henüz geçmiş veri yok. Sistem ilk veriyi bekliyor...")

# --- ANA DÖNGÜ ---
while True:
    # Kuyrukta yeni veri var mı?
    while not data_queue.empty():
        payload = data_queue.get()
        
        new_count = payload['occupancy']
        current_time = datetime.now().strftime('%H:%M:%S')
        current_date = datetime.now().strftime('%Y-%m-%d')
        status = payload.get('status', 'Normal')

        # --- KRİTİK NOKTA: DEĞİŞİM KONTROLÜ ---
        # Sadece sayı değiştiyse kaydet
        should_save = False
        
        if st.session_state.history_df.empty:
            should_save = True # İlk veriyi kesin kaydet
        else:
            last_count = st.session_state.history_df.iloc[-1]['Kişi']
            if new_count != last_count:
                should_save = True # Sayı değişti, kaydet!
        
        if should_save:
            # 1. Yeni satırı oluştur
            new_data = {
                "Saat": current_time,
                "Tarih": current_date,
                "Kişi": new_count,
                "Durum": status
            }
            new_row_df = pd.DataFrame([new_data])
            
            # 2. RAM'deki listeye ekle
            st.session_state.history_df = pd.concat([st.session_state.history_df, new_row_df], ignore_index=True)
            
            # 3. CSV DOSYASINA YAZ (Kalıcı Hafıza)
            # mode='a' (append) ile dosyanın sonuna ekleriz
            # header=False (başlıkları tekrar yazmasın diye)
            write_header = not os.path.exists(CSV_FILE)
            new_row_df.to_csv(CSV_FILE, mode='a', header=write_header, index=False)
            
            # 4. Arayüzü Güncelle
            with metric_col.container():
                c1, c2, c3 = st.columns(3)
                c1.metric("Anlık Kişi", new_count, delta="Değişim Var 🔔")
                c2.metric("Saat", current_time)
                icon = "🔴" if new_count > 15 else "🟢"
                c3.metric("Durum", f"{status} {icon}")

            chart_col.line_chart(st.session_state.history_df.set_index("Saat")['Kişi'])
            info_box.success(f"Yeni kayıt eklendi: {current_time} -> {new_count} Kişi")
            
        else:
            # Sayı değişmediyse sadece bilgi ver, kaydetme
            # info_box.info(f"Sayı sabit ({new_count}). Kayıt yapılmadı.") 
            pass

    time.sleep(1)