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

# --- VERİ YÜKLEME ---
if 'history_df' not in st.session_state:
    if os.path.exists(CSV_FILE):
        try:
            st.session_state.history_df = pd.read_csv(CSV_FILE).tail(MAX_DISPLAY_ROWS)
        except:
            st.session_state.history_df = pd.DataFrame(columns=['Zaman', 'Kişi', 'Durum'])
    else:
        st.session_state.history_df = pd.DataFrame(columns=['Zaman', 'Kişi', 'Durum'])

# --- YENİ GRAFİK FONKSİYONU (AKILLI ODAKLANMA) ---
def plot_interactive_chart(df):
    if df.empty: return None
    
    # 1. Eşit Aralıklar İçin İndeks Kullanıyoruz
    fig = px.line(
        df, 
        x=df.index, 
        y="Kişi", 
        title="Zaman İçindeki Kişi Sayısı Değişimi", 
        markers=True,
        hover_data={'Kişi': True, 'Zaman': True, 'Durum': True, df.index.name: False}
    )
    
    # 2. BAŞLANGIÇ ODAĞINI AYARLA
    # Grafiği açtığında tüm 5000 veriyi göstermesin, sıkışır.
    # Sadece son 20 veriye odaklansın. Geri kalanı için alttaki çubuk kullanılsın.
    total_points = len(df)
    start_view = max(0, total_points - 20) # Son 20 nokta
    end_view = total_points
    
    fig.update_xaxes(
        # X Ekseninde sadece var olan kayıtların tarihini göster
        tickvals=df.index,
        ticktext=df['Zaman'],
        
        # --- İŞTE SİHİRLİ DOKUNUŞ ---
        # range: Başlangıçta hangi aralığın görüneceğini belirler.
        range=[start_view, end_view], 
        
        # rangeslider: Alttaki kaydırma çubuğunu açar
        rangeslider=dict(visible=True, thickness=0.10),
        
        type='category',
        tickangle=-45 # Tarihleri çapraz yap (Telefonda üst üste binmesin)
    )

    fig.update_layout(
        xaxis_title="Zaman (Veri Kayıt Noktaları)",
        yaxis_title="Kişi Sayısı",
        template="plotly_dark",
        height=550,
        # width parametresini sildik, çünkü artık zoom yaparak genişliyor!
        margin=dict(l=20, r=20, t=50, b=20),
        
        # Telefonda rahat kullanım için sürükleme modu
        dragmode="pan" 
    )
    return fig

# --- ARAYÜZ ---
st.subheader("📊 Canlı Değişim Grafiği")
metric_col = st.empty()
chart_placeholder = st.empty()
info_box = st.empty()

# --- 1. AÇILIŞ GÖSTERİMİ ---
if not st.session_state.history_df.empty:
    last_row = st.session_state.history_df.iloc[-1]
    
    with metric_col.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("Son Bilinen Kişi", last_row['Kişi'])
        c2.metric("Tarih", last_row['Zaman'])
        status_icon = "🔴" if last_row['Kişi'] > 15 else "🟢"
        c3.metric("Son Durum", f"{last_row['Durum']} {status_icon}")
    
    fig = plot_interactive_chart(st.session_state.history_df.copy())
    # use_container_width=True yaparak ekran genişliğine tam oturmasını sağlıyoruz
    chart_placeholder.plotly_chart(fig, use_container_width=True)
    
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

            # Grafiği güncelle
            fig = plot_interactive_chart(st.session_state.history_df.copy())
            chart_placeholder.plotly_chart(fig, use_container_width=True)
            
            info_box.success(f"Kayıt Eklendi: {full_time_str}")

    time.sleep(1)