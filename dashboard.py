import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime, timedelta
import queue
import os 

# --- AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"
CSV_FILE = "history_v2.csv" 

st.set_page_config(page_title="Canlı Amfi Paneli", layout="wide")

# --- YAN MENÜ (SIDEBAR) ---
# Ayarları buraya alıyoruz ki ana ekran karışmasın
with st.sidebar:
    st.header("⚙️ Panel Ayarları")
    st.write("Grafikte ne kadar geçmişi görmek istersin?")
    # Slider artık solda duracak
    zoom_level = st.slider("Veri Adedi (Zoom)", min_value=10, max_value=200, value=20)
    
    st.divider()
    st.info("Bu sistem MQTT üzerinden anlık veri alır.")

st.title("🏫 Akıllı Amfi Takip Sistemi (İstanbul)")

# --- VERİLERİ YÜKLE ---
def load_data():
    if os.path.exists(CSV_FILE):
        try:
            return pd.read_csv(CSV_FILE)
        except:
            return pd.DataFrame(columns=['Zaman', 'Kişi', 'Durum'])
    else:
        return pd.DataFrame(columns=['Zaman', 'Kişi', 'Durum'])

if 'history_df' not in st.session_state:
    st.session_state.history_df = load_data()

# --- GLOBAL POSTA KUTUSU ---
@st.cache_resource
def get_message_queue():
    return queue.Queue()

data_queue = get_message_queue()

# --- MQTT ---
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

start_mqtt()

# --- ARAYÜZ YER TUTUCULARI ---
metric_col = st.empty()
st.subheader("📊 Canlı Değişim Grafiği")
chart_col = st.empty()
info_box = st.empty()

# --- İLK YÜKLEME (ESKİ VERİLER VARSA) ---
if not st.session_state.history_df.empty:
    # Veriyi kesip (tail) öyle gösteriyoruz
    visible_df = st.session_state.history_df.tail(zoom_level)
    last_row = st.session_state.history_df.iloc[-1]
    
    with metric_col.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("Son Bilinen Kişi", last_row['Kişi'])
        c2.metric("Son Güncelleme", last_row['Zaman'])
        status_icon = "🔴" if last_row['Kişi'] > 15 else "🟢"
        c3.metric("Son Durum", f"{last_row['Durum']} {status_icon}")
    
    chart_col.line_chart(visible_df.set_index("Zaman")['Kişi'])
else:
    info_box.info("Veri bekleniyor...")

# --- ANA DÖNGÜ ---
while True:
    while not data_queue.empty():
        payload = data_queue.get()
        new_count = payload['occupancy']
        status = payload.get('status', 'Normal')

        # Saat Ayarı
        tr_now = datetime.now() + timedelta(hours=3)
        full_time_str = tr_now.strftime('%Y-%m-%d %H:%M:%S')

        # Değişim Kontrolü
        should_save = False
        if st.session_state.history_df.empty:
            should_save = True
        else:
            last_count = st.session_state.history_df.iloc[-1]['Kişi']
            if new_count != last_count:
                should_save = True
        
        if should_save:
            new_data = {
                "Zaman": full_time_str,
                "Kişi": new_count,
                "Durum": status
            }
            new_row_df = pd.DataFrame([new_data])
            st.session_state.history_df = pd.concat([st.session_state.history_df, new_row_df], ignore_index=True)
            
            write_header = not os.path.exists(CSV_FILE)
            new_row_df.to_csv(CSV_FILE, mode='a', header=write_header, index=False)
            
            # GÖSTERİLECEK VERİYİ KES (ZOOM AYARINA GÖRE)
            visible_df = st.session_state.history_df.tail(zoom_level)
            
            with metric_col.container():
                c1, c2, c3 = st.columns(3)
                c1.metric("Anlık Kişi", new_count, delta="Değişim Var 🔔")
                c2.metric("Zaman (TR)", full_time_str)
                icon = "🔴" if new_count > 15 else "🟢"
                c3.metric("Durum", f"{status} {icon}")

            # Kesilmiş veriyi grafiğe bas
            chart_col.line_chart(visible_df.set_index("Zaman")['Kişi'])
            
            info_box.success(f"Kayıt Eklendi: {full_time_str}")

    time.sleep(1)