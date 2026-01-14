import streamlit as st
import random
import requests
import json
import os
import time
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from collections import Counter

# ==========================================
# MIRU-PAD: FINAL ARCHITECTURE (CSS FIXED)
# ==========================================

# --- 1. CONFIG ---
DATA_FILE = "miru_status.json"
st.set_page_config(page_title="MIRU-PAD", layout="centered", initial_sidebar_state="collapsed")

# --- 2. CONSTANTS ---
WINDMILL_MAP = {
    'n1': [0, 7, 4, 1, 8, 5, 2, 9, 6, 3],
    'n2': [0, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    'n3': [0, 3, 6, 9, 2, 5, 8, 1, 4, 7],
    'n4': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
}
INDEX_MAP = {k: {num: i for i, num in enumerate(arr)} for k, arr in WINDMILL_MAP.items()}
KCOO_MAP = {1: "🍎", 2: "🍊", 3: "🍈", 4: "🍇", 5: "🍑"}

# --- 3. STATE MANAGEMENT (AUTO REPAIR) ---
def load_state():
    # 完全な初期状態定義
    default = {
        "N4": {"last": "----", "preds": ["----"]*10},
        "N3": {"last": "----", "preds": ["---"]*10},
        "NM": {"last": "----", "preds": ["--"]*10},
        "KC": {"last": "----", "preds": ["----"]*10},
        "game_mode": "N4",
        "count": 10
    }
    
    if not os.path.exists(DATA_FILE): return default
    
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # 欠損キーがあればデフォルト値で埋める
            for k, v in default.items():
                if k not in data: data[k] = v
            # ネストされた辞書もチェック
            for g in ["N4", "N3", "NM", "KC"]:
                if g not in data: data[g] = default[g]
            return data
    except:
        return default

def save_state(data):
    try:
        with open(DATA_FILE, "w") as f: json.dump(data, f)
    except: pass

# --- 4. LOGIC ENGINE ---
def fetch_latest_data(game_type):
    if game_type == 'KC': return "----", None
    
    target = 'numbers4' if game_type == 'N4' else 'numbers3'
    url = f"https://www.mizuhobank.co.jp/takarakuji/numbers/{target}/index.html"
    digits = 4 if game_type == 'N4' else 3
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=4)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # テーブルから最新の結果を探す
        val = None
        for td in soup.find_all(['td', 'th'], class_='alnCenter'):
            text = td.text.strip().replace(' ', '')
            if text.isdigit() and len(text) == digits:
                val = text
                break
        
        if not val: return None, None
        
        # 簡易トレンド分析
        trends = {}
        cols = ['n1', 'n2', 'n3', 'n4'] if game_type == 'N4' else ['n1', 'n2', 'n3']
        nums = [int(c) for c in val]
        for i, col in enumerate(cols):
            trends[col] = (nums[i] + 1) % 10 # 簡易計算
            
        return val, trends
    except:
        return None, None

def run_simulation(game_type, last_val, trends):
    if game_type == 'KC':
        return ["".join([KCOO_MAP[random.randint(1,5)] for _ in range(4)]) for _ in range(10)]

    if not last_val or not trends: return ["ERROR"] * 10
    
    calc_g = 'N3' if game_type == 'NM' else game_type
    cols = ['n1', 'n2', 'n3', 'n4'] if calc_g == 'N4' else ['n1', 'n2', 'n3']
    last_nums = [int(c) for c in last_val]
    
    preds = []
    seen = set()
    
    for _ in range(50):
        row = ""
        for i, col in enumerate(cols):
            curr = INDEX_MAP[col][last_nums[i]]
            spin = trends[col]
            spin = (spin + random.choice([0, 1, -1, 5])) % 10
            final = (curr + spin) % 10
            row += str(WINDMILL_MAP[col][final])
        
        res = row[-2:] if game_type == 'NM' else row
        if res not in seen:
            seen.add(res)
            preds.append(res)
            if len(preds) >= 10: break
    
    while len(preds) < 10: preds.append("----")
    return preds

# --- 5. INITIALIZE ---
state = load_state()
if 'game_mode' not in st.session_state: st.session_state.game_mode = state.get('game_mode', 'N4')
if 'count' not in st.session_state: st.session_state.count = state.get('count', 10)

gm = st.session_state.game_mode

# データがない場合の自動取得
if gm != 'KC' and state[gm]["last"] == "----":
    l, t = fetch_latest_data(gm)
    if l:
        state[gm]["last"] = l
        save_state(state)
        st.rerun()

