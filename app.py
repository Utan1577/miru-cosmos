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

# --- ロジック関数 ---
def get_n4_data():
    try:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        res = requests.get(url)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        r_round = soup.find('th', class_='alnCenter').text.strip()
        r_num_str = soup.find('td', class_='alnCenter').find('strong').text.strip()
        return r_round, list(r_num_str) # 結果をリストで返す ['1', '2', '3', '4']
    except:
        return "取得失敗", ['-', '-', '-', '-']

def generate_nums(count, length):
    # 各桁をリストにした予測のリストを返す [['1','2','3','4'], ['5','6','7','8']]
    return [list("".join([str(random.randint(0, 9)) for _ in range(length)])) for _ in range(count)]

# --- CSSスタイル (ここが重要！) ---
st.markdown("""
    <style>
    /* 全体の背景 */
    .stApp { background-color: #0a0a0a; color: #ffffff; }
    h1, h2, h3 { color: #00ffff; text-shadow: 0 0 5px #00ffff; }
    .sub-header { color: #aaaaaa; font-size: 0.9em; margin-bottom: 20px; }

    /* スマホ強制2列レイアウト */
    div[data-testid="column"] { width: 50% !important; flex: 1 1 50% !important; }
    div[data-testid="stHorizontalBlock"] { gap: 10px; }

    /* ボタンの共通スタイル */
    .stButton>button {
        width: 100%; height: 60px; border-radius: 12px; font-weight: bold; font-size: 1.1em;
        border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.3); transition: all 0.2s; color: white;
    }
    .stButton>button:active { box-shadow: 0 2px 3px rgba(0,0,0,0.3); transform: translateY(2px); }

    /* 各ボタンのカラー設定 (左列) */
    div[data-testid="column"]:nth-of-type(1) .stButton:nth-of-type(1) > button { background: linear-gradient(to bottom, #ff4b4b, #cc0000); } /* L7(赤) */
    div[data-testid="column"]:nth-of-type(1) .stButton:nth-of-type(2) > button { background: linear-gradient(to bottom, #ff69b4, #db1a7f); } /* L6(ピンク) */
    div[data-testid="column"]:nth-of-type(1) .stButton:nth-of-type(3) > button { background: linear-gradient(to bottom, #4169e1, #0000cd); } /* ML(青) */
    div[data-testid="column"]:nth-of-type(1) .stButton:nth-of-type(4) > button { background: linear-gradient(to bottom, #00bfff, #0080ff); } /* B5(水色) */
    /* 各ボタンのカラー設定 (右列) */
    div[data-testid="column"]:nth-of-type(2) .stButton:nth-of-type(1) > button { background: linear-gradient(to bottom, #32cd32, #008000); } /* N4(緑) */
    div[data-testid="column"]:nth-of-type(2) .stButton:nth-of-type(2) > button { background: linear-gradient(to bottom, #adff2f, #7cfc00); color: #000;} /* N3(黄緑) */
    div[data-testid="column"]:nth-of-type(2) .stButton:nth-of-type(3) > button { background: linear-gradient(to bottom, #ffa500, #ff8c00); } /* NM(オレンジ) */
    div[data-testid="column"]:nth-of-type(2) .stButton:nth-of-type(4) > button { background: linear-gradient(to bottom, #ffff00, #ffd700); color: #000;} /* KC(黄色) */

    /* 結果表示のマスタイル */
    .num-cell {
        background: #222; border: 2px solid #444; border-radius: 10px;
        padding: 10px 0; text-align: center; font-size: 2em; font-weight: bold;
        color: #00ff00; text-shadow: 0 0 5px #00ff00;
    }
    .last-cell {
        background: #333; border: 2px solid #555; color: #ff00ff; text-shadow: 0 0 5px #ff00ff;
    }
    </style>
""", unsafe_allow_html=True)

# --- メイン画面UI ---
st.markdown("<h1>MIRU-COSMOS</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-header'>UNIVERSAL PREDICTION CONSOLE</p>", unsafe_allow_html=True)

# ボタングリッド
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
count = st.slider("予想口数", 1, 10, 3)
with st.expander("📝 MIRU PROTOCOL (哲学)"):
    st.write("「当てるために使わず、無駄な負けを消すために使う。」")

# --- 結果表示エリア ---
active = st.session_state.active_game
if active == 'N4':
    r_round, r_nums = get_n4_data()
    preds = generate_nums(count, 4)

    st.markdown(f"<h2>Numbers 4 {r_round}</h2>", unsafe_allow_html=True)
    
    # 予想数字の表示
    for i, p_list in enumerate(preds):
        st.markdown(f"<h3>予想 {i+1}</h3>", unsafe_allow_html=True)
        cols = st.columns(4)
        for j, digit in enumerate(p_list):
            cols[j].markdown(f"<div class='num-cell'>{digit}</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    # 前回結果の表示
    st.markdown("<h3>前回結果</h3>", unsafe_allow_html=True)
    cols = st.columns(4)
    for j, digit in enumerate(r_nums):
        cols[j].markdown(f"<div class='num-cell last-cell'>{digit}</div>", unsafe_allow_html=True)

elif active:
    st.info(f"{active} のロジックを同期中...")
