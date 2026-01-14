import streamlit as st
import random
import requests
import json
import os
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from collections import Counter

# ==========================================
# MIRU-PAD: MOBILE GRID FIXED EDITION
# Logic: Python/JSON (Server Side)
# UI: Native Buttons + Force-Grid CSS
# ==========================================

# --- CONFIG ---
DATA_FILE = "miru_status.json"
JST = timezone(timedelta(hours=9), 'JST')
st.set_page_config(page_title="MIRU-PAD", layout="centered", initial_sidebar_state="collapsed")

# --- LOGIC CONSTANTS ---
WINDMILL_MAP = {
    'n1': [0, 7, 4, 1, 8, 5, 2, 9, 6, 3],
    'n2': [0, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    'n3': [0, 3, 6, 9, 2, 5, 8, 1, 4, 7],
    'n4': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
}
INDEX_MAP = {k: {num: i for i, num in enumerate(arr)} for k, arr in WINDMILL_MAP.items()}
GRAVITY_SECTORS = [4, 5, 6]
ANTI_GRAVITY_SECTORS = [9, 0, 1]

# --- STATE MANAGEMENT ---
def load_state():
    default = {
        "N4": {"last": "----", "preds": ["----"]*10},
        "N3": {"last": "----", "preds": ["---"]*10},
        "NM": {"last": "----", "preds": ["--"]*10}
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

# --- LOGIC FUNCTIONS ---
def fetch_history_logic(game_type):
    # N4かN3(NM含む)かでURL分岐
    target_g = 'N4' if game_type == 'N4' else 'N3'
    url = f"https://www.mizuhobank.co.jp/takarakuji/numbers/numbers{target_g[-1]}/index.html"
    cols = ['n1', 'n2', 'n3', 'n4'] if target_g == 'N4' else ['n1', 'n2', 'n3']
    
    try:
        res = requests.get(url, timeout=3)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.find_all('tr')
        history = []
        for row in rows:
            data = row.find('td', class_='alnCenter')
            if data:
                val = data.text.strip().replace(' ', '')
                if val.isdigit() and len(val) == len(cols):
                    history.append([int(d) for d in val])
        if not history: return None, None
        
        last_val_str = "".join(map(str, history[0]))
        trends = {}
        for i, col in enumerate(cols):
            spins = []
            for j in range(len(history) - 1):
                c = INDEX_MAP[col][history[j][i]]
                p = INDEX_MAP[col][history[j+1][i]]
                spins.append((c - p) % 10)
            trends[col] = Counter(spins).most_common(1)[0][0] if spins else 0
        return last_val_str, trends
    except: return None, None

def run_prediction(game_type, last_val, trends):
    if not last_val or last_val == "----": return ["ERROR"] * 10
    calc_g = 'N3' if game_type == 'NM' else game_type
    cols = ['n1', 'n2', 'n3', 'n4'] if calc_g == 'N4' else ['n1', 'n2', 'n3']
    last_nums = [int(d) for d in last_val]
    
    preds = []
    seen = set()
    
    for _ in range(30):
        row_str = ""
        for i, col in enumerate(cols):
            curr = INDEX_MAP[col][last_nums[i]]
            spin = trends[col]
            spin = (spin + random.choice([0, 1, -1, 5])) % 10
            
            # Simple Gravity
            final_idx = (curr + spin) % 10
            row_str += str(WINDMILL_MAP[col][final_idx])
            
        final_val = row_str[-2:] if game_type == 'NM' else row_str
        if final_val not in seen:
            seen.add(final_val)
            preds.append(final_val)
            if len(preds) >= 10: break
            
    while len(preds) < 10: preds.append("----")
    return preds

# --- MAIN APP ---
if 'game_mode' not in st.session_state: st.session_state.game_mode = 'N4'
if 'count' not in st.session_state: st.session_state.count = 10

state = load_state()
gm = st.session_state.game_mode

# 自動取得
if state[gm]["last"] == "----":
    l, t = fetch_history_logic(gm)
    if l:
        state[gm]["last"] = l
        save_state(state)
        st.rerun()

# === CSS: スマホレイアウト強制修正 ===
# ここが重要。スマホ(max-width: 640px)でもカラムを縦積みにさせない魔法。
st.markdown("""
<style>
    .stApp { background-color: #000 !important; color: white !important; }
    .block-container { padding-top: 1rem; max-width: 100%; padding-left: 0.5rem; padding-right: 0.5rem; }
    
    /* ボタン基本 */
    div.stButton > button {
        width: 100%;
        font-weight: bold !important;
        border: 2px solid rgba(0,0,0,0.3) !important;
        box-shadow: 0 4px #000 !important;
        margin-bottom: 5px !important;
    }
    div.stButton > button:active {
        transform: translateY(2px);
        box-shadow: 0 1px #000 !important;
    }

    /* === スマホ用グリッド強制 === */
    @media (max-width: 640px) {
        /* カラムの最小幅制限を解除して、無理やり並べる */
        div[data-testid="column"] {
            min-width: 0 !important;
            flex: 1 !important;
            padding: 0 2px !important;
        }
    }

    /* === LCD STYLE === */
    .lcd-box {
        background: #9ea7a6;
        border: 4px solid #555;
        border-radius: 12px;
        padding: 10px;
        min-height: 180px;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
        margin-bottom: 10px;
    }
    .lcd-num {
        font-family: 'Courier New', monospace; font-weight: bold; font-size: 26px; color: black; letter-spacing: 2px;
    }

    /* === CONTROL BAR STYLE (Round Buttons) === */
    /* マイナスとプラスボタンを丸くする */
    /* 1列目と3列目のボタン */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) div[data-testid="column"]:nth-of-type(1) button,
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) div[data-testid="column"]:nth-of-type(3) button {
        border-radius: 50% !important;
        height: 45px !important; width: 45px !important;
        background: #444 !important; color: white !important;
        padding: 0 !important; font-size: 20px !important;
    }
    
    /* CALCボタン (4列目) */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) div[data-testid="column"]:nth-of-type(4) button {
        background: #ffffff !important; color: #000000 !important; /* 白背景・黒文字 */
        border-radius: 20px !important; height: 45px !important;
    }

    /* === GAME GRID COLORS === */
    /* 色分けルール: 左カラム=Pink, 右カラム=Green */
    /* 左列のボタン */
    div[data-testid="column"]:nth-of-type(1) div.stButton button { background-color: #E91E63 !important; color: white !important; border: none !important; }
    /* 右列のボタン */
    div[data-testid="column"]:nth-of-type(2) div.stButton button { background-color: #009688 !important; color: white !important; border: none !important; }
    
    /* 例外: Mini LotoとNumbers Miniはピンクとオレンジにしたいが、
       今回はレイアウト優先でシンプルに 左:ピンク 右:緑 で統一する */
       
    /* Update Data (右下) を黄色に */
    /* 最後の行の右側を狙うのは難しいので緑のままで機能させる */
</style>
""", unsafe_allow_html=True)

# --- UI BUILD ---

# 1. LCD (HTML)
st.markdown(f"""
<div class="lcd-box">
    <div style="font-size:10px; color:#444; font-weight:bold; position:absolute; top:20px;">LAST RESULT ({gm}): {state[gm]["last"]}</div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:0px 20px; width:95%; margin-top:20px; text-align:center;">
        {''.join([f'<div class="lcd-num">{p}</div>' for p in state[gm]["preds"][:st.session_state.count]])}
    </div>
</div>
""", unsafe_allow_html=True)

# 2. Control Bar [-] [10] [+] [CALC]
# スマホで崩れないように比率を調整
c1, c2, c3, c4 = st.columns([1.2, 1.5, 1.2, 3])

with c1:
    if st.button("－"):
        if st.session_state.count > 1:
            st.session_state.count -= 1
            st.rerun()
with c2:
    st.markdown(f"<div style='text-align:center; line-height:45px; font-size:18px; font-weight:bold;'>{st.session_state.count} 口</div>", unsafe_allow_html=True)
with c3:
    if st.button("＋"):
        if st.session_state.count < 10:
            st.session_state.count += 1
            st.rerun()
with c4:
    # 22時まで待つロジックを入れるならここ。今は常に押せるようにしておく
    if st.button("CALC"):
        l, t = fetch_history_logic(gm)
        if l:
            state[gm]["last"] = l
            state[gm]["preds"] = run_prediction(gm, l, t)
            save_state(state)
            st.rerun()

st.write("") # Spacer

# 3. Game Grid
# ここもスマホで絶対に2列になるようにする
g_col1, g_col2 = st.columns(2)

with g_col1:
    st.button("LOTO 7", key="l7", disabled=True)
    st.button("LOTO 6", key="l6", disabled=True)
    st.button("MINI LOTO", key="ml", disabled=True)
    st.button("BINGO 5", key="bi", disabled=True)

with g_col2:
    if st.button("Numbers 4", key="n4"):
        st.session_state.game_mode = 'N4'
        st.rerun()
    if st.button("Numbers 3", key="n3"):
        st.session_state.game_mode = 'N3'
        st.rerun()
    if st.button("Numbers mini", key="nm"):
        st.session_state.game_mode = 'NM'
        st.rerun()
    if st.button("UPDATE DATA", key="upd"):
        state[gm]["last"] = "----" # 強制リロード用
        save_state(state)
        st.rerun()
