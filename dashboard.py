import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import json
import time
import sqlite3
import queue
import plotly.express as px
import streamlit.components.v1 as components
from datetime import datetime

# --- AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"
DB_FILE = "occupancy_system.db"  # CSV yerine .db dosyası
MAX_DISPLAY_ROWS = 1000  # Grafikte gösterilecek son X veri

st.set_page_config(page_title="Canlı Amfi Paneli", layout="wide", page_icon="📊")

# --- VERİTABANI İŞLEMLERİ (SQLITE) ---
def init_db():
    """Veritabanı ve tablo yoksa oluşturur."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS records
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  count INTEGER,
                  status TEXT,
                  mode TEXT)''')
    conn.commit()
    conn.close()

def insert_data(count, status, mode):
    """Yeni veriyi veritabanına ekler."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Şu anki zamanı al
    tr_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT INTO records (timestamp, count, status, mode) VALUES (?, ?, ?, ?)",
              (tr_time, count, status, mode))
    conn.commit()
    conn.close()

def get_latest_data(limit=MAX_DISPLAY_ROWS):
    """Veritabanından son verileri çeker."""
    conn = sqlite3.connect(DB_FILE)
    # SQL sorgusu ile sadece son 1000 veriyi çekiyoruz (Çok hızlıdır)
    query = f"SELECT timestamp, count, status, mode FROM records ORDER BY id DESC LIMIT {limit}"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Veriler ters geldiği için düzeltiyoruz (Eskiden yeniye)
    if not df.empty:
        df = df.iloc[::-1].reset_index(drop=True)
        df.rename(columns={'timestamp': 'Zaman', 'count': 'Kişi', 'status': 'Durum', 'mode': 'Mod'}, inplace=True)
    return df

# Başlangıçta veritabanını kur
init_db()

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
            print(f"MQTT Hata: {e}")

    client = mqtt.Client()
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        client.subscribe(MQTT_TOPIC)
        client.loop_start()
    except Exception as e:
        print(f"Bağlantı Hatası: {e}")
    return client

data_queue = get_message_queue()
start_mqtt()

# --- GRAFİK OLUŞTURUCU ---
def create_figure(df):
    if df.empty: return None, 500
    
    # Genişlik hesabı
    POINT_WIDTH_PX = 30
    dynamic_width = max(800, len(df) * POINT_WIDTH_PX)

    fig = px.line(
        df, 
        x='Zaman', 
        y="Kişi", 
        markers=True,
        color='Mod', # Çizgi rengi Moda göre değişsin (Sınıf/Amfi)
        color_discrete_map={'SINIF_LIVE': '#29b5e8', 'AMFI_SNAPSHOT': '#e8295c'},
        hover_data={'Kişi': True, 'Zaman': True, 'Durum': True}
    )
    
    fig.update_layout(
        xaxis_title="", 
        yaxis_title="Kişi Sayısı",
        template="plotly_dark",
        height=None, 
        width=None,
        autosize=True,
        margin=dict(l=20, r=20, t=30, b=20),
        dragmode=False, 
        paper_bgcolor='#0e1117', 
        plot_bgcolor='#0e1117',
        xaxis=dict(showgrid=True, gridcolor='#333'),
        yaxis=dict(showgrid=True, gridcolor='#333'),
        legend=dict(orientation="h", y=1.1)
    )

    fig.update_xaxes(showticklabels=False, fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    
    return fig, dynamic_width

# --- ARAYÜZ ---
st.title("🏫 Akıllı Kampüs Yoğunluk Takibi")

# Üst metrik kutuları
metric_col = st.empty()
chart_placeholder = st.empty()
info_box = st.empty()

def render_dashboard():
    # Veritabanından veriyi çek
    df = get_latest_data()
    
    if not df.empty:
        last_row = df.iloc[-1]
        
        with metric_col.container():
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Anlık Kişi", last_row['Kişi'])
            
            # Durum İkonu
            if last_row['Durum'] == 'Crowded':
                icon = "🔴 Kalabalık"
            else:
                icon = "🟢 Normal"
            c2.metric("Doluluk Durumu", icon)
            
            c3.metric("Son Güncelleme", last_row['Zaman'].split(" ")[1])
            c4.metric("Aktif Mod", last_row['Mod'])

        # Grafiği oluştur
        fig, calc_width = create_figure(df)
        
        # HTML/JS Enjeksiyonu (Kaydırmalı Grafik İçin)
        if fig:
            fig_html = fig.to_html(div_id="amfi_chart", include_plotlyjs='cdn', full_html=True, config={'displayModeBar': False, 'responsive': True})
            html_code = f"""
            <div id="wrapper" style="overflow-x: auto; border: 1px solid #333; border-radius: 5px; height: 500px; position: relative;">
                <div id="content-box" style="width: {calc_width}px; height: 480px;">
                    {fig_html}
                </div>
                <script>
                    // Otomatik en sağa kaydırma
                    var wrapper = document.getElementById("wrapper");
                    setTimeout(function() {{
                        wrapper.scrollLeft = wrapper.scrollWidth;
                    }}, 500);
                </script>
            </div>
            """
            with chart_placeholder.container():
                components.html(html_code, height=520)
    else:
        info_box.info("Henüz veri yok. Sistem bekleniyor...")

# --- İLK AÇILIŞ ---
render_dashboard()

# --- ANA DÖNGÜ (Canlı Veri Dinleme) ---
while True:
    # Kuyrukta yeni veri var mı?
    if not data_queue.empty():
        while not data_queue.empty():
            payload = data_queue.get()
            
            # Veriyi parçala
            count = int(payload.get('occupancy', 0))
            status = payload.get('status', 'Normal')
            mode = payload.get('mode', 'UNKNOWN')
            
            # 1. SQLITE VERİTABANINA YAZ (Artık CSV yok)
            insert_data(count, status, mode)
            
        # 2. EKRANI GÜNCELLE
        render_dashboard()
        
    time.sleep(1) # İşlemciyi yormamak için bekleme