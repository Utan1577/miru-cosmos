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
# MIRU-PAD: FINAL COMPLETE EDITION
# Design: Native Buttons with HTML-Clone CSS
# UX: No Flash (AJAX), Mobile Optimized
# ==========================================

# --- 1. CONFIG ---
DATA_FILE = "miru_status.json"
JST = timezone(timedelta(hours=9), 'JST')
st.set_page_config(page_title="MIRU-PAD", layout="centered", initial_sidebar_state="collapsed")

# --- 2. LOGIC CONSTANTS ---
WINDMILL_MAP = {
    'n1': [0, 7, 4, 1, 8, 5, 2, 9, 6, 3],
    'n2': [0, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    'n3': [0, 3, 6, 9, 2, 5, 8, 1, 4, 7],
    'n4': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
}
INDEX_MAP = {k: {num: i for i, num in enumerate(arr)} for k, arr in WINDMILL_MAP.items()}
GRAVITY_SECTORS = [4, 5, 6]

# 着せかえクーちゃんの絵文字マップ (リンゴ, ミカン, メロン, ブドウ, モモ)
KCOO_MAP = {1: "🍎", 2: "🍊", 3: "🍈", 4: "🍇", 5: "🍑"}

# --- 3. STATE MANAGEMENT ---
def load_state():
    default = {
        "N4": {"last": "----", "preds": ["----"]*10},
        "N3": {"last": "----", "preds": ["---"]*10},
        "NM": {"last": "----", "preds": ["--"]*10},
        "KC": {"last": "----", "preds": ["----"]*10}, # クーちゃん追加
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

# --- 4. LOGIC FUNCTIONS ---
def fetch_history_logic(game_type):
    if game_type == 'KC': return "----", None # クーちゃんはスクレイピング難易度高いため一旦プレースホルダー
    
    target_g = 'N4' if game_type == 'N4' else 'N3'
    url = f"https://www.mizuhobank.co.jp/takarakuji/numbers/numbers{target_g[-1]}/index.html"
    cols = ['n1', 'n2', 'n3', 'n4'] if target_g == 'N4' else ['n1', 'n2', 'n3']
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        history = []
        # 最新のテーブル構造に対応
        rows = soup.find_all('tr')
        for row in rows:
            # thやtd混在に対応
            cells = row.find_all(['td', 'th'], class_='alnCenter')
            for cell in cells:
                val = cell.text.strip().replace(' ', '')
                if val.isdigit() and len(val) == len(cols):
                    history.append([int(d) for d in val])
                    break # 1行で1つ見つけたら次へ
            if history: break # 最新1件だけでいい
            
        if not history: return None, None
        
        last_val_str = "".join(map(str, history[0]))
        
        trends = {}
        for i, col in enumerate(cols):
            spins = []
            # 本来は履歴が必要だが、簡易版としてランダムシード代わりにする
            trends[col] = (history[0][i] * 7) % 10 
            
        return last_val_str, trends
    except: return None, None

def run_prediction(game_type, last_val, trends):
    # クーちゃん専用ロジック
    if game_type == 'KC':
        preds = []
        for _ in range(10):
            # 4つの絵柄を選ぶ
            p = [KCOO_MAP[random.randint(1,5)] for _ in range(4)]
            preds.append("".join(p))
        return preds

    if not last_val or last_val == "----": return ["----"] * 10
    
    calc_g = 'N3' if game_type == 'NM' else game_type
    cols = ['n1', 'n2', 'n3', 'n4'] if calc_g == 'N4' else ['n1', 'n2', 'n3']
    last_nums = [int(d) for d in last_val]
    
    preds = []
    seen = set()
    
    for _ in range(50):
        row_str = ""
        for i, col in enumerate(cols):
            curr = INDEX_MAP[col][last_nums[i]]
            spin = trends[col] if trends else 0
            spin = (spin + random.choice([0, 1, -1, 5, 3])) % 10
            final_idx = (curr + spin) % 10
            row_str += str(WINDMILL_MAP[col][final_idx])
        
        val = row_str[-2:] if game_type == 'NM' else row_str
        if val not in seen:
            seen.add(val)
            preds.append(val)
            if len(preds) >= 10: break
            
    while len(preds) < 10: preds.append("----")
    return preds

# --- 5. INITIALIZATION ---
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
# 6. CSS (DESIGN CLONE)
# ==========================================
st.markdown("""
<style>
    /* ベース */
    .stApp { background-color: #000 !important; color: white !important; }
    .block-container { padding: 10px !important; max-width: 100% !important; }
    
    /* ボタンリセット */
    div.stButton > button {
        width: 100%;
        border: 2px solid rgba(0,0,0,0.3) !important;
        box-shadow: 0 3px #000 !important;
        font-weight: bold !important;
        margin-bottom: 4px !important;
        border-radius: 12px !important;
        height: 50px !important;
        font-family: sans-serif !important;
    }
    div.stButton > button:active {
        transform: translateY(2px) !important;
        box-shadow: 0 1px #000 !important;
    }

    /* === スマホ横並び強制 (ここが肝) === */
    @media (max-width: 640px) {
        div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 8px !important;
        }
        div[data-testid="column"] {
            min-width: 0 !important;
            flex: 1 !important;
            width: auto !important;
            padding: 0 !important;
        }
    }

    /* === 液晶画面 (見切れ修正) === */
    .lcd-box {
        background: #9ea7a6;
        border: 4px solid #555;
        border-radius: 12px;
        /* 上の余白を増やして文字切れを防ぐ */
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

    /* === コントロールバー (上段) === */
    /* 背景色と形状 */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) {
        background-color: #222; border-radius: 30px; padding: 5px 10px; margin-bottom: 10px;
        align-items: center;
    }
    /* [-] [+] ボタン (丸く) */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(1) button,
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(3) button {
        border-radius: 50% !important;
        width: 40px !important; height: 40px !important;
        background: #444 !important; color: white !important;
        border-color: #666 !important;
        font-size: 20px !important; padding: 0 !important;
        margin: 0 auto !important;
    }
    /* CALC ボタン (白) */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-of-type(4) button {
        background: #ffffff !important; color: #000000 !important;
        border-radius: 20px !important; height: 40px !important;
    }

    /* === ゲームボタン色分け === */
    /* 行ごとに st.columns(2) を作っているので、nth-of-type で行を指定し、
       その中の nth-child で左右を指定する。
    */

    /* --- 行1: LOTO7(Pink) | Numbers4(Green) --- */
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div:nth-child(1) button { background: #E91E63 !important; color: white !important; border:none!important; }
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) > div:nth-child(2) button { background: #009688 !important; color: white !important; border:none!important; }

    /* --- 行2: LOTO6(Pink) | Numbers3(Green) --- */
    div[data-testid="stHorizontalBlock"]:nth-of-type(3) > div:nth-child(1) button { background: #E91E63 !important; color: white !important; border:none!important; }
    div[data-testid="stHorizontalBlock"]:nth-of-type(3) > div:nth-child(2) button { background: #009688 !important; color: white !important; border:none!important; }

    /* --- 行3: MINI LOTO(Pink) | Numbers mini(Orange) --- */
    div[data-testid="stHorizontalBlock"]:nth-of-type(4) > div:nth-child(1) button { background: #E91E63 !important; color: white !important; border:none!important; }
    div[data-testid="stHorizontalBlock"]:nth-of-type(4) > div:nth-child(2) button { background: #FF9800 !important; color: white !important; border:none!important; }

    /* --- 行4: BINGO5(Blue) | 着替クー(Yellow) --- */
    div[data-testid="stHorizontalBlock"]:nth-of-type(5) > div:nth-child(1) button { background: #2196F3 !important; color: white !important; border:none!important; }
    div[data-testid="stHorizontalBlock"]:nth-of-type(5) > div:nth-child(2) button { background: #FFEB3B !important; color: #333 !important; border:none!important; }

</style>
""", unsafe_allow_html=True)

# --- UI RENDER ---

# 1. LCD Screen
disp_last = state[gm]["last"]
st.markdown(f"""
<div class="lcd-box">
    <div class="lcd-label">LAST RESULT ({gm}) : {disp_last}</div>
    <div class="lcd-grid">
        {''.join([f'<div class="lcd-num">{p}</div>' for p in state[gm]["preds"][:st.session_state.count]])}
    </div>
</div>
""", unsafe_allow_html=True)

# 2. Control Bar (Block 1)
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
            # クーちゃん計算
            state[gm]["preds"] = run_prediction(gm, None, None)
            save_state(state)
        else:
            # ナンバーズ計算
            l, t = fetch_history_logic(gm)
            # 取得できなくても計算は回す(過去データ/ランダム利用)
            if not l and state[gm]["last"] != "----": l = state[gm]["last"]
            state[gm]["preds"] = run_prediction(gm, l, t)
            if l: state[gm]["last"] = l
            save_state(state)
        st.rerun()

# 3. Game Grid
st.write("") # Spacer

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
    if st.button("着替クー"): 
        st.session_state.game_mode = 'KC'
        st.rerun()
