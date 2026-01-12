import streamlit as st
import random
import requests
from bs4 import BeautifulSoup

# --- 1. ページ基本設定 (余白を殺す) ---
st.set_page_config(page_title="MIRU-COSMOS", layout="centered")

# --- 2. セッション管理 ---
if 'g' not in st.session_state: st.session_state.g = 'N4'
if 'c' not in st.session_state: st.session_state.c = 2
def set_g(n): st.session_state.g = n

# --- 3. ロジック部 ---
def get_n4():
    try:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        res = requests.get(url)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        idx = soup.find('th', class_='alnCenter').text.strip()
        val = soup.find('td', class_='alnCenter').find('strong').text.strip()
        return f"{idx} {val}"
    except: return "SYNCING..."

def gen_p(g, c):
    l = 4 if g == 'N4' else (3 if g in ['N3','NM'] else 4)
    return ["".join([str(random.randint(0,9)) for _ in range(l)]) for _ in range(c)]

# --- 4. 究極のCSS (1画面完結・スクロール禁止) ---
st.markdown("""
    <style>
    /* 全体をスマホ1画面にロック */
    html, body, [data-testid="stAppViewContainer"] {
        overflow: hidden !important;
        background-color: #000 !important;
    }
    .block-container {
        padding: 5px !important;
        height: 100vh !important;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    
    /* 液晶モニターエリア (画面の約35%) */
    .lcd-unit {
        background-color: #222;
        border: 2px solid #444;
        border-radius: 8px;
        height: 35vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
        box-shadow: inset 0 0 20px #000;
    }
    .lcd-label { color: #666; font-size: 10px; font-family: monospace; }
    .lcd-last { color: #fff; font-size: 16px; font-family: monospace; margin-bottom: 5px; }
    .lcd-nums { color: #00FF00; font-size: 38px; font-weight: bold; font-family: 'Courier New', monospace; letter-spacing: 4px; line-height: 1.1; }

    /* 操作エリア (画面の約60%) */
    .control-unit {
        height: 60vh;
        display: flex;
        flex-direction: column;
        justify-content: space-around;
    }

    /* ボタンの強制2列 */
    div[data-testid="column"] {
        width: 50% !important;
        flex: 1 1 50% !important;
        min-width: 50% !important;
    }
    .stButton > button {
        height: 12vh !important; /* 画面高さに合わせてボタンサイズ調整 */
        background-color: #1a1a1a !important;
        color: white !important;
        border: 1px solid #333 !important;
        font-weight: bold !important;
        font-size: 14px !important;
        margin: 0 !important;
    }
    /* ボタンの色付け */
    div[data-testid="column"]:nth-of-type(1) button { border-left: 4px solid #E91E63 !important; }
    div[data-testid="column"]:nth-of-type(2) button { border-left: 4px solid #009688 !important; }
    
    /* スライダーを最小化 */
    .stSlider { margin-top: -20px !important; margin-bottom: -10px !important; }
    </style>
""", unsafe_allow_html=True)

# --- 5. 画面描画 ---

# [上部] 液晶モニター
game = st.session_state.g
last = get_n4() if game == 'N4' else "----"
preds = gen_p(game, st.session_state.c)
preds_html = "".join([f'<div class="lcd-nums">{p}</div>' for p in preds])

st.markdown(f"""
<div class="lcd-unit">
    <div class="lcd-label">LAST RESULT ({game})</div>
    <div class="lcd-last">{last}</div>
    <div style="width: 60%; border-top: 1px solid #333; margin: 5px 0;"></div>
    <div class="lcd-label">PREDICTION</div>
    {preds_html}
</div>
""", unsafe_allow_html=True)

# [中間] スライダー
st.session_state.c = st.slider("", 1, 3, 2, key="s")

# [下部] ボタンパッド (強制2列)
c1, c2 = st.columns(2)
with c1:
    st.button("LOTO 7", on_click=set_g, args=('L7',))
    st.button("LOTO 6", on_click=set_g, args=('L6',))
    st.button("Numbers 4", on_click=set_g, args=('N4',))
    st.button("Numbers 3", on_click=set_g, args=('N3',))
with c2:
    st.button("MINI LOTO", on_click=set_g, args=('ML',))
    st.button("BINGO 5", on_click=set_g, args=('B5',))
    st.button("NUMBERS mini", on_click=set_g, args=('NM',))
    st.button("着替クー", on_click=set_g, args=('KC',))
