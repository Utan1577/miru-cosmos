import streamlit as st
import random
import requests
from bs4 import BeautifulSoup

# --- ページ設定とセッション管理 ---
st.set_page_config(page_title="MIRU-COSMOS", layout="centered")

if 'active_game' not in st.session_state:
    st.session_state.active_game = None

def set_game(game_name):
    st.session_state.active_game = game_name

# --- デザイン調整 (スマホ強制2列 & 視認性UP) ---
st.markdown("""
    <style>
    /* 全体の背景 */
    .stApp {
        background-color: #000000;
        color: #FFFFFF;
    }
    
    /* 【重要】スマホでも強制的に横並びにする魔法 */
    div[data-testid="column"] {
        width: 50% !important;
        flex: 1 1 50% !important;
        min-width: 50% !important;
        max-width: 50% !important;
    }
    div[data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
    }

    /* ボタンのデザイン */
    .stButton>button {
        width: 95%;
        margin: 0 auto;
        border-radius: 8px;
        background: #111;
        border: 1px solid #444;
        color: #fff;
        font-weight: bold;
        height: 50px;
    }
    .stButton>button:active, .stButton>button:focus {
        border-color: #00FFFF;
        color: #00FFFF;
        background: #222;
    }

    /* 結果表示のデザイン */
    .pred-box {
        border: 1px solid #00FF00;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin-top: 10px;
        background: rgba(0, 50, 0, 0.3);
    }
    .pred-num {
        font-size: 40px;
        font-weight: bold;
        color: #00FF00;
        font-family: monospace;
        line-height: 1.2;
    }
    </style>
""", unsafe_allow_html=True)

# --- ロジック関数 ---
def get_n4_result():
    try:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        res = requests.get(url)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        r_round = soup.find('th', class_='alnCenter').text.strip()
        r_num = soup.find('td', class_='alnCenter').find('strong').text.strip()
        return f"{r_round} : {r_num}"
    except:
        return "データ取得中..."

def generate_nums(count, length):
    return ["".join([str(random.randint(0, 9)) for _ in range(length)]) for _ in range(count)]

# --- メイン画面 ---
st.markdown("<h2 style='text-align: center; color: #00FFFF;'>MIRU-COSMOS</h2>", unsafe_allow_html=True)

# ボタン配置 (強制2列)
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

# 設定エリア
count = st.slider("予想口数", 1, 10, 5)

with st.expander("📝 MIRU PROTOCOL (哲学)"):
    st.write("「当てるために使わず、無駄な負けを消すために使う。」")
    st.write("J値(違和感)とH値(物理荒れ度)を観測せよ。")

# --- 結果出力エリア ---
active = st.session_state.active_game

if active:
    # 1. 前回結果をドカンと表示
    st.markdown("### 📡 前回結果 / LAST RESULT")
    
    if active == 'N4':
        last_res = get_n4_result()
        st.info(f"Numbers4 {last_res}")  # 青いボックスで目立たせる
        
        # 2. 予想数字を表示
        st.markdown("### 🔮 今回の予想 / PREDICTION")
        preds = generate_nums(count, 4)
        
        st.markdown('<div class="pred-box">', unsafe_allow_html=True)
        for p in preds:
            st.markdown(f'<div class="pred-num">{p}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    elif active == 'N3':
        st.info("Numbers3 データ同期中...")
        preds = generate_nums(count, 3)
        st.markdown('<div class="pred-box">', unsafe_allow_html=True)
        for p in preds:
            st.markdown(f'<div class="pred-num">{p}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.warning(f"{active} のロジックを宇宙と同期しています...")

else:
    st.write("👆 上のボタンを押してミッションを開始せよ")
