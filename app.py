import streamlit as st
import random
import requests
from bs4 import BeautifulSoup

# --- ページ設定 ---
st.set_page_config(page_title="MIRU-COSMOS", layout="centered")

# --- セッション状態の初期化 ---
if 'active_game' not in st.session_state:
    st.session_state.active_game = None

def set_game(game_name):
    st.session_state.active_game = game_name

# --- データ取得ロジック (Numbers4のみ実裝例) ---
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

# --- 【重要】デザインを「超的くん」に強制変換するCSS ---
st.markdown("""
    <style>
    /* 全体の背景：あの機械の「金色の筐体」をイメージした少し暗めのゴールド調、または黒で引き締める */
    .stApp {
        background-color: #222222; 
    }

    /* ----------------------------------------------------
       スマホで強制的に2列にするための魔法のコード
    ---------------------------------------------------- */
    div[data-testid="column"] {
        width: 50% !important;
        flex: 1 1 50% !important;
        min-width: 50% !important;
        padding: 0 5px !important;
    }
    
    /* ボタンの共通スタイル（角丸でプックリさせる） */
    .stButton > button {
        width: 100%;
        height: 60px;
        border-radius: 20px; /* 丸っこく */
        border: 2px solid rgba(0,0,0,0.2);
        color: white !important;
        font-weight: 900 !important;
        font-size: 16px !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
        margin-bottom: 5px;
        box-shadow: 0 4px 0 rgba(0,0,0,0.4); /* 立体感 */
        transition: all 0.1s;
    }
    .stButton > button:active {
        box-shadow: 0 1px 0 rgba(0,0,0,0.4);
        transform: translateY(3px);
    }

    /* ----------------------------------------------------
       ここからボタンごとの色指定 (画像の色を再現)
       ※ nth-of-typeを使って順番に色を塗り替えています
    ---------------------------------------------------- */
    
    /* 左列 (LOTO系) */
    div[data-testid="column"]:nth-of-type(1) .stButton:nth-of-type(1) > button {
        background: #E91E63 !important; /* LOTO 7 (ピンク) */
    }
    div[data-testid="column"]:nth-of-type(1) .stButton:nth-of-type(2) > button {
        background: #E91E63 !important; /* LOTO 6 (ピンク) */
    }
    div[data-testid="column"]:nth-of-type(1) .stButton:nth-of-type(3) > button {
        background: #E91E63 !important; /* MINI LOTO (ピンク) */
    }
    div[data-testid="column"]:nth-of-type(1) .stButton:nth-of-type(4) > button {
        background: #2196F3 !important; /* BINGO 5 (青) */
    }

    /* 右列 (Numbers系) */
    div[data-testid="column"]:nth-of-type(2) .stButton:nth-of-type(1) > button {
        background: #009688 !important; /* Numbers 4 (緑) */
    }
    div[data-testid="column"]:nth-of-type(2) .stButton:nth-of-type(2) > button {
        background: #009688 !important; /* Numbers 3 (緑) */
    }
    div[data-testid="column"]:nth-of-type(2) .stButton:nth-of-type(3) > button {
        background: #FF9800 !important; /* Mini (オレンジ) */
    }
    div[data-testid="column"]:nth-of-type(2) .stButton:nth-of-type(4) > button {
        background: #FFEB3B !important; /* クーちゃん (黄色) */
        color: #333 !important; /* 文字色を黒に */
    }

    /* ----------------------------------------------------
       液晶画面風の結果表示
    ---------------------------------------------------- */
    .lcd-screen {
        background-color: #9ea7a6; /* 昔の液晶画面っぽいグレー */
        border: 4px solid #555;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 20px;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.2);
        font-family: 'Courier New', monospace;
        text-align: center;
    }
    .lcd-title {
        color: #333;
        font-size: 14px;
        margin-bottom: 5px;
        font-weight: bold;
    }
    .lcd-number {
        font-size: 32px;
        letter-spacing: 5px;
        color: #000;
        font-weight: bold;
        background: rgba(255,255,255,0.4);
        border: 1px solid #777;
        display: inline-block;
        padding: 5px 15px;
        margin: 5px 0;
        border-radius: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# --- UI構築 ---

st.markdown("<h2 style='text-align: center; color: white;'>MIRU-COSMOS</h2>", unsafe_allow_html=True)

# 液晶画面エリア（結果表示）
active = st.session_state.active_game
if active:
    st.markdown('<div class="lcd-screen">', unsafe_allow_html=True)
    
    if active == 'N4':
        r_round, r_nums = get_n4_data()
        count = st.session_state.get('pred_count', 3)
        
        # 液晶：前回結果
        st.markdown(f'<div class="lcd-title">LAST RESULT ({r_round})</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="lcd-number">{"".join(r_nums)}</div>', unsafe_allow_html=True)
        
        st.markdown("<hr style='border-top: 1px dashed #555;'>", unsafe_allow_html=True)
        
        # 液晶：今回の予想
        st.markdown('<div class="lcd-title">PREDICTION</div>', unsafe_allow_html=True)
        preds = generate_nums(count, 4)
        for p_list in preds:
            st.markdown(f'<div class="lcd-number">{"".join(p_list)}</div>', unsafe_allow_html=True)
            
    else:
        st.markdown(f'<div class="lcd-title">{active} SYSTEM</div>', unsafe_allow_html=True)
        st.markdown('<div class="lcd-number">READY...</div>', unsafe_allow_html=True)
        
    st.markdown('</div>', unsafe_allow_html=True)

else:
    # 待機画面
    st.markdown("""
    <div class="lcd-screen">
        <div class="lcd-title">SYSTEM STANDBY</div>
        <div class="lcd-number">SELECT</div>
    </div>
    """, unsafe_allow_html=True)


# ボタン配置エリア（強制2列）
c1, c2 = st.columns(2)

with c1:
    st.button("LOTO 7", on_click=set_game, args=('L7',))
    st.button("LOTO 6", on_click=set_game, args=('L6',))
    st.button("MINI LOTO", on_click=set_game, args=('ML',))
    st.button("BINGO 5", on_click=set_game, args=('B5',))

with c2:
    st.button("Numbers 4", on_click=set_game, args=('N4',))
    st.button("Numbers 3", on_click=set_game, args=('N3',))
    st.button("Numbers Mini", on_click=set_game, args=('NM',))
    st.button("着替クー", on_click=set_game, args=('KC',))

# 口数スライダー
st.slider("予想口数", 1, 10, 3, key='pred_count')

# プロトコル文書
with st.expander("📝 MIRU PROTOCOL"):
    st.write("当てるために使わず、無駄な負けを消すために使う。")
