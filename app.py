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
# MIRU-PAD: FINAL FIXED EDITION
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
# クーちゃん絵柄（リンゴ, ミカン, メロン, ブドウ, モモ）
KCOO_MAP = {1: "🍎", 2: "🍊", 3: "🍈", 4: "🍇", 5: "🍑"}

# --- 3. STATE ---
def load_state():
    default = {
        "N4": {"last": "----", "preds": ["----"]*10},
        "N3": {"last": "----", "preds": ["---"]*10},
        "NM": {"last": "----", "preds": ["--"]*10},
        "KC": {"last": "----", "preds": ["----"]*10},
    }
    if not os.path.exists(DATA_FILE): return default
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            for k in default:
                if k not in data: data[k] = default[k]
            return data
    except: return default

def save_state(data):
    try:
        with open(DATA_FILE, "w") as f: json.dump(data, f)
    except: pass

# --- 4. LOGIC ---
def fetch_history_logic(game_type):
    # クーちゃん(KC)はネット予想要素が強いため、ここでは簡易的に「----」かランダムシード取得とする
    # (スクレイピングが難しいため)
    if game_type == 'KC':
        return "----", None

    target_g = 'N4' if game_type == 'N4' else 'N3'
    url = f"https://www.mizuhobank.co.jp/takarakuji/numbers/numbers{target_g[-1]}/index.html"
    cols = ['n1', 'n2', 'n3', 'n4'] if target_g == 'N4' else ['n1', 'n2', 'n3']
    
    try:
        # ヘッダー追加でブロック回避
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        history = []
        rows = soup.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'], class_='alnCenter')
            for cell in cells:
                val = cell.text.strip().replace(' ', '')
                if val.isdigit() and len(val) == len(cols):
                    history.append([int(d) for d in val])
                    break
            if history: break
            
        if not history: return None, None
        last_val_str = "".join(map(str, history[0]))
        
        trends = {}
        for i, col in enumerate(cols):
            spins = []
            trends[col] = (history[0][i] * 3) % 10 # 簡易トレンド
        return last_val_str, trends
    except: return None, None

def run_prediction(game_type, last_val, trends):
    # クーちゃん
    if game_type == 'KC':
        preds = []
        for _ in range(10):
            p = [KCOO_MAP[random.randint(1,5)] for _ in range(4)]
            preds.append("".join(p))
        return preds

    if not last_val or last_val == "----": return ["ERROR"] * 10
    
    calc_g = 'N3' if game_type == 'NM' else game_type
    cols = ['n1', 'n2', 'n3', 'n4'] if calc_g == 'N4' else ['n1', 'n2', 'n3']
    last_nums = [int(d) for d in last_val]
    
    preds = []
    seen = set()
    for _ in range(50):
        row = ""
        for i, col in enumerate(cols):
            curr = INDEX_MAP[col][last_nums[i]]
            spin = trends[col] if trends else 0
            spin = (spin + random.choice([0, 1, -1, 5])) % 10
            final = (curr + spin) % 10
            row += str(WINDMILL_MAP[col][final])
        
        val = row[-2:] if game_type == 'NM' else row
        if val not in seen:
            seen.add(val)
            preds.append(val)
            if len(preds) >= 10: break
    
    while len(preds) < 10: preds.append("----")
    return preds

# --- 5. INIT ---
if 'game_mode' not in st.session_state: st.session_state.game_mode = 'N4'
if 'count' not in st.session_state: st.session_state.count = 10

state = load_state()
gm = st.session_state.game_mode

# 自動取得
if gm != 'KC' and state[gm]["last"] == "----":
    l, t = fetch_history_logic(gm)
    if l:
        state[gm]["last"] = l
        save_state(state)
        st.rerun()

