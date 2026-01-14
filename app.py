import streamlit as st
import random
import requests
import json
import os
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from collections import Counter

# ==========================================
# MIRU-PAD: PERFECT HYBRID EDITION
# Design: Exact Replica of User's HTML (CSS Forced)
# Logic: Python Backend (Scraping + JSON Sync)
# ==========================================

# --- CONFIG ---
DATA_FILE = "miru_status.json"
JST = timezone(timedelta(hours=9), 'JST')
st.set_page_config(page_title="MIRU-PAD", layout="centered", initial_sidebar_state="collapsed")

# --- WINDMILL LOGIC ---
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
    target_g = 'N4' if game_type == 'N4' else 'N3'
    url = f"https://www.mizuhobank.co.jp/takarakuji/numbers/numbers{target_g[-1]}/index.html"
    cols = ['n1', 'n2', 'n3', 'n4'] if target_g == 'N4' else ['n1', 'n2', 'n3']
    
    try:
        res = requests.get(url, timeout=5)
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
    
    for _ in range(50):
        row_str = ""
        for i, col in enumerate(cols):
            curr = INDEX_MAP[col][last_nums[i]]
            spin = trends[col]
            spin = (spin + random.choice([0, 1, -1, 5])) % 10
            final_idx = (curr + spin) % 10
            row_str += str(WINDMILL_MAP[col][final_idx])
        
        final_val = row_str[-2:] if game_type == 'NM' else row_str
        if final_val not in seen:
            seen.add(final_val)
            preds.append(final_val)
            if len(preds) >= 10: break
            
    while len(preds) < 10: preds.append("----")
    return preds

# --- INITIALIZATION ---
if 'game_mode' not in st.session_state: st.session_state.game_mode = 'N4'
if 'count' not in st.session_state: st.session_state.count = 10

state = load_state()
gm = st.session_state.game_mode

if state[gm]["last"] == "----":
    l, t = fetch_history_logic(gm)
    if l:
        state[gm]["last"] = l
        save_state(state)
        st.rerun()

