import streamlit as st
import random
import requests
from bs4 import BeautifulSoup

# --- 1. 究極の画面固定 ---
st.set_page_config(page_title="MIRU-PAD", layout="centered")

# --- 2. セッション管理 ---
if 'g' not in st.session_state: st.session_state.g = 'N4'
if 'c' not in st.session_state: st.session_state.c = 2

def set_g(n): st.session_state.g = n
def add_c():
    if st.session_state.c < 10: st.session_state.c += 1
def sub_c():
    if st.session_state.c > 1: st.session_state.c -= 1

# --- 3. データ取得 & 生成 ---
def get_n4():
    try:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        res = requests.get(url)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        idx = soup.find('th', class_='alnCenter').text.strip()
        val = soup.find('td', class_='alnCenter').find('strong').text.strip()
        return f"{idx}: {val}"
    except: return "DATA SYNCING..."

def gen_p(g, c):
    l = 4 if g == 'N4' else (3 if g in ['N3','NM'] else 4)
    return ["".join([str(random.randint(0,9)) for _ in range(l)]) for _ in range(c)]

# --- 4. CSS (一画面完結・はみ出し禁止) ---
st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        overflow: hidden !important;
        background-color: #000 !important;
    }
    .block-container { padding: 5px !important; }
    
    /* モニターエリア */
    .lcd-box {
        background-color: #222;
        border: 2px solid #444;
        border-radius: 8px;
        height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
        margin-bottom: 5px;
    }
    .lcd-label { color: #666; font-size: 10px; font-family: monospace; }
    .lcd-val { color: #fff; font-size: 14px; margin-bottom: 5px; }
    .lcd-nums { color: #00FF00; font-size: 28px; font-weight: bold; letter-spacing: 4px; line-height: 1.1; }

    /* 操作エリア：ボタンを2列に固定 */
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 5px !important;
    }
    div[data-testid="column"] {
        width: 50% !important;
        flex: 1 !important;
        min-width: 50% !important;
    }
    
    /* 全ボタンのサイズ統一 */
    .stButton > button {
        width: 100% !important;
        height: 48px !important;
        background-color: #1a1a1a !important;
        color: white !important;
        border: 1px solid #333 !important;
        font-size: 12px !important;
        padding: 0 !important;
        margin-bottom: 2px !important;
    }
    
    /* プラスマイナスボタン用 */
    .count-btn > div[data-testid="stHorizontalBlock"] {
        align-items: center;
        justify-content: center;
        background: #111;
        padding: 5px;
        border-radius: 4px;
        margin-bottom: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 5. UI構築 ---

# [上部] モニター
game = st.session_state.g
last = get_n4() if game == 'N4' else "SYNCING..."
preds = gen_p(game, st.session_state.c)
preds_html = "".join([f'<div class="lcd-nums">{p}</div>' for p in preds])

st.markdown(f"""
<div class="lcd-box">
    <div class="lcd-label">LAST RESULT ({game})</div>
    <div class="lcd-val">{last}</div>
    <div style="width: 50%; border-top: 1px solid #444; margin-bottom: 5px;"></div>
    <div class="lcd-label">PREDICTION ({st.session_state.c}口)</div>
    {preds_html}
</div>
""", unsafe_allow_html=True)

# [中間] 口数調整 (+ - ボタン)
st.markdown('<div class="count-btn">', unsafe_allow_html=True)
col_sub, col_val, col_add = st.columns([1, 2, 1])
with col_sub:
    st.button("－", on_click=sub_c)
with col_val:
    st.markdown(f"<div style='text-align:center; font-weight:bold; color:white;'>{st.session_state.c} 口</div>", unsafe_allow_html=True)
with col_add:
    st.button("＋", on_click=add_c)
st.markdown('</div>', unsafe_allow_html=True)

# [下部] 選択パッド (2列固定)
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
