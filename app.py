import streamlit as st
import random
import requests
import json
import os
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from collections import Counter

# ==========================================
# MIRU-PAD: FINAL PERFECT EDITION
# Logic: Windmill + Physics
# UI: High-Fidelity CSS Replication
# ==========================================

# --- 1. CONFIG & CONSTANTS ---
DATA_FILE = "miru_status.json"
JST = timezone(timedelta(hours=9), 'JST')
st.set_page_config(page_title="MIRU-PAD", layout="centered", initial_sidebar_state="collapsed")

# 風車盤ロジック定数
WINDMILL_MAP = {
    'n1': [0, 7, 4, 1, 8, 5, 2, 9, 6, 3],
    'n2': [0, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    'n3': [0, 3, 6, 9, 2, 5, 8, 1, 4, 7],
    'n4': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
}
INDEX_MAP = {k: {num: i for i, num in enumerate(arr)} for k, arr in WINDMILL_MAP.items()}
GRAVITY_SECTORS = [4, 5, 6]
ANTI_GRAVITY_SECTORS = [9, 0, 1]

# --- 2. STATE MANAGEMENT (JSON) ---
def load_state():
    default_state = {
        "N4": {"last": "----", "preds": ["----"]*10},
        "N3": {"last": "----", "preds": ["---"]*10},
        "NM": {"last": "----", "preds": ["--"]*10}
    }
    if not os.path.exists(DATA_FILE): return default_state
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # マージ処理
            for k in default_state:
                if k not in data: data[k] = default_state[k]
            return data
    except: return default_state

def save_state(data):
    try:
        with open(DATA_FILE, "w") as f: json.dump(data, f)
    except: pass

# --- 3. LOGIC ENGINE ---
def fetch_history_logic(game_type):
    # N3とMiniは同じソース
    url_n4 = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
    url_n3 = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers3/index.html"
    
    target_url = url_n4 if game_type == 'N4' else url_n3
    cols = ['n1', 'n2', 'n3', 'n4'] if game_type == 'N4' else ['n1', 'n2', 'n3']
    
    try:
        res = requests.get(target_url, timeout=3)
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
        
        # 最新結果文字列
        last_val_str = "".join(map(str, history[0]))
        
        # 傾向分析 (スピン計算)
        trends = {}
        for i, col in enumerate(cols):
            spins = []
            for j in range(len(history) - 1):
                curr = INDEX_MAP[col][history[j][i]]
                prev = INDEX_MAP[col][history[j+1][i]]
                spins.append((curr - prev) % 10)
            trends[col] = Counter(spins).most_common(1)[0][0] if spins else 0
            
        return last_val_str, trends
    except:
        return None, None

def apply_gravity(idx, mode):
    if mode == 'chaos': return random.randint(0, 9)
    sectors = GRAVITY_SECTORS if mode == 'ace' else ANTI_GRAVITY_SECTORS
    candidates = [{'idx': idx, 'score': 1.0}]
    for s in [-1, 1, 0]:
        n_idx = (idx + s) % 10
        if n_idx in sectors: candidates.append({'idx': n_idx, 'score': 1.5})
    candidates.sort(key=lambda x: x['score'], reverse=True)
    # 確率で決定
    return candidates[0]['idx'] if random.random() < 0.7 else candidates[-1]['idx']

def run_prediction(game_type, last_val, trends):
    if not last_val: return ["ERROR"] * 10
    
    # NM(Mini)はN3のロジックで計算して下2桁を使う
    calc_type = 'N3' if game_type == 'NM' else game_type
    cols = ['n1', 'n2', 'n3', 'n4'] if calc_type == 'N4' else ['n1', 'n2', 'n3']
    
    last_nums = [int(d) for d in last_val]
    roles = ['ace', 'shift', 'chaos', 'ace', 'shift', 'ace', 'shift', 'ace', 'shift', 'chaos']
    preds = []
    seen = set()
    
    for role in roles:
        for _ in range(50):
            row_str = ""
            for i, col in enumerate(cols):
                curr = INDEX_MAP[col][last_nums[i]]
                spin = trends[col]
                
                # ゆらぎ
                if role == 'chaos': spin = random.randint(0, 9)
                elif role == 'shift': spin = (spin + random.choice([1, -1, 5])) % 10
                else: spin = spin if random.random() > 0.2 else (spin + 1) % 10
                
                final_idx = apply_gravity((curr + spin) % 10, role)
                row_str += str(WINDMILL_MAP[col][final_idx])
            
            # Miniなら下2桁
            check_val = row_str[-2:] if game_type == 'NM' else row_str
            
            if check_val not in seen:
                seen.add(check_val)
                preds.append(check_val)
                break
        
        # 埋まらなかった場合の予備
        if len(preds) < roles.index(role) + 1:
            digits = 2 if game_type == 'NM' else len(cols)
            preds.append("".join([str(random.randint(0,9)) for _ in range(digits)]))
            
    return preds

# --- 4. INIT & AUTO FETCH ---
if 'game_mode' not in st.session_state: st.session_state.game_mode = 'N4'
if 'count' not in st.session_state: st.session_state.count = 10

state = load_state()
gm = st.session_state.game_mode

# データがない場合、自動取得
if state[gm]["last"] == "----":
    l_val, trends = fetch_history_logic(gm)
    if l_val:
        state[gm]["last"] = l_val
        save_state(state)
        st.rerun()

# --- 5. UI CONSTRUCTION (CSS MAGIC) ---
st.markdown("""
<style>
    /* 全体設定 */
    .stApp { background-color: #000 !important; color: white; }
    .block-container { padding-top: 1rem; padding-bottom: 5rem; max-width: 100%; }
    
    /* 液晶画面 (HTMLで再現) */
    .lcd-container {
        background-color: #9ea7a6;
        border: 4px solid #555;
        border-radius: 12px;
        padding: 15px;
        min-height: 180px;
        box-shadow: inset 0 0 15px rgba(0,0,0,0.6);
        text-align: center;
        margin-bottom: 20px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    .lcd-title { font-size: 12px; color: #444; font-weight: bold; margin-bottom: 10px; width: 100%; }
    .lcd-grid {
        display: grid; grid-template-columns: 1fr 1fr; gap: 5px 30px;
        width: 90%;
    }
    .lcd-num {
        font-family: 'Courier New', monospace; font-weight: bold; 
        font-size: 26px; color: #000; letter-spacing: 3px; line-height: 1.0;
    }

    /* ボタン共通スタイル */
    div.stButton > button {
        border: 2px solid rgba(0,0,0,0.3) !important;
        box-shadow: 0 4px #000 !important;
        font-weight: bold !important;
        transition: all 0.1s !important;
        color: white !important;
    }
    div.stButton > button:active {
        transform: translateY(2px) !important;
        box-shadow: 0 1px #000 !important;
    }

    /* === コントロールバー (- / + / CALC) === */
    /* 丸いボタン (- / +) */
    div[data-testid="column"]:nth-of-type(1) div.stButton button,
    div[data-testid="column"]:nth-of-type(3) div.stButton button {
        border-radius: 50% !important;
        width: 45px !important;
        height: 45px !important;
        padding: 0 !important;
        font-size: 24px !important;
        background-color: #444 !important;
        border-color: #666 !important;
    }
    
    /* CALCボタン (白) */
    div[data-testid="column"]:nth-of-type(4) div.stButton button {
        border-radius: 25px !important;
        width: 100% !important;
        height: 45px !important;
        background-color: #ffffff !important; /* 白 */
        color: #000000 !important; /* 黒文字 */
        font-size: 16px !important;
        letter-spacing: 1px !important;
    }
    
    /* === ゲームグリッド (色分け) === */
    /* 左列 (Pink / Blue) */
    div[data-testid="column"]:nth-of-type(1) div.stButton button {
        border-radius: 10px !important;
        border: none !important;
        height: 50px !important;
    }
    
    /* 右列 (Green / Orange) */
    div[data-testid="column"]:nth-of-type(2) div.stButton button {
        border-radius: 10px !important;
        border: none !important;
        height: 50px !important;
    }

</style>
""", unsafe_allow_html=True)

# --- PART A: LCD SCREEN (Native Markdown) ---
# N3系の場合、Last Resultの表示を調整
disp_last = state[gm]["last"]
# Miniでも元のN3の当選番号(3桁)を表示するのが一般的だが、
# もし2桁だけ見せたいならスライスする。ここでは全桁表示。
if gm == 'NM' and len(disp_last) == 3:
    pass 
    
st.markdown(f"""
<div class="lcd-container">
    <div class="lcd-title">LAST RESULT ({gm}): {disp_last}</div>
    <div class="lcd-grid">
        {''.join([f'<div class="lcd-num">{p}</div>' for p in state[gm]["preds"][:st.session_state.count]])}
    </div>
</div>
""", unsafe_allow_html=True)

# --- PART B: CONTROL BAR ---
c1, c2, c3, c4 = st.columns([1, 1.5, 1, 2.5])

with c1:
    if st.button("－"):
        if st.session_state.count > 1: st.session_state.count -= 1
        st.rerun()
with c2:
    st.markdown(f"<div style='text-align:center; line-height:45px; font-size:20px; font-weight:bold;'>{st.session_state.count} 口</div>", unsafe_allow_html=True)
with c3:
    if st.button("＋"):
        if st.session_state.count < 10: st.session_state.count += 1
        st.rerun()
with c4:
    if st.button("CALC"):
        # 計算実行
        l_val, trends = fetch_history_logic(gm)
        if l_val:
            state[gm]["last"] = l_val
            state[gm]["preds"] = run_prediction(gm, l_val, trends)
            save_state(state)
            st.rerun()

st.write("") # Spacer

# --- PART C: GAME BUTTONS GRID ---
# 色指定のためのハック: 
# 左カラムのボタンは全部ピンク(または青)、右カラムは緑(またはオレンジ)にするCSSを適用済み。
# 個別の色指定(Bingo=Blue, Mini=Orange)は、Pythonロジックでボタンを描画する順序を利用して
# CSSのnth-of-type等で狙い撃ちするのはStreamlitの構造上不安定。
# そのため、今回は「左右の色分け」で統一感を持たせる。

# 左: #E91E63 (Pink), 右: #009688 (Green) を基本とする。
# Bingo5とUpdateだけ色を変えるためのCSSを追加注入。

st.markdown("""
<style>
/* 左列の基本: Pink */
div[data-testid="column"]:nth-of-type(1) div.row-widget button { background-color: #E91E63 !important; }
/* 右列の基本: Green */
div[data-testid="column"]:nth-of-type(2) div.row-widget button { background-color: #009688 !important; }

/* 個別上書き (Bingo 5 - 左列4番目) */
/* 構造上、行ごとにst.columnsを使っているため、nth-of-typeが効きにくい。
   しかし、行ごとにコンテナが分かれるため、
   "4つ目のstHorizontal > column 1 > button" という指定が必要。
   これは非常に複雑。
   
   ★解決策★
   シンプルに、session_stateを使って「今選ばれているゲーム」に白い枠線をつける機能(Active)を優先し、
   色は2色(Pink/Green)ベースで美しくまとめる。
   (Updateボタンだけ黄色にしたいが、緑でも機能的には問題ない)
*/
</style>
""", unsafe_allow_html=True)

# Row 1
r1_1, r1_2 = st.columns(2)
with r1_1: st.button("LOTO 7", disabled=True)
with r1_2: 
    if st.button("Numbers 4"): 
        st.session_state.game_mode = 'N4'
        st.rerun()

# Row 2
r2_1, r2_2 = st.columns(2)
with r2_1: st.button("LOTO 6", disabled=True)
with r2_2: 
    if st.button("Numbers 3"): 
        st.session_state.game_mode = 'N3'
        st.rerun()

# Row 3
r3_1, r3_2 = st.columns(2)
with r3_1: st.button("MINI LOTO", disabled=True)
with r3_2: 
    if st.button("Numbers mini"): 
        st.session_state.game_mode = 'NM'
        st.rerun()

# Row 4
r4_1, r4_2 = st.columns(2)
with r4_1: st.button("BINGO 5", disabled=True) # 本来は青
with r4_2: 
    if st.button("UPDATE DATA"): # 本来は黄色
        state[gm]["last"] = "----" 
        save_state(state)
        st.rerun()

# アクティブボタンの強調 (枠線を白くする)
# これもCSSでやるにはclassが必要だが、Streamlitはclassをつけられない。
# 代わりに、現在選択中のモード名をLCDに表示することでユーザーにフィードバックしている。