# ==========================================
# CSS: THE ULTIMATE FIX (MOBILE GRID)
# ==========================================
st.markdown("""
<style>
    /* 1. Global Reset */
    .stApp { background-color: #000 !important; color: white !important; }
    .block-container { 
        padding-top: 1rem !important; 
        padding-left: 0.5rem !important; 
        padding-right: 0.5rem !important; 
        max-width: 100% !important; 
    }
    
    /* 2. Button Styling (Base) */
    div.stButton > button {
        width: 100%;
        border: 2px solid rgba(0,0,0,0.3) !important;
        box-shadow: 0 4px #000 !important;
        font-weight: bold !important;
        margin-bottom: 6px !important;
        border-radius: 10px !important;
        height: 50px !important;
    }
    div.stButton > button:active {
        transform: translateY(2px);
        box-shadow: 0 1px #000 !important;
    }

    /* 3. MOBILE GRID ENFORCER (Important!) */
    /* モバイルでも横並びを強制する最強の指定 */
    @media (max-width: 640px) {
        div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 8px !important;
        }
        div[data-testid="column"] {
            flex: 1 !important;
            min-width: 0 !important; /* 縮小を許可 */
            width: auto !important;
        }
    }

    /* 4. LCD Screen */
    .lcd-box {
        background: #9ea7a6;
        border: 4px solid #555;
        border-radius: 12px;
        padding: 10px;
        min-height: 180px;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
        margin-bottom: 20px;
    }
    .lcd-num {
        font-family: 'Courier New', monospace; font-weight: bold; font-size: 26px; color: black; letter-spacing: 2px;
        text-align: center; white-space: nowrap;
    }

    /* 5. Control Bar Specifics */
    /* Block 1 = Control Bar */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) {
        align-items: center !important;
        background-color: #222;
        border-radius: 30px;
        padding: 5px 10px;
        margin-bottom: 15px;
    }
    
    /* Round Buttons [-] [+] */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(1) button,
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(3) button {
        border-radius: 50% !important;
        width: 40px !important; height: 40px !important;
        padding: 0 !important; font-size: 20px !important;
        background: #444 !important; color: white !important;
        border-color: #666 !important;
        margin: 0 auto !important;
        min-width: 40px !important; /* 潰れ防止 */
    }
    
    /* CALC Button */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(4) button {
        background: #ffffff !important; color: #000000 !important;
        border-radius: 20px !important; height: 40px !important;
    }

    /* 6. Game Grid Colors (By Row Structure) */
    
    /* Row 1: [LOTO7] [N4] */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div:nth-child(1) button { background: #E91E63 !important; color: white !important; border:none!important; }
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div:nth-child(2) button { background: #009688 !important; color: white !important; border:none!important; }

    /* Row 2: [LOTO6] [N3] */
    div[data-testid="stHorizontalBlock"]:nth-of-type(3) > div:nth-child(1) button { background: #E91E63 !important; color: white !important; border:none!important; }
    div[data-testid="stHorizontalBlock"]:nth-of-type(3) > div:nth-child(2) button { background: #009688 !important; color: white !important; border:none!important; }

    /* Row 3: [MINI LOTO] [N-MINI] */
    div[data-testid="stHorizontalBlock"]:nth-of-type(4) > div:nth-child(1) button { background: #E91E63 !important; color: white !important; border:none!important; }
    div[data-testid="stHorizontalBlock"]:nth-of-type(4) > div:nth-child(2) button { background: #FF9800 !important; color: white !important; border:none!important; }

    /* Row 4: [BINGO5] [UPDATE] */
    div[data-testid="stHorizontalBlock"]:nth-of-type(5) > div:nth-child(1) button { background: #2196F3 !important; color: white !important; border:none!important; }
    div[data-testid="stHorizontalBlock"]:nth-of-type(5) > div:nth-child(2) button { background: #FFEB3B !important; color: #333 !important; border:none!important; }

</style>
""", unsafe_allow_html=True)

# --- UI RENDER ---

# 1. LCD Screen
disp_last = state[gm]["last"]
st.markdown(f"""
<div class="lcd-box">
    <div style="font-size:10px; color:#444; font-weight:bold; position:absolute; top:15px;">LAST RESULT ({gm}): {disp_last}</div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:0px 20px; width:95%; margin-top:15px; text-align:center;">
        {''.join([f'<div class="lcd-num">{p}</div>' for p in state[gm]["preds"][:st.session_state.count]])}
    </div>
</div>
""", unsafe_allow_html=True)

# 2. Control Bar (Block 1)
c1, c2, c3, c4 = st.columns([1, 1.5, 1, 3])
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
        l, t = fetch_history_logic(gm)
        if l:
            state[gm]["last"] = l
            state[gm]["preds"] = run_prediction(gm, l, t)
            save_state(state)
            st.rerun()

# 3. Game Grid Rows
# Row 1 (Block 2)
r1_1, r1_2 = st.columns(2)
with r1_1: st.button("LOTO 7", disabled=True)
with r1_2: 
    if st.button("Numbers 4"): st.session_state.game_mode = 'N4'; st.rerun()

# Row 2 (Block 3)
r2_1, r2_2 = st.columns(2)
with r2_1: st.button("LOTO 6", disabled=True)
with r2_2: 
    if st.button("Numbers 3"): st.session_state.game_mode = 'N3'; st.rerun()

# Row 3 (Block 4)
r3_1, r3_2 = st.columns(2)
with r3_1: st.button("MINI LOTO", disabled=True)
with r3_2: 
    if st.button("Numbers mini"): st.session_state.game_mode = 'NM'; st.rerun()

# Row 4 (Block 5)
r4_1, r4_2 = st.columns(2)
with r4_1: st.button("BINGO 5", disabled=True)
with r4_2: 
    if st.button("UPDATE DATA"):
        state[gm]["last"] = "----"
        save_state(state)
        st.rerun()
