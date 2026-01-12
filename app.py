import streamlit as st
import random
import requests
from bs4 import BeautifulSoup

# --- 1. 究極の画面固定設定 ---
st.set_page_config(page_title="MIRU-DASH", layout="centered")

# --- 2. CSS: 1画面にすべてを閉じ込める魔法 ---
st.markdown("""
    <style>
    /* 背景と文字色 */
    .stApp {
        background-color: #000000 !important;
        overflow: hidden; /* スクロール禁止 */
    }
    .block-container {
        padding: 10px !important;
    }
    
    /* 液晶モニター (数字を絶対に外に出さない) */
    .lcd-monitor {
        background-color: #9ea7a6;
        border: 4px solid #444;
        border-radius: 8px;
        height: 200px;
        width: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        box-sizing: border-box;
        margin-bottom: 10px;
        box-shadow: inset 0 0 15px rgba(0,0,0,0.5);
    }
    .lcd-label {
        font-family: monospace;
        font-size: 10px;
        color: #333;
        margin-bottom: 2px;
    }
    .lcd-last {
        font-family: monospace;
        font-size: 18px;
        color: #222;
        background: rgba(255,255,255,0.2);
        padding: 2px 10px;
        border-radius: 4px;
        margin-bottom: 10px;
    }
    .lcd-pred-container {
        display: flex;
        flex-direction: column;
        gap: 5px;
    }
    .lcd-pred-num {
        font-family: 'Courier New', monospace;
        font-size: 32px;
        font-weight: bold;
        color: #000;
        letter-spacing: 5px;
        line-height: 1.0;
    }

    /* 強制2列ボタン */
    div[data-testid="column"] {
        width: 50% !important;
        flex: 1 1 50% !important;
        min-width: 50% !important;
    }
    .stButton > button {
        width: 100% !important;
        height: 55px !important;
        background-color: #222 !important;
        color: white !important;
        border: 1px solid #444 !important;
        border-radius: 6px !important;
        font-weight: bold !important;
    }
    .stButton > button:active {
        background-color: #00FF00 !important;
        color: black !important;
    }
    
    /* スライダーの圧縮 */
    .stSlider {
        margin-top: -10px !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. ロジック部 ---
if 'g' not in st.session_state: st.session_state.g = 'N4'
if 'c' not in st.session_state: st.session_state.c = 2

def set_g(name): st.session_state.g = name

def get_last(g):
    if g == 'N4':
        try:
            url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
            res = requests.get(url)
            res.encoding = 'Shift_JIS'
            soup = BeautifulSoup(res.text, 'html.parser')
            idx = soup.find('th', class_='alnCenter').text.strip()
            val = soup.find('td', class_='alnCenter').find('strong').text.strip()
            return f"{idx}: {val}"
        except: return "取得中..."
    return "----"

def gen_nums(g, c):
    l = 4 if g == 'N4' else (3 if g in ['N3','NM'] else 4)
    return ["".join([str(random.randint(0,9)) for _ in range(l)]) for _ in range(c)]

# --- 4. 描画 ---
st.markdown("<h3 style='text-align: center; color: #00FFFF; margin: 0;'>MIRU-COSMOS</h3>", unsafe_allow_html=True)

# 液晶モニター
last_res = get_last(st.session_state.g)
preds = gen_nums(st.session_state.g, st.session_state.c)
preds_html = "".join([f'<div class="lcd-pred-num">{p}</div>' for p in preds])

st.markdown(f"""
<div class="lcd-monitor">
    <div class="lcd-label">LAST RESULT ({st.session_state.g})</div>
    <div class="lcd-last">{last_res}</div>
    <div style="border-top:1px dashed #666; width:80%; margin-bottom:10px;"></div>
    <div class="lcd-label">PREDICTION</div>
    <div class="lcd-pred-container">
        {preds_html}
    </div>
</div>
""", unsafe_allow_html=True)

# スライダー
st.session_state.c = st.slider("", 1, 4, 2, key="s")

# ボタン
c1, c2 = st.columns(2)
with c1:
    st.button("LOTO 7", on_click=set_g, args=('L7',))
    st.button("LOTO 6", on_click=set_g, args=('L6',))
    st.button("Numbers 4", on_click=set_g, args=('N4',))
    st.button("Numbers 3", on_click=set_g, args=('N3',))
with c2:
    st.button("MINI LOTO", on_click=set_g, args=('ML',))
    st.button("BINGO 5", on_click=set_g, args=('B5',))
    st.button("Numbers Mini", on_click=set_g, args=('NM',))
    st.button("着替クー", on_click=set_g, args=('KC',))
