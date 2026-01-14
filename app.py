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
# MIRU-PAD: THE ORIGINAL DESIGN RESTORED
# Logic: Python Backend
# UI: Pure HTML (iframe) with Reload Trigger
# ==========================================

# --- 1. CONFIG & CONSTANTS ---
DATA_FILE = "miru_status.json"
JST = timezone(timedelta(hours=9), 'JST')
st.set_page_config(page_title="MIRU-PAD", layout="centered", initial_sidebar_state="collapsed")

# 風車盤ロジック
WINDMILL_MAP = {
    'n1': [0, 7, 4, 1, 8, 5, 2, 9, 6, 3],
    'n2': [0, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    'n3': [0, 3, 6, 9, 2, 5, 8, 1, 4, 7],
    'n4': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
}
INDEX_MAP = {k: {num: i for i, num in enumerate(arr)} for k, arr in WINDMILL_MAP.items()}
GRAVITY_SECTORS = [4, 5, 6]
ANTI_GRAVITY_SECTORS = [9, 0, 1]

# --- 2. STATE & DATA ---
def load_state():
    default = {
        "N4": {"last": "----", "preds": ["----"]*10},
        "N3": {"last": "----", "preds": ["---"]*10},
        "NM": {"last": "----", "preds": ["--"]*10},
        "current_game": "N4",
        "count": 10
    }
    if not os.path.exists(DATA_FILE): return default
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except: return default

def save_state(data):
    try:
        with open(DATA_FILE, "w") as f: json.dump(data, f)
    except: pass

# --- 3. LOGIC ENGINES ---
def fetch_history_logic(game_type):
    # N3/NM共用
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
            final_idx = (curr + spin) % 10 # Simple Gravity
            row += str(WINDMILL_MAP[col][final_idx])
        
        val = row[-2:] if game_type == 'NM' else row
        if val not in seen:
            seen.add(val)
            preds.append(val)
            if len(preds) >= 10: break
    
    while len(preds) < 10: preds.append("----")
    return preds

# --- 4. MAIN PROCESS ---
state = load_state()

# URLクエリパラメータの処理 (HTMLボタンからの指令を受け取る)
query_params = st.query_params
action = query_params.get("action", None)
target_game = query_params.get("game", state["current_game"])

# モード切替
if target_game != state["current_game"]:
    state["current_game"] = target_game
    save_state(state)

# アクション実行
gm = state["current_game"]
if action == "calc":
    # 計算実行
    l, t = fetch_history_logic(gm)
    if l:
        state[gm]["last"] = l
        state[gm]["preds"] = run_prediction(gm, l, t)
        save_state(state)
elif action == "update":
    # 強制更新
    state[gm]["last"] = "----"
    l, t = fetch_history_logic(gm)
    if l:
        state[gm]["last"] = l
        save_state(state)

# 起動時自動取得
if state[gm]["last"] == "----":
    l, t = fetch_history_logic(gm)
    if l:
        state[gm]["last"] = l
        save_state(state)

# クエリパラメータを掃除 (リロードループ防止)
if action:
    st.query_params.clear()

# --- 5. HTML GENERATION (THE ORIGINAL DESIGN) ---
# データ準備
d_map = {
    'N4': state["N4"]["preds"],
    'N3': state["N3"]["preds"],
    'NM': state["NM"]["preds"],
    'L7': ["COMING"]*10, 'L6': ["COMING"]*10, 'ML': ["COMING"]*10, 'B5': ["COMING"]*10, 'KC': ["COMING"]*10
}
l_map = {
    'N4': state["N4"]["last"],
    'N3': state["N3"]["last"],
    'NM': state["NM"]["last"]
}

# Python変数をJSに埋め込む
js_d_map = json.dumps(d_map)
js_l_map = json.dumps(l_map)
current_g = state["current_game"]

# HTMLコード (あんたのくれたコードをベースに、クリック時にPythonを叩くリンクを追加)
html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <style>
        body {{ background-color: #000; color: #fff; font-family: sans-serif; margin: 0; padding: 4px; overflow: hidden; user-select: none; touch-action: manipulation; }}
        
        .lcd {{ background-color: #9ea7a6; color: #000; border: 4px solid #555; border-radius: 12px; height: 170px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: inset 0 0 10px rgba(0,0,0,0.5); position: relative; margin-bottom: 10px; }}
        .lcd-label {{ font-size: 10px; color: #444; font-weight: bold; position: absolute; top: 8px; width:100%; text-align:center; }}
        .preds-container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 2px 20px; width: 90%; margin-top: 15px; }}
        .num-text {{ font-family: 'Courier New', monospace; font-weight: bold; letter-spacing: 2px; line-height: 1.1; font-size: 24px; text-align: center; width:100%; }}
        .locked {{ font-size: 14px; color: #555; letter-spacing: 1px; text-align: center; width:100%; }}
        
        .count-bar {{ display: flex; justify-content: space-between; align-items: center; background: #222; padding: 5px 10px; border-radius: 30px; margin-bottom: 8px; height: 50px; }}
        .btn-round {{ width: 40px; height: 40px; border-radius: 50%; background: #444; color: white; display: flex; justify-content: center; align-items: center; font-size: 24px; font-weight: bold; border: 2px solid #666; cursor: pointer; }}
        
        .btn-calc {{ width: 100px; height: 40px; border-radius: 20px; background: #fff; color: #000; display: flex; justify-content: center; align-items: center; font-size: 16px; font-weight: bold; cursor: pointer; margin-left: 10px; }}
        .btn-calc:active {{ background: #ccc; }}

        .pad-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
        .btn {{ height: 48px; border-radius: 12px; color: white; font-weight: bold; font-size: 13px; display: flex; justify-content: center; align-items: center; border: 2px solid rgba(0,0,0,0.3); box-shadow: 0 3px #000; cursor: pointer; text-decoration: none; }}
        .btn:active {{ transform: translateY(2px); box-shadow: 0 1px #000; }}
        
        .btn-pink {{ background: #E91E63; }}
        .btn-green {{ background: #009688; }}
        .btn-orange {{ background: #FF9800; }}
        .btn-blue {{ background: #2196F3; }}
        .btn-yellow {{ background: #FFEB3B; color: #333; }}
        
        .active {{ border: 2px solid #fff !important; box-shadow: 0 0 15px rgba(255,255,255,0.6); }}
        .disabled {{ opacity: 0.5; pointer-events: none; }}
    </style>
</head>
<body>
    <div class="lcd">
        <div id="game-label" class="lcd-label">LAST RESULT</div>
        <div id="preds-box" class="preds-container"></div>
    </div>
    
    <div class="count-bar">
        <div class="btn-round" onclick="changeCount(-1)">－</div>
        <div id="count-label" style="font-size:18px; font-weight:bold;">10 口</div>
        <div class="btn-round" onclick="changeCount(1)">＋</div>
        <a id="link-calc" href="?action=calc&game={current_g}" target="_parent" class="btn-calc">CALC</a>
    </div>
    
    <div class="pad-grid">
        <div class="btn btn-pink disabled">LOTO 7</div>
        <a href="?game=N4" target="_parent" id="btn-N4" class="btn btn-green">Numbers 4</a>
        
        <div class="btn btn-pink disabled">LOTO 6</div>
        <a href="?game=N3" target="_parent" id="btn-N3" class="btn btn-green">Numbers 3</a>
        
        <div class="btn btn-pink disabled">MINI LOTO</div>
        <a href="?game=NM" target="_parent" id="btn-NM" class="btn btn-orange">Numbers mini</a>
        
        <div class="btn btn-blue disabled">BINGO 5</div>
        <a href="?action=update&game={current_g}" target="_parent" class="btn btn-yellow">UPDATE DATA</a>
    </div>

    <script>
        const d = {js_d_map};
        const l = {js_l_map};
        let curG = '{current_g}';
        let curC = 10; // デフォルト10口

        function update() {{
            document.getElementById('count-label').innerText = curC + ' 口';
            document.getElementById('game-label').innerText = 'LAST RESULT ('+curG+'): ' + (l[curG]||'----');
            
            // 予想数字描画
            let h = '';
            let data = d[curG] || [];
            for(let i=0; i<curC; i++) {{
                let v = data[i] || '----';
                let c = v === 'COMING' ? 'locked' : 'num-text';
                h += `<div class="${{c}}">${{v}}</div>`;
            }}
            document.getElementById('preds-box').innerHTML = h;

            // ボタンのアクティブ化
            document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
            const activeBtn = document.getElementById('btn-'+curG);
            if(activeBtn) activeBtn.classList.add('active');
            
            // リンクの更新 (今のゲームモードを維持)
            document.getElementById('link-calc').href = "?action=calc&game=" + curG;
        }}

        function changeCount(v) {{
            curC = Math.max(1, Math.min(10, curC+v));
            update();
        }}

        // 初期実行
        update();
    </script>
</body>
</html>
"""

# HTMLを埋め込む (高さを調整してスクロールバーを消す)
components.html(html_code, height=600, scrolling=False)

