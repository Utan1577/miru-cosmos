import streamlit as st
import random
import requests
import json
import os
import time
from datetime import datetime, timedelta, timezone
import streamlit.components.v1 as components
from collections import Counter

# ==========================================
# MIRU-PAD: COLD MACHINE (DESIGN LOCKED)
# ==========================================

# --- CONFIG & DATA ---
DATA_FILE = "miru_status.json"
JST = timezone(timedelta(hours=9), 'JST')
st.set_page_config(page_title="MIRU-PAD", layout="centered", initial_sidebar_state="collapsed")

# --- 1. GLOBAL SYNC ENGINE (JSON) ---
def load_state():
    if not os.path.exists(DATA_FILE):
        return {
            "date": "2000-01-01",
            "last_draw": "0000",
            # デフォルトは未計算状態
            "predictions_n4": ["----"] * 10,
            "is_calculated": False
        }
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_state(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# --- 2. DATA FETCHING (AUTO UPDATE) ---
def fetch_latest_result(game_type='N4'):
    try:
        if game_type == 'N4':
            url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
            expected_len = 4
        else:
            return "----"
            
        res = requests.get(url, timeout=3)
        res.encoding = 'Shift_JIS'
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.find_all('tr')
        # 最新の結果を取得（ヘッダーの次）
        for row in rows:
            data = row.find('td', class_='alnCenter')
            if data:
                val = data.text.strip().replace(' ', '')
                if val.isdigit() and len(val) == expected_len:
                    return val
        return None
    except:
        return None

# --- 3. COLD MACHINE LOGIC (PRO MODE) ---
def run_simulation(last_draw_str):
    # 前回の結果から物理的な拘束条件を自動生成
    try:
        last_nums = [int(c) for c in last_draw_str]
        last_sum = sum(last_nums)
    except:
        last_nums = [0,0,0,0]
        last_sum = 0
    
    # [A] 合計値の平均回帰
    # 昨日のエネルギーが高すぎたら低く、低すぎたら高く
    if last_sum >= 22:
        target_min, target_max = 10, 16 # Low Target
    elif last_sum <= 14:
        target_min, target_max = 20, 26 # High Target
    else:
        target_min, target_max = 13, 22 # Mid Range

    # [B] ベクトル干渉 (距離3の禁止)
    forbidden_vectors = set()
    for n in last_nums:
        forbidden_vectors.add((n + 3) % 10)
        forbidden_vectors.add((n - 3) % 10)
    
    # [C] 構造チェック (ダブルの反動)
    # 昨日がダブルなら、今日はシングル(バラバラ)を強制
    force_single = len(set(last_nums)) < 4

    # [D] 10万回シミュレーション (高速フィルタリング)
    candidates = []
    attempts = 0
    
    while len(candidates) < 10 and attempts < 100000:
        attempts += 1
        nums = [random.randint(0, 9) for _ in range(4)]
        
        # Filter 1: Sum
        if not (target_min <= sum(nums) <= target_max): continue
        
        # Filter 2: Forbidden 7 (Death Number)
        if 7 in nums: continue # 今日の死に数字
        
        # Filter 3: Forbidden Vectors
        if any(n in forbidden_vectors for n in nums): continue
        
        # Filter 4: Structure
        if force_single and len(set(nums)) < 4: continue

        # Filter 5: Attractor (0 or 3 preference)
        if (0 not in nums) and (3 not in nums):
            if random.random() > 0.2: continue # 80% reject

        candidates.append("".join(map(str, nums)))
    
    # 補充
    while len(candidates) < 10:
        candidates.append(f"{random.randint(0,9)}{random.randint(0,9)}{random.randint(0,9)}{random.randint(0,9)}")
    
    return candidates

# --- 4. TIME CONTROL ---
now = datetime.now(JST)
current_hour = now.hour
current_date_str = now.strftime('%Y-%m-%d')

# 20:00 - 21:59 : RESULT CHECK TIME (Last Result Updates, Prediction Locked)
# 22:00 - 19:59 : CALC TIME (Prediction Unlocked)
is_result_time = 20 <= current_hour < 22
is_calc_time = current_hour >= 22 or current_hour < 20

# Load State
state = load_state()

# Auto Update Last Result (Only during Result Time)
if is_result_time:
    # まだ今日の日付で更新していない場合
    if state["date"] != current_date_str:
        new_res = fetch_latest_result('N4')
        if new_res and new_res != state["last_draw"]:
            state["last_draw"] = new_res
            state["date"] = current_date_str
            state["is_calculated"] = False # 明日の分は未計算
            save_state(state)
            st.rerun()

# --- 5. UI CONSTRUCTION (EXACT LAYOUT) ---

# Custom CSS to match the user's design EXACTLY + Add CALC button style
st.markdown("""
<style>
    body { background-color: #000; color: #fff; margin: 0; padding: 0; }
    
    /* Control Bar Container */
    .control-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #222;
        padding: 5px 15px;
        border-radius: 30px;
        margin: 10px auto;
        width: 90%;
        max-width: 400px;
    }
    
    /* Round Buttons (- / +) */
    .stButton button {
        border-radius: 50%;
        width: 40px;
        height: 40px;
        padding: 0;
        font-size: 20px;
        font-weight: bold;
        background-color: #444;
        color: white;
        border: 2px solid #666;
        line-height: 1;
    }
    .stButton button:hover {
        border-color: #fff;
        color: #fff;
    }
    
    /* CALC Button Style (Special) */
    div[data-testid="column"] .calc-btn button {
        border-radius: 20px; /* Pill shape */
        width: 100%;
        background-color: #009688; /* Match Green Theme */
        border-color: #009688;
        font-size: 14px;
        letter-spacing: 1px;
    }
    div[data-testid="column"] .calc-btn button:disabled {
        background-color: #333;
        border-color: #444;
        color: #777;
    }

    /* Hide Streamlit default margins */
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    
</style>
""", unsafe_allow_html=True)

# --- PART A: LCD SCREEN (HTML Component) ---
# JSONデータを渡して表示
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

# --- PART B: CONTROL BAR (Streamlit Native with Custom CSS) ---
# ここをネイティブにすることで、CALCボタンがPythonロジックを叩けるようにする
# レイアウト: [ - ] [ COUNT ] [ + ] [ CALC ]

# Session State for Count
if 'count' not in st.session_state: st.session_state.count = 10

col1, col2, col3, col4 = st.columns([1, 2, 1, 2.5])

with col1:
    if st.button("－"):
        if st.session_state.count > 1:
            st.session_state.count -= 1
            st.rerun()

with col2:
    # テキスト表示 (HTML)
    st.markdown(f"""
        <div style="text-align: center; font-weight: bold; font-size: 18px; line-height: 40px; color: #fff;">
            {st.session_state.count} 口
        </div>
    """, unsafe_allow_html=True)

with col3:
    if st.button("＋"):
        if st.session_state.count < 10:
            st.session_state.count += 1
            st.rerun()

with col4:
    st.markdown('<div class="calc-btn">', unsafe_allow_html=True)
    
    # CALCボタンのラベルと状態制御
    calc_label = "CALC" if is_calc_time else "WAIT"
    
    if st.button(calc_label, disabled=not is_calc_time, key="calc_main"):
        # === 激辛シミュレーション実行 ===
        with st.spinner("COMPUTING..."):
            new_preds = run_simulation(state["last_draw"])
            state["predictions_n4"] = new_preds
            state["is_calculated"] = True
            save_state(state)
        st.rerun()
        
    st.markdown('</div>', unsafe_allow_html=True)


# --- PART C: GAME BUTTONS (HTML/CSS EXACT COPY) ---
# ユーザーが愛するデザインをそのまま保持
# CALCボタンでのN4計算に特化しているため、ここのボタンは視覚的な切り替え（将来用）として残す

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
        
        /* EXACT COLORS FROM USER */
        .btn-loto { background: #E91E63; } 
        .btn-num { background: #009688; } 
        .btn-mini { background: #FF9800; }
        .btn-bingo { background: #2196F3; } /* Blue */
        .btn-yellow { background: #FFEB3B; color: #333; } /* Yellow */
        
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
