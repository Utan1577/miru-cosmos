import streamlit as st
import random
import requests
import json
import os
import streamlit.components.v1 as components
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from collections import Counter

# ==========================================
# MIRU-PAD: GENESIS RESTORED (IFRAME VER)
# Design: User's Original HTML + CSS
# Logic: Query Params -> Python Backend
# ==========================================

# --- 1. CONFIG ---
DATA_FILE = "miru_status.json"
JST = timezone(timedelta(hours=9), 'JST')
st.set_page_config(page_title="MIRU-PAD", layout="centered", initial_sidebar_state="collapsed")

# --- 2. WINDMILL LOGIC ---
WINDMILL_MAP = {
    'n1': [0, 7, 4, 1, 8, 5, 2, 9, 6, 3],
    'n2': [0, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    'n3': [0, 3, 6, 9, 2, 5, 8, 1, 4, 7],
    'n4': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
}
INDEX_MAP = {k: {num: i for i, num in enumerate(arr)} for k, arr in WINDMILL_MAP.items()}
GRAVITY_SECTORS = [4, 5, 6]
ANTI_GRAVITY_SECTORS = [9, 0, 1]

# --- 3. ROBUST STATE MANAGEMENT (KeyError Fix) ---
def load_state():
    # 必須キーを網羅したデフォルト値
    default = {
        "current_game": "N4",  # これがないと死ぬ
        "count": 10,
        "N4": {"last": "----", "preds": ["----"]*10},
        "N3": {"last": "----", "preds": ["---"]*10},
        "NM": {"last": "----", "preds": ["--"]*10}
    }
    
    if not os.path.exists(DATA_FILE):
        return default

    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # データの自動修復（足りないキーがあればデフォルト値で埋める）
            for k, v in default.items():
                if k not in data:
                    data[k] = v
            # ゲームごとのデータもチェック
            for g in ['N4', 'N3', 'NM']:
                if g not in data: data[g] = default[g]
            
            return data
    except:
        return default

def save_state(data):
    try:
        with open(DATA_FILE, "w") as f: json.dump(data, f)
    except: pass

# --- 4. LOGIC FUNCTIONS ---
def fetch_history_logic(game_type):
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
    if not last_val or last_val == "----": return ["----"] * 10
    calc_g = 'N3' if game_type == 'NM' else game_type
    cols = ['n1', 'n2', 'n3', 'n4'] if calc_g == 'N4' else ['n1', 'n2', 'n3']
    last_nums = [int(d) for d in last_val]
    
    preds = []
    seen = set()
    for _ in range(50):
        row = ""
        for i, col in enumerate(cols):
            curr = INDEX_MAP[col][last_nums[i]]
            spin = trends[col]
            spin = (spin + random.choice([0, 1, -1, 5])) % 10
            final_idx = (curr + spin) % 10
            row += str(WINDMILL_MAP[col][final_idx])
        
        val = row[-2:] if game_type == 'NM' else row
        if val not in seen:
            seen.add(val)
            preds.append(val)
            if len(preds) >= 10: break
    
    while len(preds) < 10: preds.append("----")
    return preds

# --- 5. MAIN PROCESS ---
state = load_state()

# URLパラメータ取得 (ユーザー操作の受け取り)
query = st.query_params
action = query.get("action", None)
req_game = query.get("game", None)
req_count = query.get("count", None)

# --- ACTION HANDLING ---
needs_save = False

# 1. ゲーム切り替え
if req_game and req_game != state["current_game"]:
    state["current_game"] = req_game
    needs_save = True

# 2. 口数変更
if req_count:
    try:
        new_c = int(req_count)
        if 1 <= new_c <= 10:
            state["count"] = new_c
            needs_save = True
    except: pass

# 3. 計算 / 更新
gm = state["current_game"]
if action == "calc":
    l, t = fetch_history_logic(gm)
    if l:
        state[gm]["last"] = l
        state[gm]["preds"] = run_prediction(gm, l, t)
        needs_save = True
elif action == "update":
    state[gm]["last"] = "----"
    l, t = fetch_history_logic(gm)
    if l:
        state[gm]["last"] = l
        needs_save = True

# 起動時の自動取得
if state[gm]["last"] == "----":
    l, t = fetch_history_logic(gm)
    if l:
        state[gm]["last"] = l
        needs_save = True

# 保存とリダイレクト (URLを綺麗にするため)
if needs_save:
    save_state(state)
    # パラメータをクリアして再読み込み (無限ループ防止)
    st.query_params.clear()
    st.rerun()

# --- 6. HTML GENERATION (EXACT DESIGN) ---
# JSONデータをHTMLに埋め込む準備
preds_data = state[gm]["preds"]
last_data = state[gm]["last"]
count_val = state["count"]
cg = state["current_game"]

# HTML本体
# target="_top" を使うことで、リンククリック時にStreamlitアプリ全体をリロードし、Pythonロジックを走らせる
html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        body {{ background-color: #000; color: #fff; font-family: sans-serif; margin: 0; padding: 4px; overflow: hidden; user-select: none; -webkit-tap-highlight-color: transparent; }}
        
        /* LCD Screen */
        .lcd {{ 
            background-color: #9ea7a6; color: #000; 
            border: 4px solid #555; border-radius: 12px; 
            height: 170px; 
            display: flex; flex-direction: column; justify-content: center; align-items: center; 
            box-shadow: inset 0 0 10px rgba(0,0,0,0.5); position: relative; margin-bottom: 10px; 
        }}
        .lcd-label {{ font-size: 10px; color: #444; font-weight: bold; position: absolute; top: 8px; width:100%; text-align:center; }}
        .preds-container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 2px 20px; width: 90%; margin-top: 15px; }}
        .num-text {{ font-family: 'Courier New', monospace; font-weight: bold; letter-spacing: 2px; line-height: 1.1; font-size: 24px; text-align: center; width:100%; }}
        
        /* Control Bar */
        .count-bar {{ display: flex; justify-content: space-between; align-items: center; background: #222; padding: 5px 10px; border-radius: 30px; margin-bottom: 8px; height: 50px; }}
        
        /* Round Buttons (Links) */
        .btn-round {{ 
            width: 40px; height: 40px; border-radius: 50%; 
            background: #444; color: white; border: 2px solid #666; 
            display: flex; justify-content: center; align-items: center; 
            font-size: 24px; font-weight: bold; text-decoration: none; 
        }}
        .btn-round:active {{ background: #666; }}
        
        /* CALC Button (Link) */
        .btn-calc {{ 
            background: #fff; color: #000; 
            border-radius: 20px; height: 40px; padding: 0 20px; 
            display: flex; justify-content: center; align-items: center; 
            font-weight: bold; font-size: 16px; text-decoration: none; margin-left: 10px;
        }}
        .btn-calc:active {{ opacity: 0.8; }}

        /* Game Grid */
        .pad-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
        .btn {{ 
            height: 48px; border-radius: 12px; color: white; font-weight: bold; font-size: 13px; 
            display: flex; justify-content: center; align-items: center; 
            border: 2px solid rgba(0,0,0,0.3); box-shadow: 0 3px #000; 
            text-decoration: none; 
        }}
        .btn:active {{ transform: translateY(2px); box-shadow: 0 1px #000; }}
        
        /* Colors */
        .btn-pink {{ background: #E91E63; }}
        .btn-green {{ background: #009688; }}
        .btn-orange {{ background: #FF9800; }}
        .btn-blue {{ background: #2196F3; }}
        .btn-yellow {{ background: #FFEB3B; color: #333; }}
        
        .active {{ border: 2px solid #fff !important; box-shadow: 0 0 15px rgba(255,255,255,0.6); }}
        .disabled {{ opacity: 0.4; pointer-events: none; }}
        
        /* Layout Fixes */
        .count-text {{ font-size: 18px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="lcd">
        <div class="lcd-label">LAST RESULT ({cg}) : {last_data}</div>
        <div class="preds-container">
            {''.join([f'<div class="num-text">{p}</div>' for p in preds_data[:count_val]])}
        </div>
    </div>
    
    <div class="count-bar">
        <a href="?count={max(1, count_val-1)}" target="_top" class="btn-round">－</a>
        <div class="count-text">{count_val} 口</div>
        <a href="?count={min(10, count_val+1)}" target="_top" class="btn-round">＋</a>
        <a href="?action=calc" target="_top" class="btn-calc">CALC</a>
    </div>
    
    <div class="pad-grid">
        <div class="btn btn-pink disabled">LOTO 7</div>
        <a href="?game=N4" target="_top" class="btn btn-green {'active' if cg=='N4' else ''}">Numbers 4</a>
        
        <div class="btn btn-pink disabled">LOTO 6</div>
        <a href="?game=N3" target="_top" class="btn btn-green {'active' if cg=='N3' else ''}">Numbers 3</a>
        
        <div class="btn btn-pink disabled">MINI LOTO</div>
        <a href="?game=NM" target="_top" class="btn btn-orange {'active' if cg=='NM' else ''}">Numbers mini</a>
        
        <div class="btn btn-blue disabled">BINGO 5</div>
        <a href="?action=update" target="_top" class="btn btn-yellow">UPDATE DATA</a>
    </div>
</body>
</html>
"""

# 余白を消して全画面表示
st.markdown("""<style>.block-container {padding: 0 !important;}</style>""", unsafe_allow_html=True)
components.html(html_code, height=600, scrolling=False)
