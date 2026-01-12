import streamlit as st
import random
import requests
from bs4 import BeautifulSoup

# --- 1. 究極の画面固定 ---
st.set_page_config(page_title="MIRU-PAD", layout="centered")

# --- 2. セッション管理 ---
if 'g' not in st.session_state: st.session_state.g = 'N4'
if 'c' not in st.session_state: st.session_state.c = 2

# JavaScriptを使って、HTML内の自作ボタンからStreamlitに命令を送るためのフック
def update_state():
    query_params = st.query_params
    if "game" in query_params:
        st.session_state.g = query_params["game"]
    if "action" in query_params:
        if query_params["action"] == "plus" and st.session_state.c < 10:
            st.session_state.c += 1
        elif query_params["action"] == "minus" and st.session_state.c > 1:
            st.session_state.c -= 1
    st.query_params.clear()

update_state()

# --- 3. データ取得 ---
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

# --- 4. CSS (一画面完結・完全配置固定) ---
st.markdown("""
    <style>
    /* 標準要素を隠す */
    header, footer, .stDeployButton, [data-testid="stToolbar"] { display: none !important; }
    html, body, [data-testid="stAppViewContainer"] {
        overflow: hidden !important;
        background-color: #000 !important;
    }
    .block-container { padding: 5px !important; }
    
    /* リモコン筐体 */
    .remote-body {
        width: 100%;
        max-width: 400px;
        margin: auto;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    /* 液晶モニター */
    .lcd {
        background-color: #9ea7a6;
        border: 4px solid #555;
        border-radius: 10px;
        height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        box-shadow: inset 0 0 15px rgba(0,0,0,0.5);
    }
    .lcd-nums { color: #000; font-family: 'Courier New', monospace; font-size: 30px; font-weight: bold; letter-spacing: 5px; }

    /* コントロールパネル */
    .pad-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
    }
    .btn {
        height: 55px;
        border-radius: 20px;
        border: 2px solid rgba(0,0,0,0.3);
        color: white;
        font-weight: bold;
        font-size: 14px;
        display: flex;
        justify-content: center;
        align-items: center;
        text-decoration: none;
        box-shadow: 0 4px 0 rgba(0,0,0,0.4);
    }
    .btn:active { transform: translateY(2px); box-shadow: 0 2px 0 rgba(0,0,0,0.4); }
    
    .btn-loto { background: #E91E63; }
    .btn-num { background: #009688; }
    .btn-bingo { background: #2196F3; }
    .btn-mini { background: #FF9800; }
    .btn-koo { background: #FFEB3B; color: #000; }

    /* 口数調整用バー */
    .counter-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #222;
        padding: 5px 15px;
        border-radius: 30px;
        color: white;
    }
    .btn-round {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #444;
        display: flex;
        justify-content: center;
        align-items: center;
        color: white;
        text-decoration: none;
        font-size: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 5. UI構築 ---

game = st.session_state.g
last = get_n4() if game == 'N4' else "SYNCING..."
preds = gen_p(game, st.session_state.c)
preds_html = "".join([f'<div class="lcd-nums">{p}</div>' for p in preds])

# 全てを一つのHTML構造として流し込む
st.markdown(f"""
<div class="remote-body">
    <div class="lcd">
        <div style="color:#444; font-size:10px;">LAST: {last}</div>
        <div style="width:70%; border-top:1px solid #777; margin:5px 0;"></div>
        {preds_html}
    </div>

    <div class="counter-bar">
        <a href="/?action=minus" target="_self" class="btn-round">－</a>
        <div style="font-weight:bold;">{st.session_state.c} 口</div>
        <a href="/?action=plus" target="_self" class="btn-round">＋</a>
    </div>

    <div class="pad-grid">
        <a href="/?game=L7" target="_self" class="btn btn-loto">LOTO 7</a>
        <a href="/?game=N4" target="_self" class="btn btn-num">Numbers 4</a>
        <a href="/?game=L6" target="_self" class="btn btn-loto">LOTO 6</a>
        <a href="/?game=N3" target="_self" class="btn btn-num">Numbers 3</a>
        <a href="/?game=ML" target="_self" class="btn btn-loto">MINI LOTO</a>
        <a href="/?game=NM" target="_self" class="btn btn-mini">Numbers mini</a>
        <a href="/?game=B5" target="_self" class="btn btn-bingo">BINGO 5</a>
        <a href="/?game=KC" target="_self" class="btn btn-koo">着替クー</a>
    </div>
</div>
""", unsafe_allow_html=True)
