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

# --- ÖZEL CSS (SCROLL BAR İÇİN) ---
# Bu ayar, grafiğin taşmasını engeller ve altına kaydırma çubuğu ekler
st.markdown("""
<style>
    .chart-container {
        overflow-x: auto;
        white-space: nowrap;
        padding-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- GLOBAL POSTA KUTUSU VE MQTT ---
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

# --- VERİ LİSTESİNİ YÜKLE ---
if 'history_df' not in st.session_state:
    if os.path.exists(CSV_FILE):
        try:
            st.session_state.history_df = pd.read_csv(CSV_FILE).tail(MAX_DISPLAY_ROWS)
        except:
            st.session_state.history_df = pd.DataFrame(columns=['Zaman', 'Kişi', 'Durum'])
    else:
        st.session_state.history_df = pd.DataFrame(columns=['Zaman', 'Kişi', 'Durum'])

# --- GRAFİK FONKSİYONU (SABİT ARALIKLI SCROLL) ---
def plot_interactive_chart(df):
    if df.empty: return None
    
    # --- AYAR: Veriler Arası Mesafe ---
    # Burayı artırırsan veriler daha seyrek olur, grafik daha çok uzar.
    POINT_WIDTH_PX = 40 
    
    # Dinamik Genişlik Hesabı: Veri Sayısı x 40 piksel
    # En az 800 piksel olsun.
    dynamic_width = max(800, len(df) * POINT_WIDTH_PX)

    fig = px.line(
        df, 
        x=df.index, 
        y="Kişi", 
        title="Zaman İçindeki Kişi Sayısı Değişimi", 
        markers=True,
        hover_data={'Kişi': True, 'Zaman': True, 'Durum': True, df.index.name: False}
    )
    
    fig.update_layout(
        xaxis_title="Zaman",
        yaxis_title="Kişi Sayısı",
        template="plotly_dark",
        height=550,
        width=dynamic_width, # <--- Grafiği zorla uzatıyoruz
        margin=dict(l=20, r=20, t=50, b=100), # Kenar boşlukları
        
        xaxis=dict(
            rangeslider=dict(visible=False), # O sıkışık alt grafiği kapattık
            type='category',
            tickvals=df.index,
            ticktext=df['Zaman'],
            tickangle=-45 # Tarihleri okunaklı olsun diye eğdik
        )
    )
    return fig

# --- ARAYÜZ ---
st.subheader("📊 Canlı Değişim Grafiği")
metric_col = st.empty()
info_box = st.empty()

# Grafik için özel bir yer tutucu (Container içinde değil, direkt HTML basacağız)
chart_area = st.empty()

# --- GRAFİK ÇİZME YARDIMCISI ---
def render_chart():
    if not st.session_state.history_df.empty:
        fig = plot_interactive_chart(st.session_state.history_df.copy())
        # Grafiği JSON'a çevirip Streamlit'in container genişliğine uymasını engelliyoruz
        # Böylece sağa doğru sonsuza kadar uzayabilir.
        st.plotly_chart(fig, use_container_width=False) # <--- TRUE DEĞİL FALSE!

# --- 1. AÇILIŞTA EKRANI DOLDUR ---
if not st.session_state.history_df.empty:
    last_row = st.session_state.history_df.iloc[-1]
    
    with metric_col.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("Anlık Kişi", last_row['Kişi'])
        c2.metric("Tarih", last_row['Zaman'])
        status_icon = "🔴" if last_row['Kişi'] > 15 else "🟢"
        c3.metric("Durum", f"{last_row['Durum']} {status_icon}")
    
    # Grafiği çiz (Kaydırılabilir modda)
    with chart_area.container():
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        render_chart()
        st.markdown('</div>', unsafe_allow_html=True)
        
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
            
            with metric_col.container():
                c1, c2, c3 = st.columns(3)
                c1.metric("Anlık Kişi", new_count, delta="Değişim Var 🔔")
                c2.metric("Zaman (TR)", full_time_str)
                icon = "🔴" if new_count > 15 else "🟢"
                c3.metric("Durum", f"{status} {icon}")

            # Grafiği Güncelle
            with chart_area.container():
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                render_chart()
                st.markdown('</div>', unsafe_allow_html=True)
            
            info_box.success(f"Kayıt Eklendi: {full_time_str}")

    time.sleep(1)