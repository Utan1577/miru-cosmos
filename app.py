import streamlit as st
import random
import requests
from bs4 import BeautifulSoup

# --- 究極の画面固定設定 ---
st.set_page_config(page_title="MIRU-DASH", layout="centered")

# --- データ取得 ---
def get_last_n4():
    try:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        res = requests.get(url)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        idx = soup.find('th', class_='alnCenter').text.strip()
        val = soup.find('td', class_='alnCenter').find('strong').text.strip()
        return f"{idx}: {val}"
    except: return "SYNCING..."

def gen_nums(g, c):
    l = 4 if g == 'N4' else (3 if g in ['N3','NM'] else 4)
    return ["".join([str(random.randint(0,9)) for _ in range(l)]) for _ in range(c)]

# --- セッション管理 ---
if 'g' not in st.session_state: st.session_state.g = 'N4'
if 'c' not in st.session_state: st.session_state.c = 2
def set_g(n): st.session_state.g = n

# --- 【完全固定】CSS Grid & Flex ---
st.markdown("""
    <style>
    /* 全体をスクロール不可にする */
    html, body, [data-testid="stAppViewContainer"] {
        overflow: hidden !important;
        background-color: #000 !important;
    }
    .block-container {
        padding: 5px !important;
        height: 100vh !important;
    }

    /* 液晶モニターエリア (高さ固定) */
    .lcd-frame {
        background-color: #222;
        border: 2px solid #444;
        border-radius: 8px;
        height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
        margin-bottom: 10px;
    }
    .lcd-label { color: #666; font-size: 10px; font-family: monospace; }
    .lcd-last { color: #fff; font-size: 14px; margin-bottom: 5px; }
    .lcd-nums { color: #00FF00; font-size: 32px; font-weight: bold; letter-spacing: 5px; line-height: 1.0; }

    /* 【解決策】強制的に2列にする魔法 */
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
    
    /* ボタンを小さく・平たくして一画面に収める */
    .stButton > button {
        height: 45px !important;
        background-color: #1a1a1a !important;
        color: white !important;
        border: 1px solid #333 !important;
        font-size: 12px !important;
        margin-bottom: 2px !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 描画開始 ---

# モニター描画
game = st.session_state.g
last = get_last_n4() if game == 'N4' else "----"
preds = gen_nums(game, st.session_state.c)
preds_html = "".join([f'<div class="lcd-nums">{p}</div>' for p in preds])

st.markdown(f"""
<div class="lcd-frame">
    <div class="lcd-label">LAST RESULT ({game})</div>
    <div class="lcd-last">{last}</div>
    <div style="width: 50%; border-top: 1px solid #333; margin: 5px 0;"></div>
    <div class="lcd-label">PREDICTION</div>
    {preds_html}
</div>
""", unsafe_allow_html=True)

# スライダー (高さを食わないように最小限に)
st.session_state.c = st.slider("", 1, 3, 2, key="s")

# ボタン (強制2列)
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
