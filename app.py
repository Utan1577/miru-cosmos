import streamlit as st
import random
import requests
import json
import os
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from collections import Counter

# ==========================================
# MIRU-PAD: HYBRID GENESIS
# Design: Cloned from User's HTML
# Logic: Python Backend Active
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

def apply_gravity(idx, mode):
    if mode == 'chaos': return random.randint(0, 9)
    sectors = GRAVITY_SECTORS if mode == 'ace' else ANTI_GRAVITY_SECTORS
    candidates = [{'idx': idx, 'score': 1.0}]
    for s in [-1, 1, 0]:
        n_idx = (idx + s) % 10
        if n_idx in sectors: candidates.append({'idx': n_idx, 'score': 1.5})
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[0]['idx'] if random.random() < 0.7 else candidates[-1]['idx']

def run_prediction(game_type, last_val, trends):
    if not last_val or last_val == "----": return ["ERROR"] * 10
    calc_g = 'N3' if game_type == 'NM' else game_type
    cols = ['n1', 'n2', 'n3', 'n4'] if calc_g == 'N4' else ['n1', 'n2', 'n3']
    last_nums = [int(d) for d in last_val]
    
    preds = []
    seen = set()
    roles = ['ace', 'shift', 'chaos', 'ace', 'shift', 'ace', 'shift', 'ace', 'shift', 'chaos']
    
    for role in roles:
        for _ in range(20):
            row_str = ""
            for i, col in enumerate(cols):
                curr = INDEX_MAP[col][last_nums[i]]
                spin = trends[col]
                spin = (spin + random.choice([0, 1, -1, 5])) % 10
                final_idx = apply_gravity((curr + spin) % 10, role)
                row_str += str(WINDMILL_MAP[col][final_idx])
            
            final_val = row_str[-2:] if game_type == 'NM' else row_str
            if final_val not in seen:
                seen.add(final_val)
                preds.append(final_val)
                break
        if len(preds) < roles.index(role) + 1:
             preds.append("".join([str(random.randint(0,9)) for _ in range(len(final_val))]))
             
    return preds

# --- INIT ---
if 'game_mode' not in st.session_state: st.session_state.game_mode = 'N4'
if 'count' not in st.session_state: st.session_state.count = 10

state = load_state()
gm = st.session_state.game_mode

# Auto Fetch
if state[gm]["last"] == "----":
    l, t = fetch_history_logic(gm)
    if l:
        state[gm]["last"] = l
        save_state(state)
        st.rerun()

