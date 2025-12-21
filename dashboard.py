import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# Sayfa Yapılandırması
st.set_page_config(page_title="Amfi Doluluk Paneli", layout="wide")
st.title("📊 Amfi Canlı Takip Sistemi")

# Bulut Bağlantısı
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # Veriyi Google Sheets'ten oku
    data = conn.read(worksheet="Sheet1")
    
    if not data.empty:
        # Veri temizleme ve formatlama
        data = data.dropna(subset=['timestamp'])
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        last_entry = data.iloc[-1]

        # ÜST METRİKLER (Büyük rakamlar)
        c1, c2, c3 = st.columns(3)
        c1.metric("Mevcut Kişi", int(last_entry['count']))
        c2.metric("Durum", last_entry['status'])
        c3.metric("Son Güncelleme", last_entry['timestamp'].strftime('%H:%M:%S'))

        # GRAFİK ANALİZİ (Plotly)
        st.subheader("Doluluk Değişimi (Son 50 Kayıt)")
        fig = px.line(data.tail(50), x="timestamp", y="count", 
                     labels={"count": "Kişi Sayısı", "timestamp": "Zaman"},
                     template="plotly_dark") # Koyu tema profesyonel görünür
        st.plotly_chart(fig, use_container_width=True)

        # TABLO GÖRÜNÜMÜ
        st.subheader("Geçmiş Veri Akışı")
        st.dataframe(data.sort_values(by="timestamp", ascending=False), use_container_width=True)
    else:
        st.info("Henüz veri yok. Kamera sistemini çalıştırarak veri gönderin.")

except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.info("İpucu: Secrets ayarlarındaki linki ve Google Sheet başlıklarını kontrol edin.")