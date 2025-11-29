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

# --- ÖZEL CSS (GELENEKSEL SCROLLBAR İÇİN) ---
# Bu CSS, grafiği bir kutu içine alır ve taşarsa
# tarayıcının standart kaydırma çubuğunu çıkarır.
st.markdown("""
<style>
    .plotly-chart-container {
        overflow-x: auto; /* Yatay taşmada standart scrollbar çıkar */
        white-space: nowrap; /* İçeriği tek satırda tut */
        padding-bottom: 10px; /* Scrollbar için biraz boşluk */
        border-radius: 5px;
        border: 1px solid #333; /* İsteğe bağlı ince çerçeve */
    }
    /* Scrollbar'ı biraz daha belirgin yapalım (Webkit tarayıcılar için) */
    .plotly-chart-container::-webkit-scrollbar {
        height: 12px;
    }
    .plotly-chart-container::-webkit-scrollbar-track {
        background: #1e1e1e;
        border-radius: 10px;
    }
    .plotly-chart-container::-webkit-scrollbar-thumb {
        background: #555;
        border-radius: 10px;
    }
    .plotly-chart-container::-webkit-scrollbar-thumb:hover {
        background: #888;
    }
</style>
""", unsafe_allow_html=True)

# --- MQTT VE VERİ ALTYAPISI ---
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

if 'history_df' not in st.session_state:
    if os.path.exists(CSV_FILE):
        try:
            st.session_state.history_df = pd.read_csv(CSV_FILE).tail(MAX_DISPLAY_ROWS)
        except:
            st.session_state.history_df = pd.DataFrame(columns=['Zaman', 'Kişi', 'Durum'])
    else:
        st.session_state.history_df = pd.DataFrame(columns=['Zaman', 'Kişi', 'Durum'])

# --- YENİ GRAFİK FONKSİYONU ---
def plot_interactive_chart(df):
    if df.empty: return None
    
    # 1. SABİT GENİŞLİK AYARI (Sıkışmayı Önler)
    # Her veri noktasına 30 piksel ayırıyoruz.
    # 100 veri varsa grafik 3000 piksel genişliğinde çizilir.
    # Bu sayede noktalar asla birbirine girmez.
    POINT_WIDTH_PX = 30
    dynamic_width = max(1200, len(df) * POINT_WIDTH_PX)

    # 2. BAŞLANGIÇ ODAĞI (Zoom Sınırı Gibi Davranır)
    # Grafik ilk açıldığında sadece SON 50 VERİYİ gösterir.
    # Bu, "maksimum zoom-out" hissi verir, çünkü başlangıçta sıkışık değildir.
    total_points = len(df)
    start_view = max(0, total_points - 50) 
    end_view = total_points

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
        width=dynamic_width, # <--- Grafiği zorla genişletiyoruz
        margin=dict(l=20, r=20, t=50, b=20),
        dragmode="pan" # Varsayılan olarak kaydırma modu
    )

    fig.update_xaxes(
        tickvals=df.index,
        ticktext=df['Zaman'],
        # Kullanışsız dediğin o alt çubuğu KAPATIYORUZ
        rangeslider=dict(visible=False), 
        # Başlangıçta gösterilecek aralık (Son 50 veri)
        range=[start_view, end_view], 
        type='category',
        tickangle=-45
    )
    return fig

# --- ARAYÜZ ---
st.subheader("📊 Canlı Değişim Grafiği")
metric_col = st.empty()
info_box = st.empty()

# Grafik Alanı için HTML Yer Tutucu
chart_area = st.empty()

# Grafiği Çizen Yardımcı Fonksiyon
def render_chart():
    if not st.session_state.history_df.empty:
        fig = plot_interactive_chart(st.session_state.history_df.copy())
        # Grafiği özel CSS kutumuzun içine koyuyoruz
        st.markdown('<div class="plotly-chart-container">', unsafe_allow_html=True)
        # use_container_width=False OLMALI ki bizim belirlediğimiz büyük genişlik geçerli olsun
        st.plotly_chart(fig, use_container_width=False) 
        st.markdown('</div>', unsafe_allow_html=True)

# --- 1. AÇILIŞ GÖSTERİMİ ---
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

            # Grafiği Güncelle
            render_chart()
            
            info_box.success(f"Kayıt Eklendi: {full_time_str}")

    time.sleep(1)