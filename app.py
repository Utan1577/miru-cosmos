import streamlit as st
import random
import requests
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

# --- データ取得 & 学習エンジン ---
def fetch_history_and_analyze():
    """
    みずほ銀行の直近結果を取得し、風車盤の「回転の癖(スピン)」を分析する
    """
    url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
    headers = {"User-Agent": "Mozilla/5.0"}
    history = []
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # テーブルから過去数回分の数字を抽出
        rows = soup.find_all('tr')
        for row in rows:
            data = row.find('td', class_='alnCenter')
            if data and data.find('strong'):
                val = data.find('strong').text.strip()
                if val.isdigit() and len(val) == 4:
                    history.append([int(d) for d in val])
            elif data:
                val = data.text.strip()
                if val.isdigit() and len(val) == 4:
                    history.append([int(d) for d in val])
                    
        # データが取れなかった場合のダミー（エラー回避用）
        if not history: 
            history = [[8,2,9,6], [1,2,3,4], [5,6,7,8]] 
            
    except:
        history = [[8,2,9,6], [1,2,3,4]] # フォールバック

    # 最新の結果（一番上）
    last_val_str = "".join(map(str, history[0]))
    
    # トレンド分析: 桁ごとの「よくある回転数(スピン)」を計算
    trends = {}
    cols = ['n1', 'n2', 'n3', 'n4']
    
    # 最新から過去へ遡ってスピンを計算
    for i, col in enumerate(cols):
        spins = []
        for j in range(len(history) - 1):
            curr_num = history[j][i]
            prev_num = history[j+1][i] # 一つ前の回
            
            curr_idx = INDEX_MAP[col][curr_num]
            prev_idx = INDEX_MAP[col][prev_num]
            
            # 前回の位置から今回の位置まで何コマ回ったか
            spin = (curr_idx - prev_idx) % 10
            spins.append(spin)
            
        # 最頻出のスピン（Mode）を特定。データ不足ならランダム。
        if spins:
            trends[col] = Counter(spins).most_common(1)[0][0]
        else:
            trends[col] = random.randint(0, 9)
            
    return last_val_str, trends

# アプリ起動時に一度だけ実行（リロードで再学習）
if 'analyzed' not in st.session_state:
    l_val, tr = fetch_history_and_analyze()
    st.session_state.last_val = l_val
    st.session_state.trends = tr
    st.session_state.analyzed = True

# --- 予測生成エンジン (風車盤 + 学習トレンド + 重力) ---
def apply_gravity(idx, mode):
    sectors = GRAVITY_SECTORS if mode == 'stable' else ANTI_GRAVITY_SECTORS
    candidates = [{'idx': idx, 'score': 1.0}]
    weight = 1.5
    
    # 隣接セクターの重力を計算
    for s in [-1, 1, 0]:
        n_idx = (idx + s) % 10
        if n_idx in sectors:
            candidates.append({'idx': n_idx, 'score': weight})
            
    candidates.sort(key=lambda x: x['score'], reverse=True)
    # 確率で重力に引っ張られる
    return candidates[0]['idx'] if random.random() < 0.7 else candidates[-1]['idx']

def generate_predictions_with_logic(count):
    last_val_str = st.session_state.last_val
    trends = st.session_state.trends
    cols = ['n1', 'n2', 'n3', 'n4']
    last_nums = [int(d) for d in last_val_str]
    
    preds = []
    for _ in range(count):
        # 10口の中で、Stable(順当)とInvert(逆張り)を混ぜる
        mode = 'stable' if random.random() > 0.4 else 'invert'
        row_str = ""
        
        for i, col in enumerate(cols):
            curr_idx = INDEX_MAP[col][last_nums[i]]
            
            # 学習したトレンド(癖)を採用するか、少しズラすか
            base_spin = trends[col]
            
            # 揺らぎを与える (Termiusロジックの再現)
            # トレンド通りか、そこからランダムにズレるか
            spin = base_spin if random.random() > 0.3 else random.randint(0, 9)
            
            if mode == 'invert':
                spin = (spin + 5) % 10
            
            target_idx = (curr_idx + spin) % 10
            final_idx = apply_gravity(target_idx, mode)
            
            row_str += str(WINDMILL_MAP[col][final_idx])
        
        preds.append(row_str)
    return preds

# --- データ準備 ---
n4_preds = generate_predictions_with_logic(10)

# 他ゲームはロック
data_map = {}
for g in ['L7', 'L6', 'ML', 'B5', 'N4', 'N3', 'NM', 'KC']:
    if g == 'N4':
        data_map[g] = n4_preds
    else:
        data_map[g] = ["COMING SOON"] * 10

