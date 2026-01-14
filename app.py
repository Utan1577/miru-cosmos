import streamlit as st
import random
import requests
import json
import os
import time
from datetime import datetime, timedelta, timezone
import streamlit.components.v1 as components

# ==========================================
# MIRU-PAD: AUTONOMOUS SYSTEM CORE
# "Cold Machine" Logic - No Intuition, Only Physics.
# ==========================================

# --- SYSTEM CONFIG ---
DATA_FILE = "miru_status.json"
JST = timezone(timedelta(hours=9), 'JST')

st.set_page_config(page_title="MIRU-PAD", layout="centered", initial_sidebar_state="collapsed")

# --- CUSTOM CSS (Dark Cyber Style) ---
st.markdown("""
<style>
    /* Global Reset */
    .stApp { background-color: #000000; color: #ffffff; }
    header, footer { visibility: hidden; }
    
    /* Control Bar Layout */
    .stButton button {
        background-color: #333333;
        color: #ffffff;
        border: 2px solid #555555;
        border-radius: 10px;
        font-weight: bold;
        font-family: 'Courier New', monospace;
        transition: all 0.2s;
        width: 100%;
        height: 50px;
    }
    .stButton button:hover {
        border-color: #00ff00;
        color: #00ff00;
        box-shadow: 0 0 10px rgba(0, 255, 0, 0.4);
    }
    .stButton button:active {
        background-color: #00ff00;
        color: #000000;
    }
    
    /* CALC Button Special Style */
    .calc-btn button {
        background-color: #004d40;
        border-color: #009688;
        color: #00ffcc;
    }
    .calc-btn button:hover {
        background-color: #009688;
        box-shadow: 0 0 15px #00ffcc;
    }
    
    /* Locked Button Style */
    .locked-btn button {
        background-color: #1a1a1a;
        color: #555555;
        border-color: #333333;
        cursor: not-allowed;
    }
    
    /* LCD Container Override */
    iframe { border: none; }
</style>
""", unsafe_allow_html=True)

# --- 1. PERSISTENCE ENGINE (Global Sync) ---
def load_state():
    if not os.path.exists(DATA_FILE):
        return {
            "date": "2000-01-01",
            "last_draw": "0000",
            "predictions": ["READY", "READY", "READY", "READY", "READY", "READY", "READY", "READY", "READY", "READY"],
            "is_calculated": False
        }
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_state(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# --- 2. DATA MINING ENGINE (Scraping) ---
def fetch_latest_draw():
    # 物理法則に従うため、最新の「事実」のみを取得する
    url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
    try:
        res = requests.get(url, timeout=3)
        res.encoding = 'Shift_JIS'
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.text, 'html.parser')
        # 最新の1行を取得
        row = soup.find_all('tr')[1] # ヘッダーの次
        val = row.find('td', class_='alnCenter').text.strip().replace(' ', '')
        return val
    except:
        return None # エラー時はNoneを返し、過去データ維持

# --- 3. PHYSICS SIMULATION ENGINE (The "Pro Mode" Logic) ---
def run_simulation(last_draw_str):
    # 【絶対ルール】入力された前回数値から、物理的な禁止領域と推奨領域を計算
    last_nums = [int(c) for c in last_draw_str]
    last_sum = sum(last_nums)
    
    # [A] 合計値の平均回帰ロジック
    # 昨日のエネルギーが高すぎたら(>22)、今日は低く落とす
    if last_sum >= 22:
        target_sum_min, target_sum_max = 10, 16
    elif last_sum <= 14:
        target_sum_min, target_sum_max = 20, 26
    else:
        target_sum_min, target_sum_max = 13, 22 # 通常時

    # [B] ベクトル干渉 (距離3の禁止)
    # 昨日の位置から物理的に移動しにくい距離(±3)を排除
    forbidden_vectors = []
    for n in last_nums:
        forbidden_vectors.append((n + 3) % 10)
        forbidden_vectors.append((n - 3) % 10)
    forbidden_vectors = set(forbidden_vectors)

    # [C] 構造チェック (ダブルの反動)
    is_double = len(set(last_nums)) < 4
    force_single = is_double # 昨日ダブルなら、今日はシングル強制

    # [D] 10万回シミュレーション (高速化のため論理フィルター形式で実装)
    candidates = []
    attempts = 0
    
    while len(candidates) < 10 and attempts < 100000:
        attempts += 1
        
        # 1. カオス生成
        nums = [random.randint(0, 9) for _ in range(4)]
        
        # 2. フィルター適用
        # Sum Check
        s = sum(nums)
        if not (target_sum_min <= s <= target_sum_max): continue
        
        # Structure Check
        if force_single and len(set(nums)) < 4: continue
        
        # Vector Check (どれか一つでも禁止数字が入っていたら廃棄)
        if any(n in forbidden_vectors for n in nums): continue
        
        # Attractor Check (0と3のペア誘引)
        # 10万回回した結果、0と3のペアは強いが、必須にすると候補が枯渇するため
        # 「0か3が含まれている」ことを推奨条件とする
        if 0 not in nums and 3 not in nums:
            if random.random() > 0.1: continue # 90%の確率で捨てる

        # 生き残ったエリート数字を採用
        candidates.append("".join(map(str, nums)))
        
    # もし厳しすぎて候補が足りない場合、補充
    while len(candidates) < 10:
        candidates.append(f"{random.randint(0,9)}{random.randint(0,9)}{random.randint(0,9)}{random.randint(0,9)}")
        
    return candidates

