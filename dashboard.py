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
MAX_DISPLAY_ROWS = 2000 

st.set_page_config(page_title="Canlı Amfi Paneli", layout="wide", page_icon="📊")

# --- SESSION STATE ---
if 'last_count' not in st.session_state:
    st.session_state.last_count = -1

# --- VERİTABANI İŞLEMLERİ ---
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
        pass
    return client

data_queue = get_message_queue()
start_mqtt()

# --- GRAFİK OLUŞTURUCU (GÜNCELLENDİ: BASAMAKLI YAPI) ---
def create_figure(df):
    if df.empty: return None, 500
    
    POINT_WIDTH_PX = 40 
    dynamic_width = max(800, len(df) * POINT_WIDTH_PX)

    fig = px.line(
        df, 
        x='Zaman', 
        y="Kişi", 
        markers=True,
        color_discrete_sequence=['#29b5e8'],
        hover_data={'Kişi': True, 'Zaman': True, 'Durum': True, 'Mod': True}
    )
    
    # --- KRİTİK DEĞİŞİKLİK: BASAMAKLI ÇİZİM ---
    # 'hv' (Horizontal-Vertical) modu: Önce yatay git, değişim anında dikey in/çık.
    # Bu sayede zoom yapınca çizgi bozulmaz, dijital sinyal gibi net durur.
    fig.update_traces(line_shape='hv', marker=dict(size=8)) 
    
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
        xaxis=dict(showgrid=True, gridcolor='#333', type='category'),
        yaxis=dict(showgrid=True, gridcolor='#333'),
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
        last_row = df.iloc[-1]
        st.session_state.last_count = int(last_row['Kişi'])

        with metric_col.container():
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Anlık Kişi", last_row['Kişi'])
            status_icon = "🔴 Kalabalık" if last_row['Durum'] == 'Crowded' else "🟢 Normal"
            c2.metric("Durum", status_icon)
            c3.metric("Son Veri", last_row['Zaman'].split(" ")[1])
            c4.metric("Aktif Mod", last_row['Mod'])

        fig, calc_width = create_figure(df)
        fig_html = fig.to_html(div_id="amfi_chart", include_plotlyjs='cdn', full_html=True, config={'displayModeBar': False, 'responsive': True})
        
        # HTML/JS (Aynı Yapı Korundu)
        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ margin: 0; background-color: #0e1117; font-family: sans-serif; }}
                #wrapper {{
                    width: 100%;
                    height: 550px;
                    position: relative;
                    border: 1px solid #333;
                    border-radius: 5px;
                    overflow-x: auto;
                    overflow-y: hidden;
                    opacity: 0;
                    transition: opacity 0.4s ease-in-out; 
                }}
                #content-box {{
                    width: {calc_width}px;
                    height: 540px;
                }}
                .zoom-controls {{
                    position: fixed; top: 20px; right: 30px; z-index: 9999; display: flex; gap: 5px;
                }}
                .btn {{
                    background: rgba(41, 181, 232, 0.2); color: #29b5e8; border: 1px solid #29b5e8;
                    border-radius: 5px; width: 30px; height: 30px; font-size: 18px; cursor: pointer;
                    display: flex; align-items: center; justify-content: center; user-select: none;
                }}
                .btn:hover {{ background: #29b5e8; color: white; }}
                .btn:active {{ background: #1a7ca0; }}
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
                var wrapper = document.getElementById("wrapper");
                var contentBox = document.getElementById("content-box");
                
                var scrollKey = "scrollPos_Tunagenc_v2";
                var widthKey = "chartWidth_Tunagenc_v2"; 

                // Zoom Yükle
                var savedWidth = sessionStorage.getItem(widthKey);
                if (savedWidth) {{
                    contentBox.style.width = savedWidth + "px";
                    var plotDiv = document.getElementById('amfi_chart');
                    if (plotDiv && window.Plotly) {{ Plotly.Plots.resize(plotDiv); }}
                }}

                // Scroll Yükle
                var savedPos = sessionStorage.getItem(scrollKey);
                if (savedPos !== null) {{
                    wrapper.scrollLeft = parseInt(savedPos);
                }} else {{
                    wrapper.scrollLeft = wrapper.scrollWidth;
                }}

                // Görünür Yap
                requestAnimationFrame(function() {{
                    wrapper.style.opacity = "1";
                }});

                // Events
                wrapper.addEventListener("scroll", function() {{
                    sessionStorage.setItem(scrollKey, wrapper.scrollLeft);
                }});

                function resizeChart(multiplier) {{
                    var currentWidth = contentBox.offsetWidth;
                    var newWidth = currentWidth * multiplier;
                    if (newWidth < 600) newWidth = 600;
                    contentBox.style.width = newWidth + "px";
                    sessionStorage.setItem(widthKey, newWidth);
                    var plotDiv = document.getElementById('amfi_chart');
                    if (plotDiv && window.Plotly) {{ Plotly.Plots.resize(plotDiv); }}
                }}
            </script>
        </body>
        </html>
        """
        
        with chart_placeholder.container():
            components.html(html_code, height=560)
            
    else:
        info_box.info("Veri bekleniyor...")

render_dashboard()

while True:
    if not data_queue.empty():
        should_refresh = False
        while not data_queue.empty():
            payload = data_queue.get()
            new_count = int(payload.get('occupancy', 0))
            status = payload.get('status', 'Normal')
            mode = payload.get('mode', 'UNKNOWN')
            
            if new_count != st.session_state.last_count:
                insert_data(new_count, status, mode)
                st.session_state.last_count = new_count
                should_refresh = True
            
        if should_refresh:
            render_dashboard()
            
    time.sleep(1)