import streamlit as st
import random
import requests
import json
import os
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import streamlit.components.v1 as components
from collections import Counter

# --- ページ設定 ---
st.set_page_config(page_title="MIRU-PAD", layout="centered")

# --- 【厳守】Termius 風車盤ロジック定数 ---
WINDMILL_MAP = {
    'n1': [0, 7, 4, 1, 8, 5, 2, 9, 6, 3],
    'n2': [0, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    'n3': [0, 3, 6, 9, 2, 5, 8, 1, 4, 7],
    'n4': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
}
INDEX_MAP = {k: {num: i for i, num in enumerate(arr)} for k, arr in WINDMILL_MAP.items()}
GRAVITY_SECTORS = [4, 5, 6]
ANTI_GRAVITY_SECTORS = [9, 0, 1]
DATA_FILE = "miru_fixed.json"

# --- 時間・保存管理エンジン (NEW) ---
def get_target_date_str():
    # サーバーがどこにあってもJST (UTC+9) で判定
    JST = timezone(timedelta(hours=9), 'JST')
    now = datetime.now(JST)
    # 22時以降なら「明日の分」として扱う
    if now.hour >= 22:
        target = now + timedelta(days=1)
    else:
        target = now
    return target.strftime('%Y-%m-%d')

def load_fixed_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_fixed_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

# --- データ取得エンジン ---
def fetch_history(game_type):
    if game_type == 'N4':
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        cols = ['n1', 'n2', 'n3', 'n4']
    else:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers3/index.html"
        cols = ['n1', 'n2', 'n3']

    headers = {"User-Agent": "Mozilla/5.0"}
    history = []
    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.find_all('tr')
        for row in rows:
            data = row.find('td', class_='alnCenter')
            if data:
                val = data.text.strip().replace(' ', '')
                if val.isdigit() and len(val) == len(cols):
                    history.append([int(d) for d in val])
        if not history: raise Exception()
    except:
        history = [[8,2,9,6], [1,3,5,7]] if game_type == 'N4' else [[3,5,8], [9,1,0]]

    last_val_str = "".join(map(str, history[0]))
    trends = {}
    for i, col in enumerate(cols):
        spins = []
        for j in range(len(history) - 1):
            curr_idx = INDEX_MAP[col][history[j][i]]
            prev_idx = INDEX_MAP[col][history[j+1][i]]
            spins.append((curr_idx - prev_idx) % 10)
        trends[col] = Counter(spins).most_common(1)[0][0] if spins else 0
    return last_val_str, trends

# --- 予測生成エンジン (共通) ---
def apply_gravity_final(idx, mode):
    if mode == 'chaos': return random.randint(0, 9)
    sectors = GRAVITY_SECTORS if mode == 'ace' else ANTI_GRAVITY_SECTORS
    candidates = [{'idx': idx, 'score': 1.0}]
    for s in [-1, 1, 0]:
        n_idx = (idx + s) % 10
        if n_idx in sectors: candidates.append({'idx': n_idx, 'score': 1.5})
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[0]['idx'] if random.random() < 0.7 else candidates[-1]['idx']

# --- N3/N4 生成 (全体被りなし、N3下2桁は許容) ---
def generate_predictions(game_type, last_val, trends):
    cols = ['n1', 'n2', 'n3', 'n4'] if game_type == 'N4' else ['n1', 'n2', 'n3']
    last_nums = [int(d) for d in last_val]
    roles = ['ace', 'shift', 'chaos', 'ace', 'shift', 'ace', 'shift', 'ace', 'shift', 'chaos']
    preds = []
    seen_full = set() # 完全一致のみ防ぐ

    for role in roles:
        for attempt in range(20):
            row = ""
            for i, col in enumerate(cols):
                curr_idx = INDEX_MAP[col][last_nums[i]]
                t_spin = trends[col]
                if attempt > 0: t_spin = (t_spin + random.choice([1, -1, 5, 2, -2])) % 10
                
                if role == 'chaos': spin = random.randint(0, 9)
                elif role == 'shift': spin = (t_spin + random.choice([1, -1, 5])) % 10
                else: spin = t_spin if random.random() > 0.2 else (t_spin + 1) % 10
                
                final_idx = apply_gravity_final((curr_idx + spin) % 10, role)
                row += str(WINDMILL_MAP[col][final_idx])
            
            if row not in seen_full:
                seen_full.add(row)
                break
        preds.append(row)
    return preds

# --- Mini独自生成 (被った時だけリスピン) ---
def generate_unique_mini(n3_preds, n3_last_val, n3_trends):
    mini_preds = []
    seen_mini = set()
    cols = ['n2', 'n3'] # MiniはN3の後ろ2つ
    last_nums = [int(d) for d in n3_last_val[-2:]] # Mini用のLast Val
    roles = ['ace', 'shift', 'chaos', 'ace', 'shift', 'ace', 'shift', 'ace', 'shift', 'chaos']

    for i, n3_val in enumerate(n3_preds):
        candidate = n3_val[-2:] # まずはN3から継承
        role = roles[i]

        # もし被っていたら、独自にリスピン
        if candidate in seen_mini:
            for attempt in range(20):
                new_row = ""
                for j, col in enumerate(cols):
                    curr_idx = INDEX_MAP[col][last_nums[j]]
                    t_spin = n3_trends[col]
                    # 強制的に少しズラす
                    t_spin = (t_spin + random.choice([1, -1, 5, 2, -2]) + attempt) % 10
                    
                    if role == 'chaos': spin = random.randint(0, 9)
                    elif role == 'shift': spin = (t_spin + random.choice([1, -1, 5])) % 10
                    else: spin = t_spin if random.random() > 0.2 else (t_spin + 1) % 10
                    
                    final_idx = apply_gravity_final((curr_idx + spin) % 10, role)
                    new_row += str(WINDMILL_MAP[col][final_idx])
                
                if new_row not in seen_mini:
                    candidate = new_row
                    break
        
        seen_mini.add(candidate)
        mini_preds.append(candidate)
    
    return mini_preds

# --- セッション初期化 (固定化ロジック適用) ---
if 'analyzed' not in st.session_state:
    # 1. 履歴取得（これは常に最新の当選結果を表示するために毎回行う）
    n4_l, n4_t = fetch_history('N4')
    n3_l, n3_t = fetch_history('N3')
    st.session_state.n4_res = n4_l
    st.session_state.n3_res = n3_l
    
    # 2. 保存データの確認と読み込み/生成
    target_date = get_target_date_str()
    saved_data = load_fixed_data()
    
    # 今日の日付（22時以降なら明日）のデータがすでにあるか？
    if target_date in saved_data:
        # あればファイルから読み込む（全員同じ数字になる）
        st.session_state.n4_p = saved_data[target_date]['N4']
        st.session_state.n3_p = saved_data[target_date]['N3']
        st.session_state.nm_p = saved_data[target_date]['NM']
    else:
        # なければ生成して保存する（最初の1人が生成し、以降固定される）
        n4_preds = generate_predictions('N4', n4_l, n4_t)
        
        # N3生成
        raw_n3 = generate_predictions('N3', n3_l, n3_t)
        
        # Mini生成
        nm_preds = generate_unique_mini(raw_n3, n3_l, n3_t)
        
        # 保存データの更新
        saved_data[target_date] = {
            'N4': n4_preds,
            'N3': raw_n3,
            'NM': nm_preds
        }
        save_fixed_data(saved_data)
        
        # セッションステートへ反映
        st.session_state.n4_p = n4_preds
        st.session_state.n3_p = raw_n3
        st.session_state.nm_p = nm_preds
    
    st.session_state.analyzed = True

# データマップ
d_map = {
    'N4': st.session_state.n4_p,
    'N3': st.session_state.n3_p,
    'NM': st.session_state.nm_p,
    'L7': ["COMING SOON"]*10, 'L6': ["COMING SOON"]*10, 'ML': ["COMING SOON"]*10, 'B5': ["COMING SOON"]*10, 'KC': ["COMING SOON"]*10
}
l_map = {'N4': st.session_state.n4_res, 'N3': st.session_state.n3_res, 'NM': st.session_state.n3_res[-2:]}

# --- UI構築 (中央揃え維持) ---
html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <style>
        body {{ background-color: #000; color: #fff; font-family: sans-serif; margin: 0; padding: 4px; overflow: hidden; user-select: none; touch-action: manipulation; }}
        .lcd {{ background-color: #9ea7a6; color: #000; border: 4px solid #555; border-radius: 12px; height: 170px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: inset 0 0 10px rgba(0,0,0,0.5); position: relative; }}
        .lcd-label {{ font-size: 10px; color: #444; font-weight: bold; position: absolute; top: 8px; width:100%; text-align:center; }}
        .preds-container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 2px 20px; width: 90%; margin-top: 15px; }}
        .num-text {{ font-family: 'Courier New', monospace; font-weight: bold; letter-spacing: 2px; line-height: 1.1; font-size: 24px; text-align: center; width:100%; }}
        .locked {{ font-size: 14px; color: #555; letter-spacing: 1px; text-align: center; width:100%; }}
        .count-bar {{ display: flex; justify-content: space-between; align-items: center; background: #222; padding: 0 15px; border-radius: 30px; margin: 8px 0; height: 45px; }}
        .btn-round {{ width: 38px; height: 38px; border-radius: 50%; background: #444; color: white; display: flex; justify-content: center; align-items: center; font-size: 24px; font-weight: bold; border: 2px solid #666; cursor: pointer; }}
        .pad-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
        .btn {{ height: 42px; border-radius: 12px; color: white; font-weight: bold; font-size: 12px; display: flex; justify-content: center; align-items: center; border: 2px solid rgba(0,0,0,0.3); box-shadow: 0 3px #000; cursor: pointer; }}
        .btn.active {{ filter: brightness(1.3); border: 2px solid #fff !important; box-shadow: 0 0 15px rgba(255,255,255,0.6); transform: translateY(2px); }}
        .btn-loto {{ background: #E91E63; }} .btn-num {{ background: #009688; }} .btn-mini {{ background: #FF9800; }}
    </style>
</head>
<body>
    <div class="lcd">
        <div id="game-label" class="lcd-label">LAST RESULT</div>
        <div id="preds-box" class="preds-container"></div>
    </div>
    <div class="count-bar">
        <div class="btn-round" onclick="changeCount(-1)">－</div>
        <div id="count-label" style="font-size:18px; font-weight:bold;">2 口</div>
        <div class="btn-round" onclick="changeCount(1)">＋</div>
    </div>
    <div class="pad-grid">
        <div class="btn btn-loto" onclick="setG('L7')">LOTO 7</div>
        <div id="btn-N4" class="btn btn-num" onclick="setG('N4')">Numbers 4</div>
        <div class="btn btn-loto" onclick="setG('L6')">LOTO 6</div>
        <div id="btn-N3" class="btn btn-num" onclick="setG('N3')">Numbers 3</div>
        <div class="btn btn-loto" onclick="setG('ML')">MINI LOTO</div>
        <div id="btn-NM" class="btn btn-mini" onclick="setG('NM')">Numbers mini</div>
        <div class="btn btn-loto">BINGO 5</div><div class="btn btn-loto">着替クー</div>
    </div>
    <script>
        const d = {d_map}; const l = {l_map};
        let curG = 'N4'; let curC = 2;
        function update() {{
            document.getElementById('count-label').innerText = curC + ' 口';
            document.getElementById('game-label').innerText = 'LAST RESULT ('+curG+'): ' + (l[curG]||'----');
            document.querySelectorAll('.btn').forEach(b=>b.classList.remove('active'));
            const active = document.getElementById('btn-'+curG);
            if(active) active.classList.add('active');
            let h = '';
            for(let i=0; i<curC; i++) {{
                let v = d[curG][i];
                let c = v === 'COMING SOON' ? 'locked' : 'num-text';
                h += `<div class="${{c}}">${{v}}</div>`;
            }}
            document.getElementById('preds-box').innerHTML = h;
        }}
        function changeCount(v) {{ curC = Math.max(1, Math.min(10, curC+v)); update(); }}
        function setG(g) {{ curG = g; update(); }}
        update();
    </script>
</body>
</html>
"""
components.html(html_code, height=580, scrolling=False)
