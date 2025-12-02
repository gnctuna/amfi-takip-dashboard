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
DB_FILE = "occupancy_system.db" 
MAX_DISPLAY_ROWS = 2000 # Ekrana sığacak maksimum veri (gerisi scroll ile görülür)

st.set_page_config(page_title="Canlı Amfi Paneli", layout="wide", page_icon="📊")

# --- SESSION STATE (Anlık Değişim Kontrolü İçin) ---
if 'last_count' not in st.session_state:
    st.session_state.last_count = -1

# --- VERİTABANI İŞLEMLERİ (SQLITE) ---
def init_db():
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
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    tr_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT INTO records (timestamp, count, status, mode) VALUES (?, ?, ?, ?)",
              (tr_time, count, status, mode))
    conn.commit()
    conn.close()

def get_latest_data(limit=MAX_DISPLAY_ROWS):
    conn = sqlite3.connect(DB_FILE)
    query = f"SELECT timestamp, count, status, mode FROM records ORDER BY id DESC LIMIT {limit}"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        # Veriyi eskiden yeniye sırala (Grafik akışı için)
        df = df.iloc[::-1].reset_index(drop=True)
        df.rename(columns={'timestamp': 'Zaman', 'count': 'Kişi', 'status': 'Durum', 'mode': 'Mod'}, inplace=True)
    return df

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
            get_message_queue().put(payload)
        except Exception as e:
            print(f"MQTT Hatası: {e}")

    client = mqtt.Client()
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        client.subscribe(MQTT_TOPIC)
        client.loop_start()
    except:
        pass # Bağlantı hatası olursa sessizce geç (retry mantığı eklenebilir)
    return client

data_queue = get_message_queue()
start_mqtt()