# --- UI構築 (MIRU-PAD Layout - No Changes) ---
html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <style>
        body {{ background-color: #000; color: #fff; font-family: sans-serif; margin: 0; padding: 4px; overflow: hidden; user-select: none; touch-action: manipulation; }}
        .lcd {{ background-color: #9ea7a6; color: #000; border: 4px solid #555; border-radius: 12px; height: 170px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; box-shadow: inset 0 0 10px rgba(0,0,0,0.5); position: relative; }}
        .lcd-label {{ font-size: 10px; color: #444; font-weight: bold; position: absolute; top: 8px; }}
        .preds-container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 2px 20px; width: 90%; margin-top: 15px; }}
        .num-text {{ font-family: 'Courier New', monospace; font-weight: bold; letter-spacing: 2px; line-height: 1.1; font-size: 24px; }}
        .locked {{ font-size: 14px; color: #555; letter-spacing: 1px; font-weight: bold; }}
        .count-bar {{ display: flex; justify-content: space-between; align-items: center; background: #222; padding: 0 15px; border-radius: 30px; margin: 8px 0; height: 45px; }}
        .btn-round {{ width: 38px; height: 38px; border-radius: 50%; background: #444; color: white; display: flex; justify-content: center; align-items: center; font-size: 24px; font-weight: bold; border: 2px solid #666; cursor: pointer; -webkit-tap-highlight-color: transparent; }}
        .pad-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
        .btn {{ height: 42px; border-radius: 12px; color: white; font-weight: bold; font-size: 12px; display: flex; justify-content: center; align-items: center; border: 2px solid rgba(0,0,0,0.3); box-shadow: 0 3px #000; cursor: pointer; transition: 0.2s; -webkit-tap-highlight-color: transparent; }}
        .btn.active {{ filter: brightness(1.3); border: 2px solid #fff !important; box-shadow: 0 0 15px rgba(255,255,255,0.6), inset 0 0 5px rgba(255,255,255,0.4); transform: translateY(2px); }}
        .btn-loto {{ background: #E91E63; }} .btn-num {{ background: #009688; }} .btn-bingo {{ background: #2196F3; }} .btn-mini {{ background: #FF9800; }} .btn-koo {{ background: #FFEB3B; color: #000; }}
    </style>
</head>
<body>
    <div class="lcd">
        <div id="lcd-game-label" class="lcd-label">LAST RESULT (N4): {st.session_state.last_val}</div>
        <div id="preds-box" class="preds-container"></div>
    </div>
    <div class="count-bar">
        <div class="btn-round" onclick="changeCount(-1)">－</div>
        <div id="count-display" style="font-size:18px; font-weight:bold;">2 口</div>
        <div class="btn-round" onclick="changeCount(1)">＋</div>
    </div>
    <div class="pad-grid">
        <div id="btn-L7" class="btn btn-loto" onclick="setGame('L7')">LOTO 7</div>
        <div id="btn-N4" class="btn btn-num" onclick="setGame('N4')">Numbers 4</div>
        <div id="btn-L6" class="btn btn-loto" onclick="setGame('L6')">LOTO 6</div>
        <div id="btn-N3" class="btn btn-num" onclick="setGame('N3')">Numbers 3</div>
        <div id="btn-ML" class="btn btn-loto" onclick="setGame('ML')">MINI LOTO</div>
        <div id="btn-NM" class="btn btn-mini" onclick="setGame('NM')">Numbers mini</div>
        <div id="btn-B5" class="btn btn-bingo" onclick="setGame('B5')">BINGO 5</div>
        <div id="btn-KC" class="btn btn-koo" onclick="setGame('KC')">着替クー</div>
    </div>
    <script>
        const allData = {data_map};
        let currentGame = 'N4';
        let currentCount = 2;
        function updateDisplay() {{
            const box = document.getElementById('preds-box');
            const countLabel = document.getElementById('count-display');
            countLabel.innerText = currentCount + ' 口';
            document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
            const activeBtn = document.getElementById('btn-' + currentGame);
            if(activeBtn) activeBtn.classList.add('active');
            let html = '';
            for(let i=0; i < currentCount; i++) {{
                let val = allData[currentGame][i];
                let className = (val === 'COMING SOON') ? 'locked' : 'num-text';
                let sizeStyle = (currentCount > 6 && val !== 'COMING SOON') ? 'font-size:20px;' : '';
                html += `<div class="${{className}}" style="${{sizeStyle}}">${{val}}</div>`;
            }}
            box.innerHTML = html;
        }}
        function changeCount(val) {{
            currentCount = Math.max(1, Math.min(10, currentCount + val));
            updateDisplay();
        }}
        function setGame(g) {{
            currentGame = g;
            updateDisplay();
        }}
        updateDisplay();
    </script>
</body>
</html>
"""

components.html(html_code, height=580, scrolling=False)
