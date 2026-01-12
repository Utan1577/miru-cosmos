import streamlit as st
import random
import requests
from bs4 import BeautifulSoup

# --- ページ設定 ---
st.set_page_config(page_title="MIRU-COSMOS", layout="centered")

if 'active_game' not in st.session_state:
    st.session_state.active_game = None

def set_game(game_name):
    st.session_state.active_game = game_name

# --- データ取得 ---
def get_n4_data():
    try:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        res = requests.get(url)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        r_round = soup.find('th', class_='alnCenter').text.strip()
        r_num_str = soup.find('td', class_='alnCenter').find('strong').text.strip()
        return r_round, list(r_num_str)
    except:
        return "データ取得失敗", ['-', '-', '-', '-']

def generate_nums(count, length):
    return [list("".join([str(random.randint(0, 9)) for _ in range(length)])) for _ in range(count)]

# --- 【完全再現】ゴールド・トイ・スタイル ---
st.markdown("""
    <style>
    /* 1. 背景をあの「金色」にする */
    .stApp {
        background-color: #F4D03F !important; /* おもちゃのゴールド */
        background-image: linear-gradient(135deg, #F4D03F 0%, #E5C330 100%);
    }
    
    /* 2. ヘッダーや文字色を調整 */
    h1, h2, h3, p, div {
        color: #333333 !important;
        font-family: 'Arial', sans-serif;
        text-shadow: none !important;
    }

    /* 3. 液晶画面 (グレーのボックス) */
    .lcd-screen {
        background-color: #95A5A6;
        border: 4px solid #555;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 20px;
        box-shadow: inset 2px 2px 5px rgba(0,0,0,0.3);
        text-align: center;
        min-height: 150px;
    }
    .lcd-text {
        font-family: 'Courier New', monospace;
        color: #1a1a1a !important;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .lcd-big-num {
        font-family: 'Courier New', monospace;
        color: #000 !important;
        font-size: 2.5rem;
        letter-spacing: 5px;
        background: rgba(255,255,255,0.3);
        border: 1px solid #777;
        margin: 5px 0;
        display: inline-block;
        padding: 0 10px;
    }

    /* 4. スマホでも絶対に「2列」にする強制魔法 */
    [data-testid="column"] {
        width: 50% !important;
        flex: 1 1 50% !important;
        min-width: 50% !important;
    }
    
    /* 5. ボタンの共通デザイン (丸っこいプラスチック感) */
    .stButton > button {
        width: 100%;
        height: 50px;
        border-radius: 25px !important; /* 丸く */
        border: 2px solid rgba(0,0,0,0.2) !important;
        color: white !important;
        font-weight: bold !important;
        font-size: 14px !important;
        box-shadow: 0 3px 0 rgba(0,0,0,0.3) !important;
        margin-bottom: 8px !important;
    }
    .stButton > button:active {
        transform: translateY(2px);
        box-shadow: 0 1px 0 rgba(0,0,0,0.3) !important;
    }

    /* 6. ボタンの色分け (あの画像通りに) */
    
    /* 左列: LOTO系 (ピンク) */
    div[data-testid="column"]:nth-of-type(1) button {
        background-color: #E91E63 !important;
    }
    /* 左列の一番下: BINGO5 (青) */
    div[data-testid="column"]:nth-of-type(1) .stButton:nth-last-of-type(1) button {
        background-color: #3498DB !important;
    }

    /* 右列: Numbers系 (緑) */
    div[data-testid="column"]:nth-of-type(2) button {
        background-color: #2ECC71 !important;
    }
    /* 右列の下2つ: Miniとクーちゃん (オレンジ/黄色) */
    div[data-testid="column"]:nth-of-type(2) .stButton:nth-of-type(3) button {
        background-color: #F39C12 !important; /* Mini */
    }
    div[data-testid="column"]:nth-of-type(2) .stButton:nth-of-type(4) button {
        background-color: #F1C40F !important; /* クーちゃん */
        color: #333 !important;
    }

    </style>
""", unsafe_allow_html=True)

# --- 画面構築 ---

# タイトル（あのロゴっぽく）
st.markdown("<h1 style='text-align: center; color: #B7950B !important; text-shadow: 1px 1px 0 #fff;'>超・MIRUくん</h1>", unsafe_allow_html=True)

# 液晶画面エリア
active = st.session_state.active_game

st.markdown('<div class="lcd-screen">', unsafe_allow_html=True)
if active == 'N4':
    # データ取得
    r_round, r_nums = get_n4_data()
    pred_count = st.session_state.get('p_count', 3)
    preds = generate_nums(pred_count, 4)
    
    # 前回結果
    st.markdown(f'<div class="lcd-text">前回結果 ({r_round})</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="lcd-big-num">{"".join(r_nums)}</div>', unsafe_allow_html=True)
    st.markdown("<hr style='border-color: #777; margin: 5px 0;'>", unsafe_allow_html=True)
    # 予想
    st.markdown(f'<div class="lcd-text">今回の予想</div>', unsafe_allow_html=True)
    for p in preds:
        st.markdown(f'<div class="lcd-big-num">{"".join(p)}</div>', unsafe_allow_html=True)

elif active:
    st.markdown(f'<div class="lcd-text">{active}</div>', unsafe_allow_html=True)
    st.markdown('<div class="lcd-text">READY...</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="lcd-text">SELECT GAME</div>', unsafe_allow_html=True)
    st.markdown('<div class="lcd-text">----</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)


# ボタン配置エリア (強制2列)
c1, c2 = st.columns(2)

with c1:
    st.button("LOTO 7", key="l7", on_click=set_game, args=('L7',))
    st.button("LOTO 6", key="l6", on_click=set_game, args=('L6',))
    st.button("MINI LOTO", key="ml", on_click=set_game, args=('ML',))
    st.button("BINGO 5", key="b5", on_click=set_game, args=('B5',))

with c2:
    st.button("Numbers 4", key="n4", on_click=set_game, args=('N4',))
    st.button("Numbers 3", key="n3", on_click=set_game, args=('N3',))
    st.button("NUMBERS mini", key="nm", on_click=set_game, args=('NM',))
    st.button("着替クー", key="kc", on_click=set_game, args=('KC',))

# スライダーと文書
st.slider("口数設定", 1, 5, 3, key='p_count')
with st.expander("解析ロジック (取扱説明書)"):
    st.write("当てるために使わず、無駄な負けを消すために使う。")