# --- GRAFİK OLUŞTURUCU (Senin Orijinal Mantığın) ---
def create_figure(df):
    if df.empty: return None, 500
    
    # 1. Her veri noktası için piksel genişliği (Veriler sıkışmasın diye)
    POINT_WIDTH_PX = 40 
    
    # 2. Dinamik Genişlik Hesabı
    dynamic_width = max(800, len(df) * POINT_WIDTH_PX)

    fig = px.line(
        df, 
        x='Zaman', 
        y="Kişi", 
        markers=True,
        color='Mod',
        color_discrete_map={'SINIF_LIVE': '#29b5e8', 'AMFI_SNAPSHOT': '#e8295c'},
        hover_data={'Kişi': True, 'Zaman': True, 'Durum': True}
    )
    
    fig.update_layout(
        xaxis_title="", 
        yaxis_title="Kişi Sayısı",
        template="plotly_dark",
        
        # Responsive olması için width/height None bırakıyoruz
        # Boyutu dışarıdaki HTML div belirleyecek
        height=None, 
        width=None,
        autosize=True,
        
        margin=dict(l=20, r=20, t=30, b=20),
        dragmode=False, 
        paper_bgcolor='#0e1117', 
        plot_bgcolor='#0e1117',
        xaxis=dict(showgrid=True, gridcolor='#333', type='category'), # Kategori tipi önemli
        yaxis=dict(showgrid=True, gridcolor='#333'),
        legend=dict(orientation="h", y=1.1)
    )

    fig.update_xaxes(showticklabels=False, fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    
    return fig, dynamic_width

# --- ARAYÜZ ---
st.title("🏫 Akıllı Kampüs - Canlı Takip")

metric_col = st.empty()
chart_placeholder = st.empty()
info_box = st.empty()

def render_dashboard():
    df = get_latest_data()
    
    if not df.empty:
        # Metrikleri Göster
        last_row = df.iloc[-1]
        st.session_state.last_count = int(last_row['Kişi']) # Hafızayı güncelle

        with metric_col.container():
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Anlık Kişi", last_row['Kişi'])
            status_icon = "🔴 Kalabalık" if last_row['Durum'] == 'Crowded' else "🟢 Normal"
            c2.metric("Durum", status_icon)
            c3.metric("Son Veri", last_row['Zaman'].split(" ")[1])
            c4.metric("Mod", last_row['Mod'])

        # Grafiği Oluştur
        fig, calc_width = create_figure(df)
        
        # Plotly'yi HTML'e çevir
        fig_html = fig.to_html(div_id="amfi_chart", include_plotlyjs='cdn', full_html=True, config={'displayModeBar': False, 'responsive': True})
        
        # --- SENİN ORİJİNAL HTML/JS KODUN (Geri Getirildi) ---
        # Bu kod scrollbar, zoom butonları ve dinamik genişliği yönetir.
        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ margin: 0; background-color: #0e1117; font-family: sans-serif; }}
                
                /* Kapsayıcı: Scrollbar bunda çıkar */
                #wrapper {{
                    width: 100%;
                    height: 550px;
                    position: relative;
                    border: 1px solid #333;
                    border-radius: 5px;
                    overflow-x: auto; /* Yatay scroll */
                    overflow-y: hidden;
                }}

                /* İçerik Kutusu: Genişliği Python belirler */
                #content-box {{
                    width: {calc_width}px; 
                    height: 540px;
                }}

                /* Zoom Butonları */
                .zoom-controls {{
                    position: fixed; 
                    top: 20px;
                    right: 30px;
                    z-index: 9999;
                    display: flex;
                    gap: 5px;
                }}
                .btn {{
                    background: rgba(41, 181, 232, 0.2);
                    color: #29b5e8;
                    border: 1px solid #29b5e8;
                    border-radius: 5px;
                    width: 30px;
                    height: 30px;
                    font-size: 18px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .btn:hover {{ background: #29b5e8; color: white; }}
            </style>
        </head>
        <body>
            <div id="wrapper">
                <div class="zoom-controls">
                    <div class="btn" onclick="resizeChart(0.8)">-</div>
                    <div class="btn" onclick="resizeChart(1.2)">+</div>
                </div>
                <div id="content-box">
                    {fig_html}
                </div>
            </div>

            <script>
                var contentBox = document.getElementById("content-box");
                var wrapper = document.getElementById("wrapper");

                // --- ZOOM FONKSİYONU ---
                function resizeChart(multiplier) {{
                    var currentWidth = contentBox.offsetWidth;
                    var newWidth = currentWidth * multiplier;
                    if (newWidth < 600) newWidth = 600; // Minimum genişlik
                    
                    contentBox.style.width = newWidth + "px";
                    
                    // Plotly'yi yeniden boyutlandır
                    var plotDiv = document.getElementById('amfi_chart');
                    if (plotDiv && window.Plotly) {{
                        Plotly.Plots.resize(plotDiv);
                    }}
                }}

                // Sayfa açıldığında otomatik en sağa (son veriye) kaydır
                setTimeout(function() {{
                    wrapper.scrollLeft = wrapper.scrollWidth;
                }}, 300);
            </script>
        </body>
        </html>
        """
        
        with chart_placeholder.container():
            components.html(html_code, height=560)
            
    else:
        info_box.info("Veri bekleniyor...")

# --- İLK ÇALIŞTIRMA ---
render_dashboard()

# --- ANA DÖNGÜ ---
while True:
    if not data_queue.empty():
        should_refresh = False
        
        while not data_queue.empty():
            payload = data_queue.get()
            
            new_count = int(payload.get('occupancy', 0))
            status = payload.get('status', 'Normal')
            mode = payload.get('mode', 'UNKNOWN')
            
            # --- KRİTİK KONTROL: SADECE DEĞİŞİM VARSA KAYDET ---
            # Eğer gelen sayı, son bildiğimiz sayıdan farklıysa kaydet.
            # Yoksa (10, 10, 10...) boşuna veritabanını şişirme.
            if new_count != st.session_state.last_count:
                insert_data(new_count, status, mode)
                st.session_state.last_count = new_count
                should_refresh = True
            
        # Sadece yeni ve farklı veri geldiyse ekranı yenile
        if should_refresh:
            render_dashboard()
            
    time.sleep(1)