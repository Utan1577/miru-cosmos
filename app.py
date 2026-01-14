import streamlit as st
import random
import requests
import json
import os
from datetime import datetime, timedelta, timezone
import streamlit.components.v1 as components

# ==========================================
# MIRU-PAD: ULTIMATE FIX (LAYOUT & MULTI-GAME)
# ==========================================

# --- CONFIG ---
DATA_FILE = "miru_status_v3.json"
JST = timezone(timedelta(hours=9), 'JST')
st.set_page_config(page_title="MIRU-PAD", layout="centered", initial_sidebar_state="collapsed")

# --- STATE MANAGEMENT ---
if 'game_mode' not in st.session_state: st.session_state.game_mode = 'N4'
if 'count' not in st.session_state: st.session_state.count = 10

def load_state():
    default_state = {
        "date": "2000-01-01",
        "last_draw_n4": "----",
        "last_draw_n3": "----",
        "preds_n4": ["----"] * 10,
        "preds_n3": ["---"] * 10,
        "preds_mini": ["--"] * 10,
    }
    if not os.path.exists(DATA_FILE): return default_state
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # マージ (足りないキーがあればデフォルト値で埋める)
            for k, v in default_state.items():
                if k not in data: data[k] = v
            return data
    except: return default_state

def save_state(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f)

state = load_state()

# --- SCRAPING ENGINE (ROBUST) ---
def fetch_data(url, digits):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'Shift_JIS'
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.find_all('tr')
        for row in rows:
            data = row.find('td', class_='alnCenter')
            if data:
                val = data.text.strip().replace(' ', '')
                if val.isdigit() and len(val) == digits:
                    return val
        return None
    except: return None

def update_latest_results():
    # N4
    n4 = fetch_data("https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html", 4)
    if n4: state["last_draw_n4"] = n4
    # N3
    n3 = fetch_data("https://www.mizuhobank.co.jp/takarakuji/numbers/numbers3/index.html", 3)
    if n3: state["last_draw_n3"] = n3
    
    state["date"] = datetime.now(JST).strftime('%Y-%m-%d')
    save_state(state)

# 起動時に結果がなければ取りに行く
if state["last_draw_n4"] == "----" or state["last_draw_n3"] == "----":
    update_latest_results()

# --- LOGIC ENGINE ---
def run_simulation(game_type, last_val_str):
    # エラーチェック
    if not last_val_str or not last_val_str.isdigit():
        digits = 4 if game_type == 'N4' else (3 if game_type == 'N3' else 2)
        return ["-"*digits] * 10
        
    last_nums = [int(c) for c in last_val_str]
    last_sum = sum(last_nums)
    
    # パラメータ設定
    digits = 4
    if game_type == 'N3': digits = 3
    if game_type == 'MINI': digits = 2
    
    candidates = []
    attempts = 0
    while len(candidates) < 10 and attempts < 50000:
        attempts += 1
        nums = [random.randint(0, 9) for _ in range(digits)]
        
        # 簡易物理フィルター
        # 1. 合計値バランス（極端な値を避ける）
        s = sum(nums)
        avg = 4.5 * digits
        if not (avg * 0.4 <= s <= avg * 1.6): continue
        
        # 2. 7の排除（今日の呪い）
        if 7 in nums: continue
        
        candidates.append("".join(map(str, nums)))
        
    while len(candidates) < 10:
        candidates.append("".join([str(random.randint(0,9)) for _ in range(digits)]))
        
    return candidates

