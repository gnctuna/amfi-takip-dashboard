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
    
    # Python tarafında başlangıç genişliği hesabı
    # Ama asıl kontrolü HTML/JS tarafına bırakacağız
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
        
        # Yükseklik ve Genişliği 'None' yapıyoruz ki, 
        # dışarıdaki HTML kutusu ne kadar büyürse grafik de o kadar büyüsün (Responsive)
        height=None, 
        width=None,
        autosize=True,
        
        margin=dict(l=20, r=20, t=30, b=20),
        dragmode=False, 
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
    return fig, dynamic_width

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

        # Grafiği oluştur (fig ve genişlik dönüyor)
        fig, calc_width = create_figure(st.session_state.history_df)
        
        # Grafiğe SABİT bir ID veriyoruz: "amfi_chart"
        # Böylece JavaScript ile bu grafiği bulup boyutunu değiştirebileceğiz.
        fig_html = fig.to_html(div_id="amfi_chart", include_plotlyjs='cdn', full_html=True, config={'displayModeBar': False, 'responsive': True})
        
        # HTML Kodu
        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ margin: 0; background-color: #0e1117; overflow: hidden; font-family: sans-serif; }}
                
                /* 1. DIŞ PENCERE */
                #wrapper {{
                    width: 100%;
                    height: 550px; /* Pencere yüksekliği sabit */
                    position: relative;
                    border: 1px solid #333;
                    border-radius: 5px;
                    /* Hem Yatay Hem Dikey Scrollbar Çıksın */
                    overflow: auto; 
                    -webkit-overflow-scrolling: touch;
                }}

                /* 2. İÇERİK KUTUSU */
                #content-box {{
                    /* Başlangıç genişliği Python'dan geliyor */
                    width: {calc_width}px; 
                    height: 520px; /* Grafiğin yüksekliği */
                }}

                /* SABİT BUTONLAR (Ekrana Çivili) */
                .zoom-controls {{
                    position: fixed; 
                    top: 15px;
                    right: 25px;
                    z-index: 99999;
                    display: flex;
                    gap: 8px;
                    padding: 5px;
                    background-color: rgba(14, 17, 23, 0.7);
                    border-radius: 20px;
                }}
                
                .btn {{
                    background-color: rgba(41, 181, 232, 0.1);
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
                .btn:active {{ background-color: #29b5e8; color: white; }}

                /* Scrollbar */
                ::-webkit-scrollbar {{ width: 12px; height: 12px; }}
                ::-webkit-scrollbar-track {{ background: #1e1e1e; }}
                ::-webkit-scrollbar-thumb {{ background: #555; border-radius: 6px; }}
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
                
                var scrollXKey = "scrollX_TrueResize_V1";
                var widthKey = "chartWidth_TrueResize_V1";
                
                // Başlangıç genişliği (Python'dan gelen değer)
                var baseWidth = {calc_width}; 

                // --- RESIZE FONKSİYONU ---
                // Zoom değil, gerçekten genişliği değiştiriyoruz.
                function resizeChart(multiplier) {{
                    // Mevcut genişliği al
                    var currentWidth = contentBox.offsetWidth;
                    var newWidth = currentWidth * multiplier;
                    
                    // Sınırlar (En az 500px, En çok 50.000px)
                    if (newWidth < 500) newWidth = 500;
                    if (newWidth > 50000) newWidth = 50000;
                    
                    // 1. Kutunun genişliğini değiştir
                    contentBox.style.width = newWidth + "px";
                    
                    // 2. Plotly'ye "Yeniden Çiz" emri ver (BU ÇOK ÖNEMLİ)
                    // Bu sayede koordinatlar güncellenir ve Tooltip çalışır.
                    var plotDiv = document.getElementById('amfi_chart');
                    if (plotDiv && window.Plotly) {{
                        Plotly.Plots.resize(plotDiv);
                    }}
                    
                    // Hafızaya kaydet
                    sessionStorage.setItem(widthKey, newWidth);
                }}

                // --- HAFIZA YÖNETİMİ ---
                // 1. Kaydedilmiş genişliği geri yükle
                var savedWidth = sessionStorage.getItem(widthKey);
                if (savedWidth) {{
                     contentBox.style.width = savedWidth + "px";
                }}

                // 2. Kaydedilmiş Scroll Konumunu geri yükle
                var savedX = sessionStorage.getItem(scrollXKey);
                setTimeout(function() {{
                    // Plotly'nin çizilmesi için minik bekleme
                    var plotDiv = document.getElementById('amfi_chart');
                    if (plotDiv && window.Plotly) {{ Plotly.Plots.resize(plotDiv); }}

                    if (savedX !== null) {{
                        wrapper.scrollLeft = parseInt(savedX);
                    }} else {{
                        wrapper.scrollLeft = wrapper.scrollWidth;
                    }}
                }}, 200);

                // Scroll dinleyicisi
                wrapper.addEventListener("scroll", function() {{
                    sessionStorage.setItem(scrollXKey, wrapper.scrollLeft);
                }});
            </script>
        </body>
        </html>
        """
        
        with chart_placeholder.container():
            components.html(html_code, height=560) # Yüksekliği biraz artırdık

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