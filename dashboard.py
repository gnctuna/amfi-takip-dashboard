import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime
import queue

# --- AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"

st.set_page_config(page_title="Canlı Amfi Paneli", layout="wide")
st.title("🏫 Akıllı Amfi Takip Sistemi (Canlı)")

# --- GLOBAL DEĞİŞKENLER (STREAMLIT DIŞI) ---
# Bu teknik çok önemlidir. @st.cache_resource kullanarak
# değişkeni Streamlit'in yenilemelerinden koruyoruz.
@st.cache_resource
def get_message_queue():
    return queue.Queue()

# Posta kutusunu al
data_queue = get_message_queue()

# --- MQTT AYARLARI ---
def on_message(client, userdata, message):
    try:
        # BURASI ÇOK ÖNEMLİ:
        # Burada ASLA 'st.' ile başlayan bir kod kullanmıyoruz.
        # Sadece standart Python queue kullanıyoruz.
        payload = json.loads(message.payload.decode())
        
        # Kutuyu çağırmak için global değişkene değil, cache fonksiyonuna gidiyoruz
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

# MQTT'yi Başlat
start_mqtt()

# --- VERİ LİSTESİ (Session State) ---
if 'history' not in st.session_state:
    st.session_state.history = []

# --- ARAYÜZ YER TUTUCULARI ---
metric_col = st.empty()
chart_col = st.empty()
info_box = st.empty()

# --- ANA DÖNGÜ ---
# Toast mesajı sadece bir kere görünsün
if 'started' not in st.session_state:
    st.toast("Sistem Başlatıldı. Veri bekleniyor...")
    st.session_state.started = True

while True:
    # 1. Posta Kutusunu Kontrol Et
    # Streamlit'in ana döngüsü (Main Thread) kutuya bakar
    while not data_queue.empty():
        payload = data_queue.get()
        
        # Veriyi işle
        current_time = datetime.now().strftime('%H:%M:%S')
        new_entry = {
            "Saat": current_time,
            "Kişi": payload['occupancy'],
            "Durum": payload.get('status', 'Normal')
        }
        
        # Streamlit hafızasına ekle (Bunu sadece ana thread yapabilir)
        st.session_state.history.append(new_entry)
        
        # Listeyi temiz tut (Son 50 veri)
        if len(st.session_state.history) > 50:
            st.session_state.history.pop(0)

    # 2. Ekranı Güncelle
    if len(st.session_state.history) > 0:
        last_entry = st.session_state.history[-1]
        
        with metric_col.container():
            c1, c2, c3 = st.columns(3)
            c1.metric("Anlık Kişi", last_entry['Kişi'])
            c2.metric("Güncelleme", last_entry['Saat'])
            
            durum_ikon = "🔴" if last_entry['Kişi'] > 15 else "🟢"
            c3.metric("Durum", f"{last_entry['Durum']} {durum_ikon}")

        # Grafik
        df = pd.DataFrame(st.session_state.history)
        chart_col.line_chart(df.set_index("Saat")['Kişi'])
        
        info_box.success(f"Bağlantı Aktif ✅ Son Veri: {last_entry['Saat']}")
        
    else:
        info_box.info("Veri bekleniyor... Simülatörü kontrol et.")

    # İşlemciyi yormamak için bekle
    time.sleep(1)