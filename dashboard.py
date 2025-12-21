import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# 1. SAYFA AYARLARI
st.set_page_config(page_title="Amfi Doluluk Paneli", layout="wide")
st.title("📊 Amfi Canlı Takip Sistemi")

# 2. BULUT BAĞLANTISI (Secrets'tan linki okur)
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    # Google Sheets'ten veriyi oku (Sayfa ismi Sheet1)
    df = conn.read(worksheet="Sheet1")
    # Zaman damgasını Python formatına çevir
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

try:
    data = load_data()

    # 3. ÖZET KARTLARI (En üstte duran büyük rakamlar)
    last_entry = data.iloc[-1]
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Mevcut Kişi Sayısı", int(last_entry['count']))
    with col2:
        st.metric("Durum", last_entry['status'])
    with col3:
        st.metric("Son Güncelleme", last_entry['timestamp'].strftime('%H:%M:%S'))

    # 4. GRAFİKLER
    st.subheader("Zaman Çizelgesi")
    # Son 50 veriyi çizgi grafik olarak göster
    fig = px.line(data.tail(50), x="timestamp", y="count", 
                 title="Doluluk Değişimi (Son 50 Kayıt)",
                 labels={"count": "Kişi Sayısı", "timestamp": "Zaman"})
    st.plotly_chart(fig, use_container_width=True)

    # 5. VERİ TABLOSU
    st.subheader("Ham Veri Akışı (Son 1000 Kayıt)")
    st.dataframe(data.sort_values(by="timestamp", ascending=False), use_container_width=True)

except Exception as e:
    st.error(f"Veri yüklenirken bir hata oluştu: {e}")
    st.info("İpucu: Google Sheet tablonuzdaki başlıkların 'timestamp', 'count', 'status', 'mode' olduğundan emin olun.")