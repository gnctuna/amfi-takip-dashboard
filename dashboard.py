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

# --- ÖZEL CSS (GELENEKSEL VE BELİRGİN SCROLLBAR) ---
st.markdown("""
<style>
    /* Grafik Kutusu */
    .plotly-chart-container {
        overflow-x: auto;       /* Yatay kaydırmaya izin ver */
        padding-bottom: 15px;   /* Scrollbar için alt boşluk */
        border: 1px solid #444; /* Çerçeve (Sınırları belli olsun) */
        border-radius: 5px;
        background-color: #0e1117; /* Arkaplan rengi */
    }

    /* Scrollbar Tasarımı (Chrome/Safari/Edge) */
    .plotly-chart-container::-webkit-scrollbar {
        height: 18px; /* Çubuk yüksekliği (Kalın ve rahat tutulabilir) */
    }
    .plotly-chart-container::-webkit-scrollbar-track {
        background: #1e1e1e; /* Ray rengi (Koyu gri) */
        border-radius: 9px;
    }
    .plotly-chart-container::-webkit-scrollbar-thumb {
        background-color: #888; /* Tutamaç rengi (Açık gri) */
        border-radius: 9px;
        border: 3px solid #1e1e1e; /* Etrafında boşluk hissi */
    }
    .plotly-chart-container::-webkit-scrollbar-thumb:hover {
        background-color: #aaa; /* Üzerine gelince parlasın */
    }
</style>
""", unsafe_allow_html=True)

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
def plot_interactive_chart(df):
    if df.empty: return None
    
    # 1. GENİŞLİK AYARI (SABİT MESAFE)
    # Her veri noktası için 50 piksel. 
    # Bu mesafe KİLİTLENECEK, yani zoom-out yapılamayacak.
    POINT_WIDTH_PX = 50
    # En az ekran genişliği kadar olsun (1200px), veri çoksa uzasın.
    dynamic_width = max(1200, len(df) * POINT_WIDTH_PX)

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
        height=500,
        width=dynamic_width, # Hesaplanan genişliği zorla
        margin=dict(l=20, r=20, t=50, b=20),
        
        # EFSANE AYAR: 'hover' modu. 
        # Grafiğin içinde sürükleme yapılmaz, sadece üzerine gelince bilgi verir.
        # Kaydırma işlemi tamamen aşağıdaki scrollbar'a bırakılır.
        dragmode=False 
    )

    fig.update_xaxes(
        tickvals=df.index,
        ticktext=df['Zaman'],
        tickangle=-45,
        rangeslider=dict(visible=False), # Plotly'nin kendi slider'ını kapattık
        type='category',
        
        # --- KİLİT NOKTASI ---
        fixedrange=True # X ekseninde ZOOM yapmayı ve SÜRÜKLEMEYİ yasakla!
    )
    
    fig.update_yaxes(
        fixedrange=True # Y ekseninde de zoom yasak
    )
    
    return fig

# --- ARAYÜZ ---
st.subheader("📊 Canlı Değişim Grafiği")
metric_col = st.empty()
info_box = st.empty()

# Grafik Kutusu (HTML)
chart_area = st.empty()

def render_chart():
    if not st.session_state.history_df.empty:
        fig = plot_interactive_chart(st.session_state.history_df.copy())
        
        # Grafiği özel CSS kutusunun içine koyuyoruz
        st.markdown('<div class="plotly-chart-container">', unsafe_allow_html=True)
        
        # config ayarları ile grafiğin üzerindeki butonları ve zoom özelliklerini kapatıyoruz
        st.plotly_chart(
            fig, 
            use_container_width=False, # Bizim genişliğimiz geçerli olsun
            config={
                'scrollZoom': False,       # Mouse tekerleğiyle zoom YASAK
                'displayModeBar': False,   # Üstteki butonları GİZLE
                'staticPlot': False        # Hover (baloncuk) bilgisi açık kalsın
            }
        )
        st.markdown('</div>', unsafe_allow_html=True)

# --- 1. AÇILIŞ ---
if not st.session_state.history_df.empty:
    last_row = st.session_state.history_df.iloc[-1]
    with metric_col.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("Anlık Kişi", last_row['Kişi'])
        c2.metric("Tarih", last_row['Zaman'])
        status_icon = "🔴" if last_row['Kişi'] > 15 else "🟢"
        c3.metric("Durum", f"{last_row['Durum']} {status_icon}")
    
    render_chart()
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

            render_chart()
            info_box.success(f"Kayıt Eklendi: {full_time_str}")

    time.sleep(1)