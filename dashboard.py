import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime, timedelta
import queue
import os 
import plotly.express as px
import streamlit.components.v1 as components

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

# --- GRAFİK OLUŞTURUCU (ESKİ GÜZEL MAVİ TASARIM) ---
def create_figure(df):
    if df.empty: return None
    
    # 1. GENİŞLİK HESABI (Sıkışmayı Önler)
    # Her veri noktasına 35 piksel ayırıyoruz. Grafik sağa doğru uzar.
    POINT_WIDTH_PX = 35
    dynamic_width = max(1000, len(df) * POINT_WIDTH_PX)

    # 2. ESKİ GÜZEL TASARIM (Streamlit Mavisi)
    # color_discrete_sequence=['#29b5e8'] -> İşte o sevdiğin mavi renk bu!
    fig = px.line(
        df, 
        x=df.index, 
        y="Kişi", 
        markers=True,
        title="",
        color_discrete_sequence=['#29b5e8'], # Parlak Mavi
        hover_data={'Kişi': True, 'Zaman': True, 'Durum': True, df.index.name: False}
    )
    
    fig.update_layout(
        xaxis_title="", 
        yaxis_title="Kişi Sayısı",
        template="plotly_dark", # Koyu tema (ama mavi çizgili)
        height=450,
        width=dynamic_width, # Hesaplanan genişlik
        margin=dict(l=20, r=20, t=30, b=20),
        
        # Telefondan parmakla sağa-sola kaydırmayı açar
        dragmode="pan",
        
        # Arkaplanı Streamlit ile tam uyumlu yap
        paper_bgcolor='#0e1117', 
        plot_bgcolor='#0e1117',
        
        # O siyah ızgara çizgilerini yumuşat
        xaxis=dict(showgrid=True, gridcolor='#333'),
        yaxis=dict(showgrid=True, gridcolor='#333')
    )

    fig.update_xaxes(
        showticklabels=False, # Alttaki kalabalık tarihleri gizle
        rangeslider=dict(visible=False), 
        fixedrange=True, # Zoom kilitli (Sıkışmayı önler)
        type='category'
    )
    
    fig.update_yaxes(fixedrange=True)
    return fig

# --- ARAYÜZ ---
st.subheader("📊 Canlı Değişim Grafiği")
metric_col = st.empty()
info_box = st.empty()
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

        # 2. GRAFİK (SCROLLBAR + GÜZEL TASARIM)
        fig = create_figure(st.session_state.history_df)
        
        # HTML'e çeviriyoruz ama Streamlit temasını koruyoruz
        fig_html = fig.to_html(include_plotlyjs='cdn', full_html=True, config={'displayModeBar': False})
        
        # Özel bir HTML kutusu oluşturuyoruz.
        # Bu kutu, içindeki grafik büyükse otomatik SCROLLBAR çıkarır.
        with chart_placeholder.container():
            components.html(
                f"""
                <style>
                    body {{ margin: 0; background-color: #0e1117; }}
                    ::-webkit-scrollbar {{ height: 10px; }}
                    ::-webkit-scrollbar-track {{ background: #1e1e1e; }}
                    ::-webkit-scrollbar-thumb {{ background: #555; border-radius: 5px; }}
                    ::-webkit-scrollbar-thumb:hover {{ background: #888; }}
                </style>
                <div style="width: 100%; overflow-x: auto;">
                    {fig_html}
                </div>
                """,
                height=480, # Scrollbar için yer açtık
                scrolling=True
            )

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

    time.sleep(0.1)