# ==========================================
# CSS: THE REAL FIX (FORCE GRID & COLORS)
# ==========================================
st.markdown("""
<style>
    /* Reset */
    .stApp { background-color: #000 !important; color: white !important; }
    .block-container { padding: 10px !important; max-width: 100% !important; }
    
    /* Button Base */
    div.stButton > button {
        width: 100%;
        border: 2px solid rgba(0,0,0,0.3) !important;
        box-shadow: 0 4px #000 !important;
        font-weight: bold !important;
        margin-bottom: 5px !important;
        border-radius: 12px !important;
        height: 50px !important;
    }
    div.stButton > button:active {
        transform: translateY(2px) !important;
        box-shadow: 0 1px #000 !important;
    }

    /* === スマホレイアウト強制 (50%ずつ配置) === */
    /* これで絶対に崩れない */
    div[data-testid="column"] {
        width: 50% !important;
        flex: 1 1 50% !important;
        min-width: 50% !important;
        max-width: 50% !important;
        padding: 0 4px !important;
    }
    
    /* コントロールバー (上段) だけは例外で比率を変える */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"] {
        width: auto !important;
        flex: 1 !important;
        min-width: 0 !important;
    }

    /* === LCD (見切れ修正) === */
    .lcd-box {
        background: #9ea7a6;
        border: 4px solid #555;
        border-radius: 12px;
        padding-top: 25px; /* 上余白確保 */
        padding-bottom: 10px;
        min-height: 180px;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
        margin-bottom: 15px;
        position: relative;
    }
    .lcd-label {
        font-size: 11px; color: #444; font-weight: bold; 
        position: absolute; top: 8px; width: 100%; text-align: center;
    }
    .lcd-grid {
        display: grid; grid-template-columns: 1fr 1fr; gap: 0px 20px; 
        width: 95%; text-align: center;
    }
    .lcd-num {
        font-family: 'Courier New', monospace; font-weight: bold; 
        font-size: 26px; color: black; letter-spacing: 2px;
    }

    /* === COLORS === */
    /* 上段: コントロールバー */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) {
        background: #222; border-radius: 30px; padding: 5px; margin-bottom: 10px;
    }
    /* 丸ボタン */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(1) button,
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(3) button {
        border-radius: 50% !important; width: 40px !important; height: 40px !important;
        background: #444 !important; color: white !important; font-size: 20px !important; padding: 0 !important;
        margin: 0 auto !important;
    }
    /* CALC (白) */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(4) button {
        background: #fff !important; color: #000 !important; border-radius: 20px !important; height: 40px !important;
    }

    /* === GAME GRID COLORS === */
    /* 左列 (Block 2) -> Pink */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) div[data-testid="column"]:nth-of-type(1) button {
        background: #E91E63 !important; color: white !important; border: none !important;
    }
    /* 右列 (Block 2) -> Green */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) div[data-testid="column"]:nth-of-type(2) button {
        background: #009688 !important; color: white !important; border: none !important;
    }
    
    /* === 例外色 (上書き) === */
    /* 左列4番目 (Bingo5) -> Blue */
    div[data-testid="column"]:nth-of-type(1) div.stVerticalBlock > div:nth-of-type(4) button {
        background-color: #2196F3 !important;
    }
    /* 右列3番目 (Mini) -> Orange */
    div[data-testid="column"]:nth-of-type(2) div.stVerticalBlock > div:nth-of-type(3) button {
        background-color: #FF9800 !important;
    }
    /* 右列4番目 (クーちゃん) -> Yellow */
    div[data-testid="column"]:nth-of-type(2) div.stVerticalBlock > div:nth-of-type(4) button {
        background-color: #FFEB3B !important; color: #333 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- UI ---

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
        if st.session_state.count > 1: st.session_state.count -= 1
with c2:
    st.markdown(f"<div style='text-align:center; font-size:18px; font-weight:bold; line-height:42px; white-space:nowrap;'>{st.session_state.count} 口</div>", unsafe_allow_html=True)
with c3:
    if st.button("＋"):
        if st.session_state.count < 10: st.session_state.count += 1
with c4:
    if st.button("CALC"):
        if gm == 'KC':
            state[gm]["preds"] = run_prediction(gm, None, None)
        else:
            l, t = fetch_history_logic(gm)
            if not l and state[gm]["last"] != "----": l = state[gm]["last"]
            state[gm]["preds"] = run_prediction(gm, l, t)
            if l: state[gm]["last"] = l
        save_state(state)
        # st.rerun() # ボタン押下で自動更新されるため不要(フラッシュ軽減)

st.write("") 

# 3. Game Grid (2列固定)
g1, g2 = st.columns(2)

with g1:
    st.button("LOTO 7", disabled=True)
    st.button("LOTO 6", disabled=True)
    st.button("MINI LOTO", disabled=True)
    st.button("BINGO 5", disabled=True) # Blue

with g2:
    if st.button("Numbers 4"): st.session_state.game_mode = 'N4'; st.rerun()
    if st.button("Numbers 3"): st.session_state.game_mode = 'N3'; st.rerun()
    if st.button("Numbers mini"): st.session_state.game_mode = 'NM'; st.rerun() # Orange
    if st.button("着替クー"): st.session_state.game_mode = 'KC'; st.rerun() # Yellow
