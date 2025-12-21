import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import streamlit.components.v1 as components
import time

# --- AYARLAR ---
st.set_page_config(page_title="Canlı Takip Şeridi", layout="wide", page_icon="🔢")

# --- GOOGLE SHEETS BAĞLANTISI ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        # ttl=0: Her seferinde güncel veriyi çek
        df = conn.read(worksheet="Sheet1", ttl=0)
        
        # Tarih formatını düzelt
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Veriyi önce YENİDEN ESKİYE sırala (ki en son gelenleri alabilelim)
        df = df.sort_values(by='timestamp', ascending=False)
        return df
    except Exception as e:
        st.error(f"Veri çekme hatası: {e}")
        return pd.DataFrame()

# --- HTML KART OLUŞTURUCU ---
def generate_html_cards(df):
    cards_html = ""
    # Dataframe buraya "Eskiden -> Yeniye" sıralı gelecek
    for index, row in df.iterrows():
        ts = row['timestamp']
        date_part = ts.strftime('%d/%m/%Y')
        time_part = ts.strftime('%H:%M:%S')
        count = int(row['count'])
        
        cards_html += f"""
        <div class="card">
            <div class="card-header">Kişi Sayısı</div>
            <div class="count-value">{count}</div>
            <div class="divider"></div>
            <div class="time-info">🕒 {time_part}</div>
            <div class="date-info">📅 {date_part}</div>
        </div>
        """
    return cards_html

# --- ARAYÜZ ---
def render_dashboard():
    # Başlık Alanı
    c1, c2 = st.columns([6, 2])
    with c1:
        st.title("🔢 Canlı Veri Akışı")
    with c2:
        # Otomatik Yenileme Anahtarı
        auto_refresh = st.toggle('🔴 Canlı İzle (Oto-Yenile)', value=True)

    # Veriyi Çek (En Yeniler En Üstte)
    df = get_data()

    if not df.empty:
        # 1. Büyük Kutular İçin: En son gelen veriyi al (Listenin başı)
        last_row = df.iloc[0] 
        current_count = int(last_row['count'])
        avg_count = df['count'].mean()
        
        # 2. Kartlar İçin: Son 50 veriyi al, ama TERS ÇEVİR (Eskiden Yeniye)
        # Böylece en yeni veri EN SAĞDA olur.
        df_cards = df.head(50).sort_values(by='timestamp', ascending=True)

        # --- İSTATİSTİK KUTULARI ---
        c_stat1, c_stat2, c_space = st.columns([1, 1, 4])
        
        with c_stat1:
            st.markdown(
                f"""
                <div style="
                    background-color: #1e1e1e;
                    border: 2px solid #29b5e8;
                    border-radius: 10px;
                    text-align: center;
                    padding: 15px;
                    box-shadow: 0 0 15px rgba(41, 181, 232, 0.2);
                ">
                    <div style="font-size: 14px; color: #aaa; margin-bottom: 5px;">ANLIK</div>
                    <div style="font-size: 48px; font-weight: bold; color: #29b5e8;">{current_count}</div>
                </div>
                """, 
                unsafe_allow_html=True
            )

        with c_stat2:
            st.markdown(
                f"""
                <div style="
                    background-color: #1e1e1e;
                    border: 2px solid #ff9f1c; /* Turuncu */
                    border-radius: 10px;
                    text-align: center;
                    padding: 15px;
                    box-shadow: 0 0 15px rgba(255, 159, 28, 0.2);
                ">
                    <div style="font-size: 14px; color: #aaa; margin-bottom: 5px;">ORTALAMA</div>
                    <div style="font-size: 48px; font-weight: bold; color: #ff9f1c;">{avg_count:.1f}</div>
                </div>
                """, 
                unsafe_allow_html=True
            )
        
        # --- YATAY KAYDIRMALI KARTLAR ---
        st.write("") 
        st.markdown("### 📜 Geçmiş Kayıtlar (Sola Doğru Eski)")
        
        inner_html = generate_html_cards(df_cards)
        
        # Javascript ekledik: "container.scrollLeft = container.scrollWidth"
        # Bu kod, sayfa yüklendiğinde çubuğu en sona (en sağa) iter.
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ margin: 0; background-color: transparent; font-family: 'Segoe UI', sans-serif; }}
                #scroll-container {{
                    display: flex; flex-direction: row; overflow-x: auto; gap: 15px; padding: 20px; padding-bottom: 10px;
                    scrollbar-width: thin; scrollbar-color: #29b5e8 #1e1e1e;
                    scroll-behavior: smooth; /* Yumuşak kaydırma */
                }}
                #scroll-container::-webkit-scrollbar {{ height: 8px; }}
                #scroll-container::-webkit-scrollbar-track {{ background: #1e1e1e; border-radius: 4px; }}
                #scroll-container::-webkit-scrollbar-thumb {{ background: #444; border-radius: 4px; }}
                #scroll-container::-webkit-scrollbar-thumb:hover {{ background: #29b5e8; }}

                .card {{
                    background: linear-gradient(145deg, #1e1e1e, #252525); 
                    min-width: 140px; max-width: 140px;
                    border: 1px solid #333; border-radius: 12px; padding: 15px; text-align: center;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.3); color: white;
                    display: flex; flex-direction: column; justify-content: space-between;
                }}
                .card:hover {{ transform: translateY(-3px); border-color: #29b5e8; transition: 0.3s; }}
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
                // Sayfa yüklendiğinde en sağa (son veriye) git
                var container = document.getElementById('scroll-container');
                container.scrollLeft = container.scrollWidth;
            </script>
        </body>
        </html>
        """
        components.html(full_html, height=260)

    else:
        st.info("Henüz veri yok. Kamera sistemini çalıştırarak veri gönderin.")

    # Otomatik Yenileme
    if auto_refresh:
        time.sleep(5)
        st.rerun()

if __name__ == "__main__":
    render_dashboard()