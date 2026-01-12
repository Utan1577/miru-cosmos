import streamlit as st
import pandas as pd
import random
import requests
from bs4 import BeautifulSoup

# --- SETTINGS & SESSION STATE ---
st.set_page_config(page_title="MIRU-COSMOS", layout="centered")

if 'active_game' not in st.session_state:
    st.session_state.active_game = None

def set_game(game_name):
    st.session_state.active_game = game_name

# --- STYLING (FORCE MOBILE GRID) ---
st.markdown("""
    <style>
    /* 全体の背景と文字色 */
    .stApp {
        background-color: #050505;
        color: #FFFFFF;
    }
    
    /* スマホでも2列を強制する魔法 */
    [data-testid="column"] {
        width: 50% !important;
        flex: 1 1 50% !important;
        min-width: 50% !important;
    }
    
    /* タイトルデザイン */
    .main-title {
        font-size: 2.2rem;
        font-weight: bold;
        text-align: center;
        color: #00FFFF;
        text-shadow: 0 0 15px #00FFFF;
        margin-top: 10px;
        margin-bottom: 0;
    }
    .sub-title {
        text-align: center;
        color: #888888;
        font-size: 0.8rem;
        font-family: monospace;
        margin-bottom: 1rem;
    }

    /* ボタンのデザイン */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        border: 1px solid #444;
        background: linear-gradient(145deg, #222, #111);
        color: #ddd;
        font-weight: bold;
        height: 3.5rem;
        margin-bottom: 5px;
    }
    .stButton>button:focus {
        border-color: #00FFFF;
        color: #00FFFF;
    }

    /* 結果カードのデザイン */
    .result-box {
        background: rgba(0, 255, 255, 0.05);
        border: 1px solid rgba(0, 255, 255, 0.2);
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        margin-top: 15px;
    }
    .last-result-label {
        color: #ff00ff;
        font-size: 0.9rem;
        margin-bottom: 5px;
    }
    .prediction-number {
        font-size: 2.2rem;
        font-weight: bold;
        color: #00FF00;
        letter-spacing: 3px;
        text-shadow: 0 0 10px rgba(0, 255, 0, 0.5);
        margin: 5px 0;
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
st.markdown('<p class="sub-title">Ver. Ultimate Grid</p>', unsafe_allow_html=True)

# 2-Column Layout (Matching the Toy)
c1, c2 = st.columns(2)

with c1:
    st.button("LOTO 7", on_click=set_game, args=('L7',))
    st.button("LOTO 6", on_click=set_game, args=('L6',))
    st.button("MINI LOTO", on_click=set_game, args=('ML',))
    st.button("BINGO 5", on_click=set_game, args=('B5',))

with c2:
    st.button("Numbers 4", on_click=set_game, args=('N4',))
    st.button("Numbers 3", on_click=set_game, args=('N3',))
    st.button("NUMBERS mini", on_click=set_game, args=('NM',))
    st.button("着替クー", on_click=set_game, args=('KC',))

st.markdown("---")

# Slider & Protocol
num_count = st.slider("PREDICTION COUNT (口数)", 1, 10, 2)

with st.expander("📖 MIRU PROTOCOL (哲学)"):
    st.write("「当てるために使わず、無駄な負けを消すために使う」")
    st.write("J値（違和感）とH値（物理荒れ度）を観測し、重力バイアスを計算する。")

# --- EXECUTION & DISPLAY ---
active = st.session_state.active_game

if active:
    st.markdown(f"### 📡 SYSTEM ACTIVE: {active}")
    
    if active == 'N4':
        r_idx, r_val = get_latest_n4()
        preds = generate_numbers(num_count, 4)
        
        st.markdown('<div class="result-box">', unsafe_allow_html=True)
        st.markdown(f'<div class="last-result-label">前回結果 ({r_idx}): {r_val}</div>', unsafe_allow_html=True)
        st.markdown('<hr style="border-color: #333;">', unsafe_allow_html=True)
        for p in preds:
            st.markdown(f'<div class="prediction-number">{p}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    elif active == 'N3':
        preds = generate_numbers(num_count, 3)
        st.markdown('<div class="result-box">', unsafe_allow_html=True)
        st.markdown('<div class="last-result-label">Scanning N3 Windmills...</div>', unsafe_allow_html=True)
        for p in preds:
            st.markdown(f'<div class="prediction-number">{p}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    else:
        # Other games placeholder
        st.info(f"Connecting to {active} physical server...")
        st.markdown(f'<div class="result-box"><div class="prediction-number">SYNCING...</div></div>', unsafe_allow_html=True)

else:
    st.write("👆 SELECT A MISSION TO START")
