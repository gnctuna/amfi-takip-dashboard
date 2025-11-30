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
            df = pd.read_csv(CSV_FILE)
            df['Kişi'] = pd.to_numeric(df['Kişi'], errors='coerce').fillna(0).astype(int)
            st.session_state.history_df = df.tail(MAX_DISPLAY_ROWS)
        except:
            st.session_state.history_df = pd.DataFrame(columns=['Zaman', 'Kişi', 'Durum'])
    else:
        st.session_state.history_df = pd.DataFrame(columns=['Zaman', 'Kişi', 'Durum'])

# --- GRAFİK OLUŞTURUCU ---
def create_figure(df):
    if df.empty: return None
    
    POINT_WIDTH_PX = 40
    dynamic_width = max(1000, len(df) * POINT_WIDTH_PX)

    fig = px.line(
        df, 
        x=df.index, 
        y="Kişi", 
        markers=True,
        color_discrete_sequence=['#29b5e8'], # Mavi
        hover_data={'Kişi': True, 'Zaman': True, 'Durum': True, df.index.name: False}
    )
    
    fig.update_layout(
        xaxis_title="", 
        yaxis_title="Kişi Sayısı",
        template="plotly_dark",
        height=450,
        width=dynamic_width,
        margin=dict(l=20, r=20, t=30, b=20),
        dragmode=False, # Plotly sürüklemesini kapat (HTML yönetecek)
        paper_bgcolor='#0e1117', 
        plot_bgcolor='#0e1117',
        xaxis=dict(showgrid=True, gridcolor='#333'),
        yaxis=dict(showgrid=True, gridcolor='#333')
    )

    fig.update_xaxes(
        showticklabels=False, 
        rangeslider=dict(visible=False), 
        fixedrange=True, 
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
    if not st.session_state.history_df.empty:
        last_row = st.session_state.history_df.iloc[-1]
        with metric_col.container():
            c1, c2, c3 = st.columns(3)
            c1.metric("Anlık Kişi", last_row['Kişi'])
            c2.metric("Tarih", last_row['Zaman'])
            status_icon = "🔴" if last_row['Kişi'] > 15 else "🟢"
            c3.metric("Durum", f"{last_row['Durum']} {status_icon}")

        fig = create_figure(st.session_state.history_df)
        fig_html = fig.to_html(include_plotlyjs='cdn', full_html=True, config={'displayModeBar': False})
        
        # --- HTML + JS (ÇİFT SCROLLBAR SİSTEMİ) ---
        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ margin: 0; background-color: #0e1117; overflow: hidden; font-family: sans-serif; }}
                
                /* 1. DIŞ PENCERE (WRAPPER) */
                /* Bu kısım ekranda sabit durur, scrollbarlar burada çıkar */
                #chart-window {{
                    width: 100%;
                    height: 500px; /* Sabit yükseklik */
                    overflow: auto; /* Hem YATAY hem DİKEY scrollbar otomatik çıkar */
                    position: relative;
                    border: 1px solid #333;
                    border-radius: 5px;
                    -webkit-overflow-scrolling: touch; /* Mobil akıcılık */
                }}

                /* 2. İÇERİK (CONTENT) */
                /* Grafik bunun içindedir ve zoom yaptıkça bu büyür */
                #chart-content {{
                    transform-origin: 0 0;
                    /* Başlangıçta sığdır */
                }}

                /* Zoom Butonları */
                .zoom-controls {{
                    position: absolute;
                    top: 10px;
                    right: 25px; /* Scrollbarın üstüne binmesin diye biraz sola */
                    z-index: 999;
                    display: flex;
                    gap: 5px;
                }}
                
                .btn {{
                    background-color: rgba(41, 181, 232, 0.2);
                    color: #29b5e8;
                    border: 1px solid #29b5e8;
                    border-radius: 50%;
                    width: 35px;
                    height: 35px;
                    font-size: 20px;
                    font-weight: bold;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    user-select: none;
                }}
                
                .btn:active {{
                    background-color: #29b5e8;
                    color: white;
                }}

                /* Scrollbar Tasarımı */
                ::-webkit-scrollbar {{ width: 12px; height: 12px; }} /* Hem dikey hem yatay kalınlık */
                ::-webkit-scrollbar-track {{ background: #1e1e1e; }}
                ::-webkit-scrollbar-thumb {{ background: #555; border-radius: 6px; }}
                ::-webkit-scrollbar-thumb:hover {{ background: #888; }}
                /* Scrollbar köşesi (iki barın kesişimi) */
                ::-webkit-scrollbar-corner {{ background: #1e1e1e; }}
            </style>
        </head>
        <body>
            <div id="chart-window">
                <div class="zoom-controls">
                    <div class="btn" onclick="changeZoom(-0.1)">-</div>
                    <div class="btn" onclick="changeZoom(0.1)">+</div>
                </div>

                <div id="chart-content">
                    {fig_html}
                </div>
            </div>

            <script>
                var windowDiv = document.getElementById("chart-window");
                var contentDiv = document.getElementById("chart-content");
                
                var scrollXKey = "scrollX_V4";
                var scrollYKey = "scrollY_V4";
                var zoomKey = "zoomLevel_V4";

                // --- ZOOM FONKSİYONLARI ---
                var currentZoom = parseFloat(sessionStorage.getItem(zoomKey)) || 1.0;
                
                function applyZoom() {{
                    contentDiv.style.zoom = currentZoom; 
                    // Firefox desteği için gerekirse transform scale eklenebilir ama zoom genelde yeterli
                    sessionStorage.setItem(zoomKey, currentZoom);
                }}
                
                function changeZoom(delta) {{
                    currentZoom += delta;
                    if (currentZoom < 0.2) currentZoom = 0.2;
                    if (currentZoom > 4.0) currentZoom = 4.0;
                    applyZoom();
                }}
                
                applyZoom(); // Başlangıçta uygula

                // --- HAFIZALI SCROLL (HEM YATAY HEM DİKEY) ---
                var savedX = sessionStorage.getItem(scrollXKey);
                var savedY = sessionStorage.getItem(scrollYKey);
                
                setTimeout(function() {{
                    // YATAY KONUM
                    if (savedX !== null) {{
                        windowDiv.scrollLeft = parseInt(savedX);
                    }} else {{
                        windowDiv.scrollLeft = windowDiv.scrollWidth; // En sağa git
                    }}

                    // DİKEY KONUM
                    if (savedY !== null) {{
                        windowDiv.scrollTop = parseInt(savedY);
                    }}
                }}, 100);

                // Kaydettikçe hafızaya at
                windowDiv.addEventListener("scroll", function() {{
                    sessionStorage.setItem(scrollXKey, windowDiv.scrollLeft);
                    sessionStorage.setItem(scrollYKey, windowDiv.scrollTop);
                }});
            </script>
        </body>
        </html>
        """
        
        # height=520 yaptık ki scrollbarlar rahat görünsün
        with chart_placeholder.container():
            components.html(html_code, height=520)

# --- İLK AÇILIŞ ---
if not st.session_state.history_df.empty:
    render_dashboard()
else:
    info_box.warning("Veri bekleniyor...")

# --- ANA DÖNGÜ ---
while True:
    if not data_queue.empty():
        
        if not st.session_state.history_df.empty:
            running_last_count = int(st.session_state.history_df.iloc[-1]['Kişi'])
        else:
            running_last_count = -1 
            
        changes_detected = False
        skipped_count = 0
        
        while not data_queue.empty():
            payload = data_queue.get()
            new_count = int(payload['occupancy'])
            status = payload.get('status', 'Normal')
            
            if new_count != running_last_count:
                tr_now = datetime.now() + timedelta(hours=3)
                full_time_str = tr_now.strftime('%Y-%m-%d %H:%M:%S')
                
                new_data = {"Zaman": full_time_str, "Kişi": new_count, "Durum": status}
                new_row_df = pd.DataFrame([new_data])
                st.session_state.history_df = pd.concat([st.session_state.history_df, new_row_df], ignore_index=True)
                
                write_header = not os.path.exists(CSV_FILE)
                new_row_df.to_csv(CSV_FILE, mode='a', header=write_header, index=False)
                
                running_last_count = new_count 
                changes_detected = True
            else:
                skipped_count += 1
        
        if changes_detected:
            render_dashboard()
            info_box.success(f"Yeni Veri Eklendi! (Atlanan Tekrar: {skipped_count})")
        elif skipped_count > 0:
            info_box.info(f"Sistem aktif. {skipped_count} adet aynı veri filtrelendi.")

    time.sleep(0.1)