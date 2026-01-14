import streamlit as st
import random
import requests
import json
import os
import time
from datetime import datetime, timedelta, timezone
import streamlit.components.v1 as components

# ==========================================
# MIRU-PAD: AUTONOMOUS (DESIGN FIXED)
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
            # 自動修復：古いデータ形式ならデフォルト値で埋める
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
    # 20時以降に自動で見に行く最新結果
    try:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        res = requests.get(url, timeout=3)
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
    # 物理シミュレーション実行
    try:
        last_nums = [int(c) for c in last_draw_str]
        last_sum = sum(last_nums)
    except:
        last_nums = [0,0,0,0]
        last_sum = 18 # Default

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

# --- 4. TIME CONTROL ---
now = datetime.now(JST)
current_hour = now.hour
current_date_str = now.strftime('%Y-%m-%d')

# 20:00-21:59: 結果確認タイム / 22:00-19:59: 計算タイム
is_result_time = 20 <= current_hour < 22
is_calc_time = current_hour >= 22 or current_hour < 20

state = load_state()

# 20時になったら自動で結果更新（予想は変えない）
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
# CSSでデザインをユーザーの元画像に極限まで近づける
st.markdown("""
<style>
    body { background-color: #000; color: #fff; margin: 0; padding: 0; }
    
    /* Control Bar Styling (Replicating user's HTML) */
    div.stButton > button {
        border-radius: 50%;
        width: 38px;
        height: 38px;
        padding: 0;
        font-size: 20px;
        font-weight: bold;
        background-color: #444;
        color: white;
        border: 2px solid #666;
        line-height: 1;
        margin: 0 auto;
        display: block;
    }
    div.stButton > button:hover {
        border-color: #fff;
        color: #fff;
    }
    
    /* Count Label */
    .count-label {
        text-align: center; 
        font-weight: bold; 
        font-size: 18px; 
        line-height: 45px; 
        color: #fff;
    }

    /* CALC Button Special Styling */
    div[data-testid="column"]:nth-of-type(4) div.stButton > button {
        border-radius: 12px; /* Pill shape */
        width: 100%;
        height: 42px;
        background-color: #009688; /* Match Green Theme */
        border-color: rgba(0,0,0,0.3);
        font-size: 14px;
        letter-spacing: 1px;
    }
    div[data-testid="column"]:nth-of-type(4) div.stButton > button:disabled {
        background-color: #333;
        border-color: #444;
        color: #777;
    }

    /* Container for the bar */
    .css-1r6slb0 {
        background: #222;
        border-radius: 30px;
        padding: 5px;
    }
    
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
</style>
""", unsafe_allow_html=True)

# --- PART A: LCD SCREEN ---
preds_list = state["predictions_n4"]
last_draw_val = state["last_draw"]

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
        <div class="lcd-label">LAST RESULT (N4): {last_draw_val}</div>
        <div class="preds-container">
            {''.join([f'<div class="num-text">{p}</div>' for p in preds_list])}
        </div>
    </div>
</body>
</html>
"""
components.html(lcd_html, height=200, scrolling=False)

# --- PART B: CONTROL BAR (Python Buttons for Logic) ---
# 背景の黒いバーをCSSで作るためのコンテナ
st.markdown('<div style="background: #222; border-radius: 30px; padding: 4px 15px; margin-bottom: 10px;">', unsafe_allow_html=True)
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
    calc_label = "CALC" if is_calc_time else "WAIT"
    if st.button(calc_label, disabled=not is_calc_time, key="calc_btn"):
        with st.spinner(".."):
            new_preds = run_simulation(state["last_draw"])
            state["predictions_n4"] = new_preds
            save_state(state)
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# --- PART C: GAME BUTTONS (HTML for Design) ---
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
