import streamlit as st
import random
import requests
import json
import os
import time
from datetime import datetime, timedelta, timezone
import streamlit.components.v1 as components

# ==========================================
# MIRU-PAD: AUTONOMOUS (DESIGN FIXED V2)
# ==========================================

# --- CONFIG & DATA ---
DATA_FILE = "miru_status.json"
JST = timezone(timedelta(hours=9), 'JST')
st.set_page_config(page_title="MIRU-PAD", layout="centered", initial_sidebar_state="collapsed")

# --- 1. GLOBAL SYNC ENGINE (JSON) ---
def load_state():
    default_state = {
        "date": "2000-01-01",
        "last_draw": "----",
        "predictions_n4": ["----"] * 10,
        "is_calculated": False
    }

    if not os.path.exists(DATA_FILE):
        return default_state
    
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # データ構造の自動修復
            if "predictions_n4" not in data:
                data["predictions_n4"] = default_state["predictions_n4"]
            if "last_draw" not in data:
                data["last_draw"] = default_state["last_draw"]
            return data
    except:
        return default_state

def save_state(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# --- 2. DATA FETCHING ---
def fetch_latest_result():
    # スクレイピング強化版
    try:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        res = requests.get(url, timeout=5)
        res.encoding = 'Shift_JIS'
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.find_all('tr')
        for row in rows:
            data = row.find('td', class_='alnCenter')
            if data:
                val = data.text.strip().replace(' ', '')
                if val.isdigit() and len(val) == 4:
                    return val
        return None
    except:
        return None

# --- 3. COLD MACHINE LOGIC (PRO MODE) ---
def run_simulation(last_draw_str):
    # 前回結果が正しく取れていない場合は計算しない
    if not last_draw_str or not last_draw_str.isdigit() or last_draw_str == "0000":
        return ["ERROR"] * 10

    try:
        last_nums = [int(c) for c in last_draw_str]
        last_sum = sum(last_nums)
    except:
        return ["ERROR"] * 10

    # [A] 合計値の平均回帰
    if last_sum >= 22:
        t_min, t_max = 10, 16 
    elif last_sum <= 14:
        t_min, t_max = 20, 26 
    else:
        t_min, t_max = 13, 22

    # [B] ベクトル干渉 (距離3の禁止)
    forbidden = set()
    for n in last_nums:
        forbidden.add((n + 3) % 10)
        forbidden.add((n - 3) % 10)
    
    # [C] 構造チェック (ダブルの反動)
    force_single = len(set(last_nums)) < 4

    # [D] 10万回シミュレーション
    candidates = []
    attempts = 0
    
    while len(candidates) < 10 and attempts < 100000:
        attempts += 1
        nums = [random.randint(0, 9) for _ in range(4)]
        
        # Filters
        if not (t_min <= sum(nums) <= t_max): continue
        if 7 in nums: continue 
        if any(n in forbidden for n in nums): continue
        if force_single and len(set(nums)) < 4: continue
        if (0 not in nums) and (3 not in nums) and (random.random() > 0.2): continue 

        candidates.append("".join(map(str, nums)))
    
    # 補充
    while len(candidates) < 10:
        candidates.append(f"{random.randint(0,9)}{random.randint(0,9)}{random.randint(0,9)}{random.randint(0,9)}")
    
    return candidates

# --- 4. TIME & STATE CONTROL ---
now = datetime.now(JST)
current_hour = now.hour
current_date_str = now.strftime('%Y-%m-%d')

is_result_time = 20 <= current_hour < 22
is_calc_time = current_hour >= 22 or current_hour < 20

state = load_state()

# 【重要】データ未取得(0000)なら、時間に関係なく強制取得を試みる
if state["last_draw"] == "----" or state["last_draw"] == "0000":
    fetched = fetch_latest_result()
    if fetched:
        state["last_draw"] = fetched
        state["date"] = current_date_str # 取得日更新
        save_state(state)
        st.rerun()

# 20時以降の自動更新チェック
if is_result_time:
    if state["date"] != current_date_str:
        new_res = fetch_latest_result()
        if new_res and new_res != state["last_draw"]:
            state["last_draw"] = new_res
            state["date"] = current_date_str
            state["is_calculated"] = False 
            save_state(state)
            st.rerun()

# --- 5. UI CONSTRUCTION ---
st.markdown("""
<style>
    body { background-color: #000; color: #fff; margin: 0; padding: 0; }
    
    /* コンテナの調整 */
    .block-container { padding-top: 1rem; padding-bottom: 0rem; max-width: 100%; }

    /* Count Label */
    .count-label {
        text-align: center; 
        font-weight: bold; 
        font-size: 18px; 
        line-height: 40px; 
        color: #fff;
    }

    /* === CSS修正: カラムごとにスタイルを分ける === */
    
    /* 1列目(-) と 3列目(+) のボタン: 丸くする */
    div[data-testid="column"]:nth-of-type(1) button,
    div[data-testid="column"]:nth-of-type(3) button {
        border-radius: 50% !important;
        width: 40px !important;
        height: 40px !important;
        padding: 0 !important;
        font-size: 20px !important;
        font-weight: bold !important;
        background-color: #444 !important;
        color: white !important;
        border: 2px solid #666 !important;
        margin: 0 auto !important;
        display: block !important;
    }
    div[data-testid="column"]:nth-of-type(1) button:hover,
    div[data-testid="column"]:nth-of-type(3) button:hover {
        border-color: #fff !important;
    }

    /* 4列目(CALC) のボタン: 四角く(Pill型)にする */
    div[data-testid="column"]:nth-of-type(4) button {
        border-radius: 12px !important;
        width: 100% !important;
        height: 42px !important;
        background-color: #009688 !important; /* Green */
        color: #fff !important;
        border: none !important;
        font-size: 14px !important;
        letter-spacing: 1px !important;
        font-weight: bold !important;
        margin-top: 0px !important;
    }
    div[data-testid="column"]:nth-of-type(4) button:hover {
        background-color: #00bfa5 !important;
        box-shadow: 0 0 10px #009688;
    }
    div[data-testid="column"]:nth-of-type(4) button:disabled {
        background-color: #333 !important;
        color: #777 !important;
        cursor: not-allowed;
    }

</style>
""", unsafe_allow_html=True)

# --- PART A: LCD SCREEN ---
preds_list = state["predictions_n4"]
last_draw_val = state["last_draw"]

# もし計算結果がまだ「----」なら、LAST RESULT取得待ち等の表示にするかそのまま
if last_draw_val == "----" or last_draw_val == "0000":
    display_msg = "FETCHING..."
else:
    display_msg = last_draw_val

lcd_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ background-color: #000; margin: 0; font-family: sans-serif; overflow: hidden; }}
        .lcd {{ 
            background-color: #9ea7a6; 
            color: #000; 
            border: 4px solid #555; 
            border-radius: 12px; 
            height: 170px; 
            display: flex; 
            flex-direction: column; 
            align-items: center; 
            box-shadow: inset 0 0 10px rgba(0,0,0,0.5); 
            position: relative; 
            padding-top: 20px;
        }}
        .lcd-label {{ 
            font-size: 12px; 
            color: #444; 
            font-weight: bold; 
            position: absolute; 
            top: 8px; 
            width:100%; 
            text-align:center; 
        }}
        .preds-container {{ 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 2px 20px; 
            width: 90%; 
            margin-top: 5px; 
        }}
        .num-text {{ 
            font-family: 'Courier New', monospace; 
            font-weight: bold; 
            letter-spacing: 3px; 
            line-height: 1.1; 
            font-size: 26px; 
            text-align: center; 
        }}
    </style>
</head>
<body>
    <div class="lcd">
        <div class="lcd-label">LAST RESULT (N4): {display_msg}</div>
        <div class="preds-container">
            {''.join([f'<div class="num-text">{p}</div>' for p in preds_list])}
        </div>
    </div>
</body>
</html>
"""
components.html(lcd_html, height=200, scrolling=False)

# --- PART B: CONTROL BAR ---
# 背景バー作成
st.markdown('<div style="background: #222; border-radius: 30px; padding: 4px 15px; margin-bottom: 10px;">', unsafe_allow_html=True)

# カラム比率調整: CALCボタンが入る隙間を作る
col1, col2, col3, col4 = st.columns([1, 2, 1, 2.5])

if 'count' not in st.session_state: st.session_state.count = 10

with col1:
    if st.button("－"):
        if st.session_state.count > 1:
            st.session_state.count -= 1
            st.rerun()

with col2:
    st.markdown(f'<div class="count-label">{st.session_state.count} 口</div>', unsafe_allow_html=True)

with col3:
    if st.button("＋"):
        if st.session_state.count < 10:
            st.session_state.count += 1
            st.rerun()

with col4:
    # 状態判定
    if state["last_draw"] == "----" or state["last_draw"] == "0000":
        # データがない場合、CALCは押せない、代わりに再取得ボタン的挙動
        if st.button("RETRY"):
            st.rerun()
    else:
        # データがある場合、時間制御に従う
        calc_label = "CALC" if is_calc_time else "WAIT"
        disabled_status = not is_calc_time
        
        if st.button(calc_label, disabled=disabled_status, key="calc_btn"):
            with st.spinner(".."):
                new_preds = run_simulation(state["last_draw"])
                state["predictions_n4"] = new_preds
                save_state(state)
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# --- PART C: GAME BUTTONS ---
buttons_html = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { margin: 0; padding: 4px; overflow: hidden; user-select: none; }
        .pad-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
        .btn { 
            height: 45px; 
            border-radius: 12px; 
            color: white; 
            font-weight: bold; 
            font-size: 14px; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            border: 2px solid rgba(0,0,0,0.3); 
            box-shadow: 0 3px #000; 
            cursor: pointer; 
            font-family: sans-serif;
        }
        .btn:active { transform: translateY(2px); box-shadow: 0 1px #000; }
        
        .btn-loto { background: #E91E63; } 
        .btn-num { background: #009688; } 
        .btn-mini { background: #FF9800; }
        .btn-bingo { background: #2196F3; } 
        .btn-yellow { background: #FFEB3B; color: #333; }
        
        .active { border: 2px solid #fff !important; box-shadow: 0 0 10px rgba(255,255,255,0.5); }
    </style>
</head>
<body>
    <div class="pad-grid">
        <div class="btn btn-loto">LOTO 7</div>
        <div class="btn btn-num active">Numbers 4</div>
        <div class="btn btn-loto">LOTO 6</div>
        <div class="btn btn-num">Numbers 3</div>
        <div class="btn btn-loto">MINI LOTO</div>
        <div class="btn btn-mini">Numbers mini</div>
        <div class="btn btn-bingo">BINGO 5</div>
        <div class="btn btn-yellow">Manage app</div>
    </div>
</body>
</html>
"""
components.html(buttons_html, height=300, scrolling=False)
