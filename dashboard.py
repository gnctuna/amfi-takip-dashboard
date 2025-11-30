import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime, timedelta
import queue
import os 
import plotly.express as px

# --- AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"
CSV_FILE = "history_v3.csv" 
MAX_DISPLAY_ROWS = 5000 

st.set_page_config(page_title="Canlı Amfi Paneli", layout="wide")

# --- MQTT ALTYAPISI ---
@st.cache_resource
def get_message_queue():
    return queue.Queue()

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

data_queue = get_message_queue()
start_mqtt()

# --- VERİ YÜKLEME ---
if 'history_df' not in st.session_state:
    if os.path.exists(CSV_FILE):
        try:
            st.session_state.history_df = pd.read_csv(CSV_FILE).tail(MAX_DISPLAY_ROWS)
        except:
            st.session_state.history_df = pd.DataFrame(columns=['Zaman', 'Kişi', 'Durum'])
    else:
        st.session_state.history_df = pd.DataFrame(columns=['Zaman', 'Kişi', 'Durum'])

# --- GRAFİK FONKSİYONU ---
def create_figure(df):
    if df.empty: return None
    
    # 1. GENİŞLİK HESABI (Sıkışmayı Önleyen Formül)
    # Her bir veri noktası için 40 piksel ayırıyoruz.
    # 10 veri varsa 400px, 100 veri varsa 4000px genişlik olur.
    POINT_WIDTH_PX = 40
    # En az 1000 piksel olsun ki boşken kötü durmasın
    dynamic_width = max(1000, len(df) * POINT_WIDTH_PX)

    fig = px.line(
        df, 
        x=df.index, 
        y="Kişi", 
        markers=True,
        # Mouse ile üzerine gelince bilgileri göster
        hover_data={'Kişi': True, 'Zaman': True, 'Durum': True, df.index.name: False}
    )
    
    fig.update_layout(
        xaxis_title="", 
        yaxis_title="Kişi Sayısı",
        template="plotly_dark",
        height=500,
        width=dynamic_width, # <--- GRAFİĞİ ZORLA UZATIYORUZ
        margin=dict(l=20, r=20, t=30, b=20),
        
        # Telefonda parmakla sağa-sola kaydırmayı açar (Pan)
        dragmode="pan" 
    )

    fig.update_xaxes(
        showticklabels=False,    # Alttaki tarih yazılarını GİZLE
        rangeslider=dict(visible=False), # O küçük alt grafiği GİZLE
        fixedrange=True,         # Zoom yapmayı KİLİTLE (Sıkışmayı önler)
        type='category'
    )
    
    fig.update_yaxes(fixedrange=True)
    return fig

# --- ARAYÜZ YERLEŞİMİ ---
st.subheader("📊 Canlı Değişim Grafiği")
metric_col = st.empty()
info_box = st.empty()

# Grafik Kutusu
chart_placeholder = st.empty()

def render_dashboard():
    # 1. Metrikler
    if not st.session_state.history_df.empty:
        last_row = st.session_state.history_df.iloc[-1]
        with metric_col.container():
            c1, c2, c3 = st.columns(3)
            c1.metric("Anlık Kişi", last_row['Kişi'])
            c2.metric("Tarih", last_row['Zaman'])
            status_icon = "🔴" if last_row['Kişi'] > 15 else "🟢"
            c3.metric("Durum", f"{last_row['Durum']} {status_icon}")

        # 2. GRAFİK ÇİZİMİ
        fig = create_figure(st.session_state.history_df)
        
        # --- KRİTİK NOKTA BURASI ---
        # use_container_width=False yapıyoruz.
        # Bu sayede Streamlit grafiği ekrana sıkıştırmaz.
        # Grafik ekrandan taşacağı için tarayıcı OTOMATİK OLARAK scrollbar koyar.
        chart_placeholder.plotly_chart(fig, use_container_width=False) 

# --- 1. AÇILIŞ ---
if not st.session_state.history_df.empty:
    render_dashboard()
    info_box.success("Sistem hazır.")
else:
    info_box.warning("Veri bekleniyor...")

# --- 2. ANA DÖNGÜ ---
while True:
    while not data_queue.empty():
        payload = data_queue.get()
        new_count = payload['occupancy']
        status = payload.get('status', 'Normal')
        tr_now = datetime.now() + timedelta(hours=3)
        full_time_str = tr_now.strftime('%Y-%m-%d %H:%M:%S')

        should_save = False
        if st.session_state.history_df.empty:
            should_save = True
        else:
            last_count = st.session_state.history_df.iloc[-1]['Kişi']
            if new_count != last_count:
                should_save = True
        
        if should_save:
            new_data = {"Zaman": full_time_str, "Kişi": new_count, "Durum": status}
            new_row_df = pd.DataFrame([new_data])
            st.session_state.history_df = pd.concat([st.session_state.history_df, new_row_df], ignore_index=True)
            
            write_header = not os.path.exists(CSV_FILE)
            new_row_df.to_csv(CSV_FILE, mode='a', header=write_header, index=False)
            
            render_dashboard()
            info_box.success(f"Kayıt Eklendi: {full_time_str}")

    time.sleep(1)