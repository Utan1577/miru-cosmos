import streamlit as st
import random
import requests
from bs4 import BeautifulSoup

# --- 1. 極限の余白カット ---
st.set_page_config(page_title="MIRU-PAD", layout="centered")

# --- 2. CSS: スマホ画面を「モニター」と「ボタン」で二分する ---
st.markdown("""
    <style>
    .stApp { background-color: #000; }
    .block-container { padding: 0 !important; }
    
    /* 上部モニターエリア */
    .monitor-area {
        background-color: #222;
        color: #00FF00;
        height: 40vh; /* 画面の40%を使用 */
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        border-bottom: 2px solid #444;
        font-family: monospace;
    }
    .res-label { font-size: 12px; color: #888; }
    .res-val { font-size: 20px; color: #fff; margin-bottom: 10px; }
    .pred-val { font-size: 45px; font-weight: bold; line-height: 1.1; letter-spacing: 5px; }

    /* 下部コントロールエリア */
    .control-area {
        height: 60vh; /* 画面の60%を使用 */
        padding: 10px;
    }
    
    /* ボタンを電卓みたいに配置 */
    div[data-testid="column"] {
        width: 50% !important;
        flex: 1 1 50% !important;
        min-width: 50% !important;
    }
    .stButton > button {
        height: 65px !important;
        background-color: #111 !important;
        border: 1px solid #333 !important;
        color: #fff !important;
        font-size: 16px !important;
        margin-bottom: 5px !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. ロジック ---
if 'g' not in st.session_state: st.session_state.g = 'N4'

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
            return f"{idx} {val}"
        except: return "取得中..."
    return "----"

def gen_nums(g):
    l = 4 if g == 'N4' else 3
    return "".join([str(random.randint(0,9)) for _ in range(l)])

# --- 4. 描画 ---

# モニター (HTML)
last = get_last(st.session_state.g)
pred = gen_nums(st.session_state.g)

st.markdown(f"""
<div class="monitor-area">
    <div class="res-label">LAST RESULT ({st.session_state.g})</div>
    <div class="res-val">{last}</div>
    <div style="width: 50%; border-top: 1px solid #444; margin-bottom: 15px;"></div>
    <div class="res-label">PREDICTION</div>
    <div class="pred-val">{pred}</div>
</div>
""", unsafe_allow_html=True)

# 操作パネル
st.markdown('<div class="control-area">', unsafe_allow_html=True)
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
st.markdown('</div>', unsafe_allow_html=True)