# ==========================================
# CSS INJECTION (FORCE MOBILE GRID)
# ==========================================
st.markdown("""
<style>
    /* 1. Reset & Base */
    .stApp { background-color: #000 !important; color: white !important; }
    .block-container { 
        padding: 10px !important; 
        max-width: 100% !important; 
    }
    
    /* 2. Button Reset */
    div.stButton > button {
        width: 100%;
        border: 2px solid rgba(0,0,0,0.3) !important;
        box-shadow: 0 4px #000 !important;
        font-weight: bold !important;
        margin: 2px 0 !important;
    }
    div.stButton > button:active {
        transform: translateY(2px);
        box-shadow: 0 1px #000 !important;
    }

    /* 3. MOBILE GRID ENFORCER (The Fix) */
    /* Streamlit's stack behavior is overridden here */
    
    /* Control Bar (Row 1) -> Force 4 items in a row */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        gap: 5px !important;
    }
    
    /* Game Grid (Row 2) -> Force 2 columns */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 8px !important;
    }
    
    /* Force columns to respect width */
    div[data-testid="column"] {
        flex: 1 1 0px !important;
        min-width: 0 !important;
    }

    /* 4. COLORING (Targeting by structure) */
    
    /* --- Control Bar Colors --- */
    /* [-] [+] Buttons */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(1) button,
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(3) button {
        border-radius: 50% !important;
        width: 40px !important; height: 40px !important;
        background: #444 !important; color: white !important;
        padding: 0 !important; font-size: 20px !important;
        margin: 0 auto !important;
    }
    /* CALC Button */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(4) button {
        background: #ffffff !important; color: #000000 !important;
        border-radius: 20px !important;
    }

    /* --- Game Grid Colors --- */
    /* Left Column (Pink Base) */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div[data-testid="column"]:nth-of-type(1) button {
        background-color: #E91E63 !important; color: white !important; border: none !important;
        height: 50px !important; border-radius: 10px !important;
    }
    /* Right Column (Green Base) */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div[data-testid="column"]:nth-of-type(2) button {
        background-color: #009688 !important; color: white !important; border: none !important;
        height: 50px !important; border-radius: 10px !important;
    }

    /* Exceptions (Colors) */
    /* Mini Loto (Left 3) -> Keep Pink */
    /* Numbers Mini (Right 3) -> Orange (#FF9800) */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div[data-testid="column"]:nth-of-type(2) div.stVerticalBlock > div:nth-of-type(3) button {
        background-color: #FF9800 !important;
    }
    /* Bingo 5 (Left 4) -> Blue (#2196F3) */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div[data-testid="column"]:nth-of-type(1) div.stVerticalBlock > div:nth-of-type(4) button {
        background-color: #2196F3 !important;
    }
    /* Update (Right 4) -> Yellow (#FFEB3B) */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div[data-testid="column"]:nth-of-type(2) div.stVerticalBlock > div:nth-of-type(4) button {
        background-color: #FFEB3B !important; color: #333 !important;
    }
    
    /* LCD Screen Style */
    .lcd-box {
        background: #9ea7a6;
        border: 4px solid #555;
        border-radius: 12px;
        padding: 10px;
        min-height: 180px;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
        margin-bottom: 15px;
    }
    .lcd-num {
        font-family: 'Courier New', monospace; font-weight: bold; font-size: 26px; color: black; letter-spacing: 2px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- UI RENDER ---

# 1. LCD Screen (HTML Injection)
disp_last = state[gm]["last"]
st.markdown(f"""
<div class="lcd-box">
    <div style="font-size:10px; color:#444; font-weight:bold; position:absolute; top:20px;">LAST RESULT ({gm}): {disp_last}</div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:0px 10px; width:100%; margin-top:20px; text-align:center;">
        {''.join([f'<div class="lcd-num">{p}</div>' for p in state[gm]["preds"][:st.session_state.count]])}
    </div>
</div>
""", unsafe_allow_html=True)

# 2. Control Bar (Native Buttons with CSS Override)
c1, c2, c3, c4 = st.columns([1, 1.5, 1, 3])
with c1:
    if st.button("－"):
        if st.session_state.count > 1: st.session_state.count -= 1; st.rerun()
with c2:
    st.markdown(f"<div style='text-align:center; font-size:18px; font-weight:bold; line-height:45px; white-space:nowrap;'>{st.session_state.count} 口</div>", unsafe_allow_html=True)
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

st.write("") 

# 3. Game Grid (Native Buttons with CSS Override)
g1, g2 = st.columns(2)

with g1:
    st.button("LOTO 7", key="l7", disabled=True)
    st.button("LOTO 6", key="l6", disabled=True)
    st.button("MINI LOTO", key="ml", disabled=True)
    st.button("BINGO 5", key="bi", disabled=True)

with g2:
    if st.button("Numbers 4", key="n4"): st.session_state.game_mode = 'N4'; st.rerun()
    if st.button("Numbers 3", key="n3"): st.session_state.game_mode = 'N3'; st.rerun()
    if st.button("Numbers mini", key="nm"): st.session_state.game_mode = 'NM'; st.rerun()
    if st.button("UPDATE DATA", key="upd"): state[gm]["last"] = "----"; save_state(state); st.rerun()