# ==========================================
# 6. CSS (THE FIX)
# ==========================================
st.markdown("""
<style>
    /* 全体設定 */
    .stApp { background-color: #000 !important; color: white !important; }
    .block-container { padding: 10px !important; max-width: 100% !important; }
    
    /* ボタンリセット */
    div.stButton > button {
        width: 100% !important;
        border: 2px solid rgba(0,0,0,0.3) !important;
        box-shadow: 0 4px #000 !important;
        font-weight: bold !important;
        margin-bottom: 5px !important;
        border-radius: 10px !important;
        height: 52px !important;
        color: white !important;
    }
    div.stButton > button:active {
        transform: translateY(2px) !important;
        box-shadow: 0 1px #000 !important;
    }

    /* === 液晶画面 === */
    .lcd-box {
        background: #9ea7a6;
        border: 4px solid #555;
        border-radius: 12px;
        padding-top: 25px; 
        padding-bottom: 10px;
        min-height: 180px;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
        margin-bottom: 15px;
        position: relative;
    }
    .lcd-label {
        font-size: 11px; color: #444; font-weight: bold; 
        position: absolute; top: 10px; width: 100%; text-align: center;
    }
    .lcd-grid {
        display: grid; grid-template-columns: 1fr 1fr; gap: 0px 20px; 
        width: 95%; text-align: center;
    }
    .lcd-num {
        font-family: 'Courier New', monospace; font-weight: bold; 
        font-size: 26px; color: black; letter-spacing: 2px;
    }

    /* === スマホ強制横並び (Flexbox Fix) === */
    /* Streamlitのレスポンシブ動作をCSSで上書きして無効化する */
    @media (max-width: 640px) {
        div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 8px !important;
        }
        div[data-testid="column"] {
            width: auto !important;
            flex: 1 !important;
            min-width: 0 !important;
            padding: 0 !important;
        }
    }

    /* === コントロールバー (1段目) === */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) {
        background-color: #222; border-radius: 30px; padding: 5px; margin-bottom: 10px; align-items: center;
    }
    /* 丸ボタン */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(1) button,
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(3) button {
        border-radius: 50% !important; width: 42px !important; height: 42px !important;
        background: #444 !important; color: white !important; font-size: 20px !important; padding: 0 !important;
        margin: 0 auto !important;
    }
    /* CALC (白) */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(4) button {
        background: #fff !important; color: #000 !important; border-radius: 20px !important; height: 42px !important;
    }

    /* === ゲームボタン色分け (2列のグリッド) === */
    /* 左カラム (1列目) */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div[data-testid="column"]:nth-of-type(1) button {
        background-color: #E91E63 !important; /* 基本ピンク */
    }
    /* 左カラム 4番目 (Bingo5) -> 青 */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div[data-testid="column"]:nth-of-type(1) div.stVerticalBlock > div:nth-of-type(4) button {
        background-color: #2196F3 !important;
    }

    /* 右カラム (2列目) */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div[data-testid="column"]:nth-of-type(2) button {
        background-color: #009688 !important; /* 基本緑 */
    }
    /* 右カラム 3番目 (Mini) -> オレンジ */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div[data-testid="column"]:nth-of-type(2) div.stVerticalBlock > div:nth-of-type(3) button {
        background-color: #FF9800 !important;
    }
    /* 右カラム 4番目 (着替クー) -> 黄色 */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div[data-testid="column"]:nth-of-type(2) div.stVerticalBlock > div:nth-of-type(4) button {
        background-color: #FFEB3B !important; color: #333 !important;
    }

</style>
""", unsafe_allow_html=True)

# --- UI BUILD ---

# 1. LCD
disp_last = state[gm]["last"]
st.markdown(f"""
<div class="lcd-box">
    <div class="lcd-label">LAST RESULT ({gm}) : {disp_last}</div>
    <div class="lcd-grid">
        {''.join([f'<div class="lcd-num">{p}</div>' for p in state[gm]["preds"][:st.session_state.count]])}
    </div>
</div>
""", unsafe_allow_html=True)

# 2. Control Bar
c1, c2, c3, c4 = st.columns([1, 1.5, 1, 2.5])
with c1:
    if st.button("－"):
        if st.session_state.count > 1: st.session_state.count -= 1; st.rerun()
with c2:
    st.markdown(f"<div style='text-align:center; font-size:18px; font-weight:bold; line-height:42px; white-space:nowrap;'>{st.session_state.count} 口</div>", unsafe_allow_html=True)
with c3:
    if st.button("＋"):
        if st.session_state.count < 10: st.session_state.count += 1; st.rerun()
with c4:
    if st.button("CALC"):
        if gm == 'KC':
            state[gm]["preds"] = run_simulation(gm, None, None)
        else:
            l, t = fetch_latest_data(gm)
            # データ取得失敗しても前回のデータで計算を回す
            if not l and state[gm]["last"] != "----": l = state[gm]["last"]
            state[gm]["preds"] = run_simulation(gm, l, t)
            if l: state[gm]["last"] = l
        
        save_state(state)
        st.rerun()

st.write("") 

# 3. Game Grid
g1, g2 = st.columns(2)

with g1:
    st.button("LOTO 7", disabled=True)
    st.button("LOTO 6", disabled=True)
    st.button("MINI LOTO", disabled=True)
    st.button("BINGO 5", disabled=True)

with g2:
    if st.button("Numbers 4"): st.session_state.game_mode = 'N4'; st.rerun()
    if st.button("Numbers 3"): st.session_state.game_mode = 'N3'; st.rerun()
    if st.button("Numbers mini"): st.session_state.game_mode = 'NM'; st.rerun()
    if st.button("着替クー"): st.session_state.game_mode = 'KC'; st.rerun()
