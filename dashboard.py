import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import json
import time
import sqlite3
import queue
import streamlit.components.v1 as components
from datetime import datetime

# --- AYARLAR ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_TOPIC = "tunagenc/occupancy"
DB_FILE = "occupancy_system.db" 
MAX_DISPLAY_CARDS = 100 

st.set_page_config(page_title="Canlı Takip Şeridi", layout="wide", page_icon="🔢")

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

def get_latest_data(limit=MAX_DISPLAY_CARDS):
    conn = sqlite3.connect(DB_FILE)
    query = f"SELECT timestamp, count, status, mode FROM records ORDER BY id DESC LIMIT {limit}"
    df = pd.read_sql_query(query, conn)
    conn.close()
    if not df.empty:
        df = df.iloc[::-1].reset_index(drop=True)
    return df

# --- YENİ FONKSİYON: ORTALAMA HESAPLAMA ---
def get_average_count():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Tüm kayıtların ortalamasını (AVG) al
    c.execute("SELECT AVG(count) FROM records")
    result = c.fetchone()[0]
    conn.close()
    # Eğer hiç veri yoksa 0 döndür, varsa 1 basamaklı float (örn: 12.5) döndür
    return result if result is not None else 0.0

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

# --- HTML KART OLUŞTURUCU ---
def generate_html_cards(df):
    cards_html = ""
    for index, row in df.iterrows():
        full_time = row['timestamp']
        date_part = full_time.split(" ")[0]
        time_part = full_time.split(" ")[1]
        try:
            date_obj = datetime.strptime(date_part, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d/%m/%Y')
        except:
            formatted_date = date_part
        count = row['count']
        
        cards_html += f"""
        <div class="card">
            <div class="card-header">Kişi Sayısı</div>
            <div class="count-value">{count}</div>
            <div class="divider"></div>
            <div class="time-info">🕒 {time_part}</div>
            <div class="date-info">📅 {formatted_date}</div>
        </div>
        """
    return cards_html

# --- ARAYÜZ ---
header_placeholder = st.empty()
timeline_placeholder = st.empty()
info_box = st.empty()

def render_dashboard():
    df = get_latest_data()
    
    if not df.empty:
        last_row = df.iloc[-1]
        current_count = int(last_row['count'])
        st.session_state.last_count = current_count
        
        # Ortalamayı Hesapla
        avg_count = get_average_count()
        
        # --- HEADER (BAŞLIK + CANLI + ORTALAMA) ---
        with header_placeholder.container():
            # Sütunları 3'e böldük: Başlık (Geniş), Canlı (Dar), Ortalama (Dar)
            c1, c2, c3 = st.columns([5, 1, 1]) 
            
            with c1:
                st.title("🔢 Canlı Veri Akışı")
            
            with c2:
                # MAVİ KUTU (Canlı)
                st.markdown(
                    f"""
                    <div style="
                        background-color: #1e1e1e;
                        border: 2px solid #29b5e8;
                        border-radius: 10px;
                        text-align: center;
                        padding: 10px;
                        margin-top: 10px;
                        box-shadow: 0 0 10px rgba(41, 181, 232, 0.3);
                    ">
                        <div style="font-size: 12px; color: #aaa; margin-bottom: -5px;">ANLIK</div>
                        <div style="font-size: 42px; font-weight: bold; color: #29b5e8;">{current_count}</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )

            with c3:
                # TURUNCU KUTU (Ortalama)
                st.markdown(
                    f"""
                    <div style="
                        background-color: #1e1e1e;
                        border: 2px solid #ff9f1c; /* Turuncu */
                        border-radius: 10px;
                        text-align: center;
                        padding: 10px;
                        margin-top: 10px;
                        box-shadow: 0 0 10px rgba(255, 159, 28, 0.3);
                    ">
                        <div style="font-size: 12px; color: #aaa; margin-bottom: -5px;">ORTALAMA</div>
                        <div style="font-size: 42px; font-weight: bold; color: #ff9f1c;">{avg_count:.1f}</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
        
        # --- KARTLAR ---
        inner_html = generate_html_cards(df)
        
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ margin: 0; background-color: #0e1117; font-family: 'Segoe UI', sans-serif; }}
                #scroll-container {{
                    display: flex; flex-direction: row; overflow-x: auto; gap: 15px; padding: 20px; padding-bottom: 10px;
                    opacity: 0; transition: opacity 0.2s ease-in;
                    scrollbar-width: thin; scrollbar-color: #29b5e8 #1e1e1e;
                }}
                #scroll-container::-webkit-scrollbar {{ height: 10px; }}
                #scroll-container::-webkit-scrollbar-track {{ background: #1e1e1e; border-radius: 5px; }}
                #scroll-container::-webkit-scrollbar-thumb {{ background: #444; border-radius: 5px; }}
                #scroll-container::-webkit-scrollbar-thumb:hover {{ background: #29b5e8; }}

                .card {{
                    background: linear-gradient(145deg, #1e1e1e, #252525); min-width: 140px; max-width: 140px;
                    border: 1px solid #333; border-radius: 12px; padding: 15px; text-align: center;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.3); color: white;
                    display: flex; flex-direction: column; justify-content: space-between;
                }}
                .card:hover {{ transform: translateY(-3px); border-color: #29b5e8; }}
                .card-header {{ font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }}
                .count-value {{ font-size: 36px; font-weight: bold; color: #29b5e8; margin: 5px 0; }}
                .divider {{ height: 1px; background: #444; margin: 10px 0; width: 100%; }}
                .time-info {{ font-size: 16px; font-weight: 600; color: #eee; margin-bottom: 2px; }}
                .date-info {{ font-size: 12px; color: #aaa; }}
            </style>
        </head>
        <body>
            <div id="scroll-container">
                {inner_html}
            </div>
            <script>
                var container = document.getElementById('scroll-container');
                var posKey = "scrollPos_Sticky_v2";
                var endKey = "isAtEnd_Sticky_v2"; 

                var wasAtEnd = sessionStorage.getItem(endKey);
                var savedPos = sessionStorage.getItem(posKey);
                
                if (wasAtEnd === "true" || wasAtEnd === null) {{
                    container.scrollLeft = container.scrollWidth;
                }} else {{
                    container.scrollLeft = parseInt(savedPos);
                }}

                requestAnimationFrame(function() {{
                    container.style.opacity = "1";
                }});

                container.addEventListener("scroll", function() {{
                    sessionStorage.setItem(posKey, container.scrollLeft);
                    var atEnd = (container.scrollLeft + container.clientWidth >= container.scrollWidth - 10);
                    sessionStorage.setItem(endKey, atEnd);
                }});
            </script>
        </body>
        </html>
        """
        with timeline_placeholder.container():
            components.html(full_html, height=240)
    else:
        info_box.info("Henüz veri yok. Bekleniyor...")

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
            
    time.sleep(0.5)