import streamlit as st
import pandas as pd
import random
import requests
from bs4 import BeautifulSoup

# --- SETTINGS & STYLE ---
st.set_page_config(page_title="MIRU-COSMOS", layout="centered")

st.markdown("""
    <style>
    .stApp {
        background-color: #000000;
        color: #FFFFFF;
    }
    .main-title {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        color: #00FFFF;
        text-shadow: 0 0 20px #00FFFF;
        margin-bottom: 0;
    }
    .sub-title {
        text-align: center;
        color: #888888;
        font-family: monospace;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        border: 1px solid #444;
        background: linear-gradient(145deg, #1e1e1e, #111111);
        color: white;
        font-weight: bold;
        height: 3rem;
        transition: 0.3s;
    }
    .stButton>button:hover {
        border-color: #00FFFF;
        box-shadow: 0 0 15px #00FFFF;
    }
    .result-card {
        background: rgba(255, 255, 255, 0.05);
        padding: 20px;
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-top: 20px;
        text-align: center;
    }
    .pred-num {
        font-size: 2.5rem;
        font-weight: bold;
        color: #00FF00;
        letter-spacing: 5px;
        text-shadow: 0 0 10px #00FF00;
    }
    .last-res {
        color: #FF00FF;
        font-family: monospace;
        font-size: 1.2rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIC FUNCTIONS ---
def get_latest_n4():
    try:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        res = requests.get(url)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        round_num = soup.find('th', class_='alnCenter').text.strip()
        result_num = soup.find('td', class_='alnCenter').find('strong').text.strip()
        return round_num, result_num
    except:
        return "Unknown", "----"

def generate_numbers(count, length, max_val=9):
    results = []
    for _ in range(count):
        num = "".join([str(random.randint(0, max_val)) for _ in range(length)])
        results.append(num)
    return results

# --- MAIN UI ---
st.markdown('<p class="main-title">🌌 MIRU-COSMOS</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">UNIVERSAL PREDICTION CONSOLE</p>', unsafe_allow_html=True)

# Game Selection Grid
col1, col2, col3, col4 = st.columns(4)
with col1:
    btn_l7 = st.button("LOTO 7")
with col2:
    btn_l6 = st.button("LOTO 6")
with col3:
    btn_ml = st.button("MINI LOTO")
with col4:
    btn_b5 = st.button("BINGO 5")

col5, col6, col7, col8 = st.columns(4)
with col5:
    btn_n4 = st.button("Numbers 4")
with col6:
    btn_n3 = st.button("Numbers 3")
with col7:
    btn_nm = st.button("NUMBERS mini")
with col8:
    btn_ck = st.button("着せ替えクーちゃん")

st.markdown("---")

# Quantity Slider
num_count = st.slider("PREDICTION COUNT", 1, 10, 2)

# Logic Protocol Toggle
with st.expander("📖 MIRU PROTOCOL"):
    st.write("当てるために使わず、無駄な負けを消すために使う。")
    st.write("物理的乖離、重力バイアス、不自然な違和感を解析し、宇宙の展開を予測する。")

# --- EXECUTION ---
if btn_n4:
    r_idx, r_val = get_latest_n4()
    st.markdown(f'<div class="result-card">', unsafe_allow_html=True)
    st.markdown(f'<p class="last-res">LAST RESULT ({r_idx}): {r_val}</p>', unsafe_allow_html=True)
    preds = generate_numbers(num_count, 4)
    for i, p in enumerate(preds):
        st.markdown(f'<p class="pred-num">{p}</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

elif btn_n3 or btn_nm:
    st.info("Numbers 3 / Mini Logic is being synced...")

elif btn_l7 or btn_l6 or btn_ml or btn_b5 or btn_ck:
    st.info("Loto & Other systems are being synced...")

else:
    st.write("SELECT A MISSION ABOVE")
