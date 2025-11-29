import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime, timedelta
import queue
import os 
import plotly.express as px # Plotly kütüphanesi

# --- AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"
# VERİ SIFIRLAMA İÇİN YENİ DOSYA ADI
CSV_FILE = "history_v3.csv" 
MAX_DISPLAY_ROWS = 5000 # Grafikte maksimum yüklenecek satır sayısı

st.set_page_config(page_title="Canlı Amfi Paneli", layout="wide")
st.title("🏫 Akıllı Amfi Takip Sistemi (İstanbul)")

# --- GLOBAL POSTA KUTUSU VE VERİ HAFIZASI ---
@st.cache_resource
def get_message_queue():
    # MQTT robotunun veri atacağı yer
    return queue.Queue()

data_queue = get_message_queue()

if 'history_df' not in st.session_state:
    st.session_state.history_df = pd.DataFrame(columns=['Zaman', 'Kişi', 'Durum'])

# --- FONKSİYONLAR ---
@st.cache_resource
def start_mqtt():
    def on_message(client, userdata, message):
        try:
            payload = json.loads(message.payload.decode())
            q = get_message_queue()
            q.put(payload)
        except Exception as e:
            print(f"Hata: {e}")

    client = mqtt.Client()
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.subscribe(MQTT_TOPIC)
    client.loop_start()
    return client

def plot_interactive_chart(df):
    if df.empty: return None
    
    # KATEGORİK EKSEN (x=df.index) ile zaman aralığı ne olursa olsun eşit mesafe sağlar
    fig = px.line(
        df, 
        x=df.index, # X eksenine sıralı satır indexi verir
        y="Kişi", 
        title="Zaman İçindeki Kişi Sayısı Değişimi", 
        markers=True,
        hover_data={'Kişi': True, 'Zaman': True, 'Durum': True, df.index.name: False}
    )
    
    # X ekseninde sadece veri olan noktaların zamanını yazdır
    fig.update_xaxes(
        tickvals=df.index,
        ticktext=df['Zaman'], 
        rangeslider=dict(visible=True, thickness=0.08), 
        type='category' # Kategorik tip, aralıkları eşit yapar
    )

    fig.update_layout(
        xaxis_title="Zaman (Veri Kayıt Noktaları)",
        yaxis_title="Kişi Sayısı",
        template="plotly_dark",
        height=500
    )
    return fig

# --- İLK YÜKLEME VE ÇALIŞTIRMA ---
start_mqtt()

# Eğer dosya varsa yükle (Kalici hafiza)
if os.path.exists(CSV_FILE):
    try:
        loaded_df = pd.read_csv(CSV_FILE)
        # Sadece Max_Rows kadarını al ve RAM'e yükle (Performans için)
        st.session_state.history_df = loaded_df.tail(MAX_DISPLAY_ROWS) 
    except:
        pass

# --- ARAYÜZ YER TUTUCULARI ---
st.header("📊 Canlı Değişim Grafiği")
chart_placeholder = st.empty()
metric_col = st.empty()
info_box = st.empty()

# --- ANA DÖNGÜ ---
while True:
    # 1. Posta Kutusunu Boşalt
    while not data_queue.empty():
        payload = data_queue.get()
        new_count = payload['occupancy']
        status = payload.get('status', 'Normal')

        # Saat Ayarı (UTC+3)
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
            # Yeni veriyi hazırla
            new_data = {"Zaman": full_time_str, "Kişi": new_count, "Durum": status}
            new_row_df = pd.DataFrame([new_data])
            
            # RAM'deki listeye ekle
            st.session_state.history_df = pd.concat([st.session_state.history_df, new_row_df], ignore_index=True)
            
            # CSV'ye Yaz (Kalıcı Hafıza)
            write_header = not os.path.exists(CSV_FILE)
            new_row_df.to_csv(CSV_FILE, mode='a', header=write_header, index=False)
            
            # --- EKRANI GÜNCELLE ---
            with metric_col.container():
                c1, c2, c3 = st.columns(3)
                c1.metric("Anlık Kişi", new_count, delta="Değişim Var 🔔")
                c2.metric("Zaman (TR)", full_time_str)
                icon = "🔴" if new_count > 15 else "🟢"
                c3.metric("Durum", f"{status} {icon}")

            # Grafiği güncelle
            fig = plot_interactive_chart(st.session_state.history_df.copy())
            chart_placeholder.plotly_chart(fig, use_container_width=True)
            
            info_box.success(f"Kayıt Eklendi: {full_time_str}")

    time.sleep(1)