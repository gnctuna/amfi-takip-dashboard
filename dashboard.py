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

# --- GRAFİK OLUŞTURUCU (Normal Zaman Akışı) ---
def create_figure(df):
    if df.empty: return None
    
    POINT_WIDTH_PX = 35
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
        dragmode="pan",
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
        
        # --- İŞTE SİHİRLİ JAVASCRIPT ---
        # Bu kod tarayıcının hafızasına (sessionStorage) scroll konumunu kaydeder.
        # Sayfa yenilendiğinde oradan okuyup geri yükler.
        html_code = f"""
        <html>
        <head>
            <style>
                body {{ margin: 0; background-color: #0e1117; }}
                ::-webkit-scrollbar {{ height: 12px; }}
                ::-webkit-scrollbar-track {{ background: #1e1e1e; }}
                ::-webkit-scrollbar-thumb {{ background: #555; border-radius: 6px; }}
                ::-webkit-scrollbar-thumb:hover {{ background: #888; }}
            </style>
        </head>
        <body>
            <div id="chart-container" style="width: 100%; overflow-x: auto; padding-bottom: 5px;">
                {fig_html}
            </div>
            <script>
                var container = document.getElementById("chart-container");
                var storageKey = "scrollPos_Amfi_V1"; // Hafıza Anahtarı

                // 1. GERİ YÜKLEME: Sayfa açılır açılmaz hafızaya bak
                var savedPos = sessionStorage.getItem(storageKey);
                
                if (savedPos !== null) {{
                    // Eğer hafızada kayıt varsa oraya git
                    container.scrollLeft = parseInt(savedPos);
                }} else {{
                    // İlk defa açılıyorsa EN SONA (Sağa) git
                    container.scrollLeft = container.scrollWidth;
                }}

                // 2. KAYDETME: Sen kaydırdıkça hafızayı güncelle
                container.onscroll = function() {{
                    sessionStorage.setItem(storageKey, container.scrollLeft);
                }};
            </script>
        </body>
        </html>
        """
        
        with chart_placeholder.container():
            components.html(html_code, height=480, scrolling=True)

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