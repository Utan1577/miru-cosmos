import streamlit as st
import random
import requests
from bs4 import BeautifulSoup

# --- 1. 極限のシンプル設定 (余白削除) ---
st.set_page_config(page_title="MIRU-DASH", layout="wide")

# --- 2. CSS: スマホ1画面に収めるための強制圧縮 ---
st.markdown("""
    <style>
    /* 全体の背景：漆黒 */
    .stApp {
        background-color: #000000;
        color: #e0e0e0;
    }
    /* Streamlitのデフォルト余白を全削除して画面を広く使う */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100%;
    }
    
    /* モニターエリア (上部) */
    .monitor {
        background-color: #111;
        border: 1px solid #333;
        border-radius: 4px;
        padding: 10px;
        margin-bottom: 10px;
        text-align: center;
        height: 180px; /* 高さ固定 */
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    .monitor-label {
        font-size: 10px;
        color: #666;
        letter-spacing: 1px;
        margin-bottom: 2px;
    }
    .monitor-val-sm {
        font-family: 'Courier New', monospace;
        font-size: 18px;
        color: #888;
        margin-bottom: 8px;
    }
    .monitor-val-lg {
        font-family: 'Courier New', monospace;
        font-size: 36px;
        font-weight: bold;
        color: #00FF00; /* ネオン・グリーン */
        letter-spacing: 3px;
        text-shadow: 0 0 10px rgba(0,255,0,0.3);
        line-height: 1.0;
    }

    /* ボタンエリア (下部) */
    .stButton > button {
        width: 100%;
        height: 60px; /* 押しやすい高さ */
        background-color: #222;
        border: 1px solid #444;
        color: #fff;
        font-weight: bold;
        font-size: 14px;
        border-radius: 4px;
        margin: 0;
    }
    .stButton > button:active {
        background-color: #00FF00;
        color: #000;
    }
    
    /* スライダーを少しコンパクトに */
    .stSlider {
        padding-bottom: 10px !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. ロジック ---
if 'game' not in st.session_state:
    st.session_state.game = 'N4' # デフォルト
if 'count' not in st.session_state:
    st.session_state.count = 2

def set_game(g):
    st.session_state.game = g

def get_data(game):
    if game == 'N4':
        try:
            url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
            res = requests.get(url)
            res.encoding = 'Shift_JIS'
            soup = BeautifulSoup(res.text, 'html.parser')
            idx = soup.find('th', class_='alnCenter').text.strip()
            val = soup.find('td', class_='alnCenter').find('strong').text.strip()
            return idx, val
        except:
            return "ERR", "----"
    return "-", "----"

def gen_nums(game, n):
    length = 4 if game == 'N4' else (3 if game in ['N3','NM'] else 4) # 仮
    return ["".join([str(random.randint(0,9)) for _ in range(length)]) for _ in range(n)]

# --- 4. レイアウト構築 (上から順に詰める) ---

# [A] モニターエリア (固定表示)
game = st.session_state.game
idx, last_val = get_data(game)
preds = gen_nums(game, st.session_state.count)

# HTMLで直接モニターを描画
monitor_html = f"""
<div class="monitor">
    <div class="monitor-label">LAST RESULT ({game})</div>
    <div class="monitor-val-sm">{idx}: {last_val}</div>
    <div style="border-top: 1px dashed #333; width: 80%; margin: 5px 0;"></div>
    <div class="monitor-label">PREDICTION</div>
    {"".join([f'<div class="monitor-val-lg">{p}</div>' for p in preds])}
</div>
"""
st.markdown(monitor_html, unsafe_allow_html=True)

# [B] スライダー (指一本で操作)
st.session_state.count = st.slider("", 1, 5, 2, key="slider_top")

# [C] コントロールパッド (4x2グリッドで敷き詰め)
c1, c2 = st.columns(2)
with c1:
    st.button("LOTO 7", on_click=set_game, args=('L7',))
    st.button("LOTO 6", on_click=set_game, args=('L6',))
    st.button("Numbers 4", on_click=set_game, args=('N4',))
    st.button("Numbers 3", on_click=set_game, args=('N3',))
with c2:
    st.button("MINI LOTO", on_click=set_game, args=('ML',))
    st.button("BINGO 5", on_click=set_game, args=('B5',))
    st.button("Numbers Mini", on_click=set_game, args=('NM',))
    st.button("着替クー", on_click=set_game, args=('KC',))

# 余計な要素ゼロ。以上。