# --- UI & LAYOUT ---
st.markdown("""
<style>
    /* 全体設定 */
    .stApp { background-color: #000; color: #fff; }
    .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 100%; }
    
    /* 液晶画面 */
    .lcd-frame {
        background-color: #9ea7a6;
        border: 4px solid #555;
        border-radius: 12px;
        padding: 10px;
        margin-bottom: 10px;
        box-shadow: inset 0 0 15px rgba(0,0,0,0.6);
        text-align: center;
        min-height: 180px;
    }
    .lcd-title { font-size: 12px; color: #333; font-weight: bold; margin-bottom: 5px; }
    .lcd-grid { 
        display: grid; grid-template-columns: 1fr 1fr; gap: 5px 20px; 
        font-family: 'Courier New', monospace; font-weight: bold; font-size: 24px; color: #000;
        letter-spacing: 3px;
    }

    /* コントロールバー (Flexboxで強制横並び) */
    .control-bar {
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        background: #222;
        border-radius: 30px;
        padding: 5px 10px;
        margin-bottom: 15px;
        gap: 10px;
    }
    
    /* 丸いボタン (- / +) */
    .btn-circle {
        width: 40px; height: 40px; border-radius: 50%;
        background: #444; border: 2px solid #666; color: white;
        font-size: 20px; font-weight: bold; line-height: 36px; text-align: center;
        cursor: pointer; user-select: none;
    }
    .btn-circle:active { background: #666; transform: scale(0.95); }
    
    /* カウント表示 */
    .count-disp { font-size: 18px; font-weight: bold; color: white; white-space: nowrap; }

    /* CALCボタン */
    .btn-calc {
        flex-grow: 1; height: 40px; border-radius: 20px;
        background: #009688; border: none; color: white;
        font-size: 16px; font-weight: bold; line-height: 40px; text-align: center;
        cursor: pointer; box-shadow: 0 2px 5px rgba(0,0,0,0.5);
    }
    .btn-calc:active { background: #00796b; transform: translateY(2px); }

    /* ゲーム選択ボタン (Grid Layout) */
    .game-grid {
        display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
    }
    .g-btn {
        height: 50px; border-radius: 10px; border: none;
        color: white; font-weight: bold; font-size: 14px;
        cursor: pointer; width: 100%;
        box-shadow: 0 3px 0 rgba(0,0,0,0.4);
    }
    .g-btn:active { transform: translateY(3px); box-shadow: none; }
    
    /* 色定義 */
    .c-loto { background-color: #E91E63; }
    .c-num { background-color: #009688; }
    .c-mini { background-color: #FF9800; }
    .c-bingo { background-color: #2196F3; }
    .c-manage { background-color: #FFEB3B; color: #333; }
    
    /* アクティブ状態の強調 */
    .active { border: 2px solid #fff; box-shadow: 0 0 10px #fff; }

</style>
""", unsafe_allow_html=True)

# --- HEADER LOGIC (Which Data to Show) ---
gm = st.session_state.game_mode
if gm == 'N4':
    last_res = state["last_draw_n4"]
    preds = state["preds_n4"]
elif gm == 'N3':
    last_res = state["last_draw_n3"]
    preds = state["preds_n3"]
elif gm == 'MINI':
    # MiniはN3の下2桁
    full_n3 = state["last_draw_n3"]
    last_res = full_n3[-2:] if full_n3.isdigit() else "--"
    preds = state["preds_mini"]
else:
    last_res = "----"
    preds = ["COMING SOON"] * 10

# --- PART 1: LCD SCREEN ---
st.markdown(f"""
<div class="lcd-frame">
    <div class="lcd-title">LAST RESULT ({gm}): {last_res}</div>
    <div class="lcd-grid">
        {''.join([f'<div>{p}</div>' for p in preds[:st.session_state.count]])}
    </div>
</div>
""", unsafe_allow_html=True)

# --- PART 2: CONTROL BAR (Native Streamlit with Custom Container) ---
# ここでst.columnsを使うと崩れるので、あえてHTML/CSSでコンテナを作り、
# その中に「不可視のStreamlitボタン」を仕込むのではなく、
# Streamlitの機能(callback)を使うために st.columns を使うが、
# CSSで強制的に並べるアプローチをとる。

c1, c2, c3, c4 = st.columns([1, 2, 1, 3])

# CSS hack to force these columns to stay in one row
st.markdown("""
<style>
div[data-testid="column"] { display: flex; align-items: center; justify-content: center; }
div.stButton > button { width: 100%; margin: 0; }
</style>
""", unsafe_allow_html=True)

with c1:
    if st.button("－"):
        if st.session_state.count > 1: st.session_state.count -= 1
        st.rerun()
with c2:
    st.markdown(f"<div style='text-align:center; font-weight:bold; font-size:18px;'>{st.session_state.count} 口</div>", unsafe_allow_html=True)
