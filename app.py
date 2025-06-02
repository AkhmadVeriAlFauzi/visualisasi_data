import streamlit as st
from pymongo import MongoClient
import pandas as pd
import altair as alt
import json
from datetime import datetime
import pytz
from dateutil import parser  # library yang fleksibel untuk parsing tanggal


# Koneksi MongoDB
client = MongoClient('mongodb+srv://user:OG2QqFuCYwkoWBek@capstone.fqvkpyn.mongodb.net/?retryWrites=true&w=majority')
dbcuaca = client['cuaca_db']

def convert_to_wib(utc_input):
    try:
        if not utc_input:
            return "Tidak tersedia"

        if isinstance(utc_input, str):
            dt_utc = parser.parse(utc_input)
        elif isinstance(utc_input, datetime):
            dt_utc = utc_input
        else:
            return "Format tidak dikenali"

        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=pytz.utc)

        wib = pytz.timezone('Asia/Jakarta')
        dt_wib = dt_utc.astimezone(wib)
        return dt_wib.strftime("%d %b %Y %H:%M WIB")
    except Exception as e:
        return f"Format tidak dikenali"



# Ambil semua data dari MongoDB
cuaca_data_raw = list(dbcuaca['prakiraan_cuaca'].find())

# Parsing suhu + handle error
for item in cuaca_data_raw:
    suhu_str = item.get('suhu', '0')
    try:
        item['suhu'] = int(suhu_str.split()[0])
    except:
        item['suhu'] = 0

# --- Streamlit UI ---
st.title("Visualisasi Cuaca")

# Input filter search daerah
search_daerah = st.text_input("Masukkan daerah (kota/kab/kec/kel):").lower()

# Pilih mode tampilan
mode = st.radio("Pilih Tampilan:", ('card', 'chart', 'pie', 'line', 'wordcloud'))

# Filter data sesuai search daerah
if search_daerah:
    cuaca_data = [
        item for item in cuaca_data_raw
        if search_daerah in (item.get('provinsi') or '').lower()
        or search_daerah in (item.get('kab_kota') or '').lower()
        or search_daerah in (item.get('kecamatan') or '').lower()
        or search_daerah in (item.get('kelurahan') or '').lower()
    ]
else:
    cuaca_data = cuaca_data_raw

# Convert ke DataFrame biar gampang diproses di chart
df = pd.DataFrame(cuaca_data)

if mode == 'card':
    # Tampilkan card sederhana (streamlit tidak punya card, kita gunakan expander / container)
    provinsi_groups = df.groupby('provinsi')
    for provinsi, group in provinsi_groups:
        st.header(provinsi)
        for idx, row in group.iterrows():
            suhu = row['suhu']
            icon = "☀️" if suhu >= 32 else ("⛅" if suhu >= 24 else "🌧️")
            st.markdown(f"""
                **{row.get('kab_kota', '')}**  
                {row.get('kecamatan', '')} - {row.get('kelurahan', '')}  
                Suhu: **{suhu}°C** {icon}  
                Cuaca: {row.get('cuaca', 'Tidak tersedia')}  
                Terakhir diperbarui: {convert_to_wib(row.get('timestamp'))}
            """)
            st.markdown("---")
            
elif mode == 'line':
    if df.empty:
        st.info("Data tidak ditemukan untuk filter yang diberikan.")
    else:
        st.subheader("Perubahan Suhu dari Waktu ke Waktu per Kelurahan")
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hari'] = df['timestamp'].dt.day

        for kelurahan, group in df.groupby('kelurahan'):
            st.markdown(f"### {kelurahan}")
            line_chart = alt.Chart(group).mark_line(point=True).encode(
                x=alt.X('hari:O', title='Tanggal'),
                y=alt.Y('suhu:Q', title='Suhu (°C)'),
                tooltip=['hari', 'suhu']
            ).properties(
                width=700,
                height=300
            )
            st.altair_chart(line_chart, use_container_width=True)



elif mode == 'pie':
    if df.empty:
        st.info("Data tidak ditemukan untuk filter yang diberikan.")
    else:
        st.subheader("Distribusi Jenis Cuaca")
        count_by_weather = df['cuaca'].value_counts().reset_index()
        count_by_weather.columns = ['cuaca', 'jumlah']

        pie_chart = alt.Chart(count_by_weather).mark_arc(innerRadius=50).encode(
            theta=alt.Theta(field="jumlah", type="quantitative"),
            color=alt.Color(field="cuaca", type="nominal"),
            tooltip=["cuaca", "jumlah"]
        ).properties(
            width=400,
            height=400
        )

        st.altair_chart(pie_chart, use_container_width=True)

elif mode == 'wordcloud':
    from wordcloud import WordCloud
    import matplotlib.pyplot as plt

    if df.empty:
        st.info("Data tidak ditemukan untuk filter yang diberikan.")
    else:
        st.subheader("Visualisasi Word Cloud dari Jenis Cuaca")

        text = " ".join(df['cuaca'].dropna().tolist())
        wc = WordCloud(width=800, height=400, background_color='white').generate(text)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wc, interpolation='bilinear')
        ax.axis('off')
        st.pyplot(fig)


else:
    # Mode chart: pakai Altair chart
    if df.empty:
        st.info("Data tidak ditemukan untuk filter yang diberikan.")
    else:
        # Contoh chart suhu per kecamatan, grouped by provinsi dan kab_kota
        for provinsi, prov_group in df.groupby('provinsi'):
            st.subheader(provinsi)
            for kab_kota, kab_group in prov_group.groupby('kab_kota'):
                st.markdown(f"**{kab_kota}**")
                chart = alt.Chart(kab_group).mark_bar().encode(
                    x='kecamatan:N',
                    y='suhu:Q',
                    tooltip=['kecamatan', 'suhu']
                ).properties(
                    width=600,
                    height=300
                )
                st.altair_chart(chart, use_container_width=True)
