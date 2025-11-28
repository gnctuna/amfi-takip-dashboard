import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime, timedelta
import queue
import os 
import plotly.express as px # <-- YENİ GRAFİK MOTORU

# --- AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"
CSV_FILE = "history_v2.csv" 

st.set_page_config(page_title="Canlı Amfi Paneli", layout="wide")

# --- YAN MENÜ ---
with st.sidebar:
    st.header("⚙️ Panel Ayarları")
    st.info("Grafik artık interaktif! Altındaki çubuğu kullanarak geçmişe gidebilir veya zoom yapabilirsin.")
    
    # Performans için güvenlik kilidi
    # Çok fazla veri (10.000+) tarayıcıyı dondurabilir, o yüzden limit koyuyoruz.
    max_rows = st.slider("Hafızadan Yüklenecek Maksimum Veri", 100, 5000, 1000)
    
    if st.button("Verileri Temizle (Sıfırla)"):
        if os.path.exists(CSV_FILE):
            os.remove(CSV_FILE)
            st.session_state.history_df = pd.DataFrame(columns=['Zaman', 'Kişi', 'Durum'])
            st.rerun()

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

# --- MQTT ---
@st.cache_resource
def get_message_queue():
    return queue.Queue()

data_queue = get_message_queue()

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

# --- ARAYÜZ ---
metric_col = st.empty()
st.subheader("📊 Canlı Değişim Grafiği (İnteraktif)")
chart_placeholder = st.empty() # Grafiğin duracağı yer
info_box = st.empty()

# --- GRAFİK ÇİZME FONKSİYONU ---
def plot_interactive_chart(df):
    if df.empty: return None
    
    # Plotly ile çizgi grafik
    fig = px.line(df, x="Zaman", y="Kişi", title="Zaman İçindeki Değişim", markers=True)
    
    # Grafiği Güzelleştir
    fig.update_layout(
        xaxis_title="Saat/Tarih",
        yaxis_title="Kişi Sayısı",
        xaxis=dict(rangeslider=dict(visible=True)), # <-- İŞTE SİHİR BURADA (KAYDIRMA ÇUBUĞU)
        template="plotly_dark" # Karanlık mod
    )
    return fig

# İlk Yükleme
if not st.session_state.history_df.empty:
    last_row = st.session_state.history_df.iloc[-1]
    with metric_col.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("Son Bilinen Kişi", last_row['Kişi'])
        c2.metric("Son Güncelleme", last_row['Zaman'])
        status_icon = "🔴" if last_row['Kişi'] > 15 else "🟢"
        c3.metric("Son Durum", f"{last_row['Durum']} {status_icon}")
    
    # Sadece son 'max_rows' kadarını al (Performans için) ama hepsi zoomlanabilir
    display_df = st.session_state.history_df.tail(max_rows)
    fig = plot_interactive_chart(display_df)
    chart_placeholder.plotly_chart(fig, use_container_width=True)
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
            
            # Arayüz Güncelle
            with metric_col.container():
                c1, c2, c3 = st.columns(3)
                c1.metric("Anlık Kişi", new_count, delta="Değişim Var 🔔")
                c2.metric("Zaman (TR)", full_time_str)
                icon = "🔴" if new_count > 15 else "🟢"
                c3.metric("Durum", f"{status} {icon}")

            # İNTERAKTİF GRAFİĞİ GÜNCELLE
            display_df = st.session_state.history_df.tail(max_rows)
            fig = plot_interactive_chart(display_df)
            
            # 'key' parametresi sayesinde grafiği komple yeniden çizmeden güncelleriz
            chart_placeholder.plotly_chart(fig, use_container_width=True, key=f"chart_{len(st.session_state.history_df)}")
            
            info_box.success(f"Kayıt Eklendi: {full_time_str}")

    time.sleep(1)