# --- 4. TIME CONTROL LOGIC ---
now = datetime.now(JST)
current_hour = now.hour
current_date_str = now.strftime('%Y-%m-%d')

# State Definitions
# 20:00 - 21:59 : RESULT_CHECK (答え合わせモード) -> CALC禁止
# 22:00 - 19:59 : PREDICTION (未来確定モード) -> CALC解禁
is_result_time = 20 <= current_hour < 22
is_calc_time = current_hour >= 22 or current_hour < 20

# Load Data
state_data = load_state()

# Auto Update Check (20時過ぎたら最新結果を取りに行く)
if is_result_time and state_data["date"] != current_date_str:
    new_draw = fetch_latest_draw()
    if new_draw and new_draw != state_data["last_draw"]:
        # 新しい結果を発見。しかし予想(predictions)は更新しない（答え合わせ用）
        state_data["last_draw"] = new_draw
        state_data["date"] = current_date_str
        state_data["is_calculated"] = False # 明日の分はまだ計算していない
        save_state(state_data)
        st.rerun()

# --- 5. UI CONSTRUCTION ---

# Session State for Local Display (Count)
if 'count' not in st.session_state: st.session_state.count = 5

# --- [A] LCD DISPLAY (HTML Component) ---
# JSONデータをHTMLに注入して表示
preds_js_array = str(state_data["predictions"])
last_draw_disp = state_data["last_draw"]

html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ background-color: #000; color: #fff; margin: 0; padding: 0; overflow: hidden; font-family: 'Courier New', monospace; }}
        .lcd-container {{
            background-color: #9ea7a6; /* LCD Grey */
            color: #000;
            border: 4px solid #555;
            border-radius: 10px;
            padding: 10px;
            height: 180px;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .header {{
            font-size: 12px;
            font-weight: bold;
            color: #333;
            letter-spacing: 1px;
            margin-bottom: 5px;
            width: 100%;
            text-align: center;
            border-bottom: 1px solid #777;
            padding-bottom: 2px;
        }}
        .last-draw {{
            font-size: 16px;
            font-weight: bold;
            color: #000;
            margin-bottom: 10px;
        }}
        .pred-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2px 20px;
            width: 90%;
        }}
        .pred-num {{
            font-size: 26px;
            font-weight: bold;
            letter-spacing: 4px;
            text-align: center;
            line-height: 1.0;
        }}
        .hidden {{ display: none; }}
    </style>
</head>
<body>
    <div class="lcd-container">
        <div class="header">MIRU-PAD AUTONOMOUS SYSTEM</div>
        <div class="last-draw">LAST RESULT: [ {last_draw_disp} ]</div>
        <div id="grid" class="pred-grid">
            </div>
    </div>
    <script>
        const preds = {preds_js_array};
        const count = {st.session_state.count};
        
        function render() {{
            const grid = document.getElementById('grid');
            grid.innerHTML = '';
            for(let i=0; i<10; i++) {{
                const el = document.createElement('div');
                el.className = 'pred-num';
                // countより多い分は隠す（または空文字にする）
                if(i < count) {{
                    el.innerText = preds[i];
                }} else {{
                    el.innerText = ''; 
                }}
                grid.appendChild(el);
            }}
        }}
        render();
    </script>
</body>
</html>
"""
components.html(html_code, height=210, scrolling=False)

# --- [B] CONTROL BAR (Streamlit Native with CSS) ---
# Layout: [ - ] [ COUNT ] [ + ] [ CALC ]
col1, col2, col3, col4 = st.columns([1.2, 2, 1.2, 2.5])

with col1:
    if st.button("－"):
        if st.session_state.count > 1:
            st.session_state.count -= 1
            st.rerun()

with col2:
    st.markdown(f"""
        <div style="
            height: 50px; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            font-weight: bold; 
            color: #fff; 
            background: #222; 
            border-radius: 10px; 
            font-size: 18px;">
            {st.session_state.count} 口
        </div>
    """, unsafe_allow_html=True)

with col3:
    if st.button("＋"):
        if st.session_state.count < 10:
            st.session_state.count += 1
            st.rerun()

with col4:
    # CALC Button Logic
    if is_calc_time:
        # 22時以降：計算解禁
        btn_label = "CALC"
        # カスタムCSS適用用のコンテナ
        st.markdown('<div class="calc-btn">', unsafe_allow_html=True)
        if st.button(btn_label, key="calc_btn"):
            # 【計算実行】
            # 1. 昨日の結果を取得（キャッシュされているもの）
            last = state_data["last_draw"]
            # 2. 激辛シミュレーション実行
            new_preds = run_simulation(last)
            # 3. データ保存（全ユーザー同期）
            state_data["predictions"] = new_preds
            state_data["is_calculated"] = True
            save_state(state_data)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        # 20時〜22時：ロック
        st.markdown('<div class="locked-btn">', unsafe_allow_html=True)
        st.button("WAIT 22:00", disabled=True)
        st.markdown('</div>', unsafe_allow_html=True)

# --- [C] GAME SELECTOR (Visual Only for now) ---
st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
g_col1, g_col2 = st.columns(2)
with g_col1:
    st.button("Numbers 4", key="n4", help="Active")
with g_col2:
    st.button("Numbers 3", key="n3", disabled=True)
    
# Debug Info (Bottom invisible basically)
# st.write(f"System Status: Online | Phase: {'CALC' if is_calc_time else 'CHECK'}")