with c3:
    if st.button("＋"):
        if st.session_state.count < 10: st.session_state.count += 1
        st.rerun()
with c4:
    # CALC Button
    if st.button("CALC", key="calc_main"):
        # 計算実行
        if gm == 'N4':
            state["preds_n4"] = run_simulation('N4', state["last_draw_n4"])
        elif gm == 'N3':
            state["preds_n3"] = run_simulation('N3', state["last_draw_n3"])
        elif gm == 'MINI':
            # Miniの計算
            state["preds_mini"] = run_simulation('MINI', state["last_draw_n3"]) # N3の結果をベースにする
            
        state["is_calculated"] = True
        save_state(state)
        st.rerun()

# --- PART 3: GAME SELECTOR BUTTONS ---
# HTMLボタンではなく、Streamlitのネイティブボタンにして機能させる
# CSSで色をつけるために key を利用してスタイルを当てる手もあるが、
# シンプルに columns でグリッドを作る

st.write("") # Spacer

row1_1, row1_2 = st.columns(2)
row2_1, row2_2 = st.columns(2)
row3_1, row3_2 = st.columns(2)
row4_1, row4_2 = st.columns(2)

# Custom CSS to color specific buttons based on aria-label or hierarchy is hard in Streamlit.
# Instead, we inject styles that target the buttons by order.

st.markdown("""
<style>
/* Button Coloring Logic by Nth-Child in the Grid */
/* Row 1 Col 1 (Loto7) - Pink */
div.row-widget.stHorizontal > div:nth-child(1) button { background-color: #E91E63; color: white; border: none; }
/* Row 1 Col 2 (N4) - Green */
div.row-widget.stHorizontal > div:nth-child(2) button { background-color: #009688; color: white; border: none; }

/* Specific Overrides for subsequent rows need careful targeting or just accept uniform style per column if easier.
   To make it exact match, we rely on the specific order. */
</style>
""", unsafe_allow_html=True)

# Helper to button style
def game_btn(label, mode, color_hex):
    # active style
    border = "2px solid white" if st.session_state.game_mode == mode else "none"
    return f"""
    <button style="
        width:100%; height:50px; background-color:{color_hex}; color:white; 
        border:{border}; border-radius:10px; font-weight:bold; cursor:pointer;"
    >{label}</button>
    """

# Since we can't inject raw HTML with click handlers easily back to Python, 
# we use st.button and try to style them as best as possible.

# ROW 1
with row1_1:
    st.button("LOTO 7", key="b_l7", disabled=True) 
with row1_2:
    if st.button("Numbers 4", key="b_n4"): 
        st.session_state.game_mode = 'N4'
        st.rerun()

# ROW 2
with row2_1:
    st.button("LOTO 6", key="b_l6", disabled=True)
with row2_2:
    if st.button("Numbers 3", key="b_n3"):
        st.session_state.game_mode = 'N3'
        st.rerun()

# ROW 3
with row3_1:
    st.button("MINI LOTO", key="b_ml", disabled=True)
with row3_2:
    if st.button("Numbers mini", key="b_mini"):
        st.session_state.game_mode = 'MINI'
        st.rerun()

# ROW 4
with row4_1:
    st.button("BINGO 5", key="b_bi", disabled=True)
with row4_2:
    if st.button("UPDATE DATA", key="b_upd"): # Manage Appの代わりにデータ更新ボタン化
        update_latest_results()
        st.rerun()

# 強制スタイル適用 (ボタンの色分け)
st.markdown("""
<style>
/* CSSで強引に色を指定 (順番依存) */
/* Loto系 (Left Column) */
div[data-testid="column"]:nth-of-type(1) button { background-color: #E91E63 !important; color: white !important; }
/* Numbers系 (Right Column) */
div[data-testid="column"]:nth-of-type(2) button { background-color: #009688 !important; color: white !important; }
/* Mini (Right Col, 3rd row) - Orange override needed? 
   Streamlit doesn't give classes per row easily. 
   We'll settle for Green for all Numbers to keep it clean, or use 'Numbers mini' text match if possible.
*/
/* Bingo (Left Col, 4th row) - Blue */
/* Update (Right Col, 4th row) - Yellow */
</style>
""", unsafe_allow_html=True)
