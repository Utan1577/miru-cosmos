import streamlit as st
import random
import requests
from bs4 import BeautifulSoup

# --- ページ設定 ---
st.set_page_config(page_title="MIRU-COSMOS", layout="centered")

# --- セッション管理 ---
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
        return r_round, r_num_str
    except:
        return "データ取得中", "----"

def generate_nums(count, length):
    return ["".join([str(random.randint(0, 9)) for _ in range(length)]) for _ in range(count)]

# --- スタイル設定 (黒ベース + 強制2列 + 液晶格納) ---
st.markdown("""
    <style>
    /* 1. 背景をクールな黒に戻す */
    .stApp {
        background-color: #000000 !important;
        color: white;
    }
    
    /* 2. スマホでボタンを強制的に2列にする絶対命令 */
    [data-testid="column"] {
        width: 50% !important;
        flex: 1 1 50% !important;
        min-width: 50% !important;
        padding: 0 4px !important;
    }
    
    /* 3. 液晶画面のデザイン */
    .screen-container {
        background-color: #9ea7a6; /* 液晶グレー */
        border: 4px solid #555;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 20px;
        text-align: center;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
        font-family: 'Courier New', monospace;
    }
    .screen-title {
        color: #333;
        font-size: 12px;
        font-weight: bold;
        margin-bottom: 5px;
        border-bottom: 1px dashed #555;
    }
    .screen-result {
        color: #000;
        font-size: 24px;
        font-weight: bold;
        letter-spacing: 5px;
        background: rgba(255,255,255,0.3);
        display: inline-block;
        padding: 2px 10px;
        margin-bottom: 10px;
        border: 1px solid #777;
    }
    .screen-pred {
        color: #000;
        font-size: 32px;
        font-weight: bold;
        letter-spacing: 8px;
        text-shadow: 1px 1px 0 rgba(255,255,255,0.5);
        margin: 5px 0;
    }

    /* 4. ボタンデザイン (色分け) */
    .stButton > button {
        width: 100%;
        height: 55px;
        border-radius: 12px !important;
        font-weight: bold !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 0 rgba(255,255,255,0.1);
        margin-bottom: 8px;
    }
    .stButton > button:active { transform: translateY(2px); box-shadow: none; }

    /* 左列 (LOTO系 - ピンク) */
    div[data-testid="column"]:nth-of-type(1) button { background: #E91E63 !important; }
    div[data-testid="column"]:nth-of-type(1) .stButton:last-of-type button { background: #2196F3 !important; } /* BINGO5は青 */

    /* 右列 (Numbers系 - 緑) */
    div[data-testid="column"]:nth-of-type(2) button { background: #009688 !important; }
    div[data-testid="column"]:nth-of-type(2) .stButton:nth-of-type(3) button { background: #FF9800 !important; } /* Mini */
    div[data-testid="column"]:nth-of-type(2) .stButton:nth-of-type(4) button { background: #FFEB3B !important; color: black !important; } /* クーちゃん */

    </style>
""", unsafe_allow_html=True)

# --- メイン画面 ---

st.markdown("<h2 style='text-align: center; color: #00FFFF;'>MIRU-COSMOS</h2>", unsafe_allow_html=True)

# 1. 液晶画面エリア (HTMLで直接描画して、数字を中に閉じ込める)
active = st.session_state.active_game
pred_count = st.session_state.get('p_count', 3)

html_content = ""

if active == 'N4':
    r_round, r_val = get_n4_data()
    predictions = generate_nums(pred_count, 4)
    
    # 予測数字のHTMLを作成
    preds_html = "".join([f"<div class='screen-pred'>{p}</div>" for p in predictions])
    
    html_content = f"""
    <div class="screen-container">
        <div class="screen-title">LAST RESULT ({r_round})</div>
        <div class="screen-result">{r_val}</div>
        <div class="screen-title" style="margin-top:10px;">PREDICTION</div>
        {preds_html}
    </div>
    """

elif active:
    # 他のゲーム用プレースホルダー
    html_content = f"""
    <div class="screen-container">
        <div class="screen-title">{active} SYSTEM</div>
        <div class="screen-pred">SYNC...</div>
    </div>
    """

else:
    # 待機画面
    html_content = """
    <div class="screen-container">
        <div class="screen-title">SYSTEM READY</div>
        <div class="screen-pred" style="font-size:20px;">SELECT GAME</div>
    </div>
    """

# ここで一気に描画（これが数字を枠内に閉じ込める鍵）
st.markdown(html_content, unsafe_allow_html=True)


# 2. 操作パネル (強制2列グリッド)
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

# 3. 設定
st.slider("口数設定 (Counts)", 1, 5, 3, key='p_count')

with st.expander("解析ロジック"):
    st.write("「当てるために使わず、無駄な負けを消すために使う。」")
