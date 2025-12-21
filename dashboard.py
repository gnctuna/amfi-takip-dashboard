import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# 1. SAYFA AYARLARI
st.set_page_config(page_title="Amfi Doluluk Paneli", layout="wide")
st.title("📊 Amfi Canlı Takip Sistemi (Google Sheets)")

# 2. BULUT BAĞLANTISI
# Secrets panelindeki linki kullanarak bağlantı kurar
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    # Google Sheets'ten veriyi oku (Sayfa ismi Sheet1)
    df = conn.read(worksheet="Sheet1")
    # Boş satırları temizle ve zaman formatını düzenle
    df = df.dropna(subset=['timestamp'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

try:
    data = load_data()

    if not data.empty:
        # 3. ÜST ÖZET KARTLARI
        last_entry = data.iloc[-1]
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Mevcut Kişi Sayısı", int(last_entry['count']))
        with col2:
            st.metric("Amfi Durumu", last_entry['status'])
        with col3:
            st.metric("Son Veri Zamanı", last_entry['timestamp'].strftime('%H:%M:%S'))

        # 4. CANLI GRAFİK (Plotly)
        st.subheader("Zaman Bazlı Doluluk Analizi")
        # Son 50 veriyi görselleştirir
        fig = px.line(data.tail(50), x="timestamp", y="count", 
                     title="Son 50 Kayıt Değişimi",
                     labels={"count": "Kişi Sayısı", "timestamp": "Zaman"},
                     template="plotly_dark") # Koyu tema Sabancı stilinde :)
        st.plotly_chart(fig, use_container_width=True)

        # 5. HAM VERİ TABLOSU
        st.subheader("Tüm Veri Akışı")
        st.dataframe(data.sort_values(by="timestamp", ascending=False), use_container_width=True)
    else:
        st.warning("Henüz tabloda veri bulunamadı. Lütfen hybrid_system.py'yi çalıştırıp veri gönderin.")

except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.info("Secrets ayarlarını ve Google Sheet başlıklarını kontrol etmeyi unutmayın.")