import streamlit as st
import random
import requests
from bs4 import BeautifulSoup
import streamlit.components.v1 as components

# --- ページ設定 ---
st.set_page_config(page_title="MIRU-PAD", layout="centered")

# --- 【厳守】Termius 風車盤ロジック定数 ---
WINDMILL_MAP = {
    'n1': [0, 7, 4, 1, 8, 5, 2, 9, 6, 3],
    'n2': [0, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    'n3': [0, 3, 6, 9, 2, 5, 8, 1, 4, 7],
    'n4': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
}
# 数字から風車盤のインデックス(位置)を引くマップ
INDEX_MAP = {k: {num: i for i, num in enumerate(arr)} for k, arr in WINDMILL_MAP.items()}

# 重力セクター（吸い寄せられる場所）
GRAVITY_SECTORS = [4, 5, 6]
# 反重力セクター（避けられる場所）
ANTI_GRAVITY_SECTORS = [9, 0, 1]

# --- データ取得 (前回の当選番号) ---
def get_n4_result():
    headers = {"User-Agent": "Mozilla/5.0"}
    urls = [
        "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html",
        "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/backnumber/index.html"
    ]
    for url in urls:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            res.encoding = 'Shift_JIS'
            soup = BeautifulSoup(res.text, 'html.parser')
            target = soup.select_one('td.alnCenter strong')
            if target: return target.text.strip()
            # 予備検索
            alt = soup.find('td', class_='alnCenter')
            if alt: return alt.text.strip()
        except: pass
    return "8296" # 取得失敗時

if 'last_val' not in st.session_state:
    st.session_state.last_val = get_n4_result()

# --- 【厳守】風車盤ロジックエンジン ---
def apply_gravity_bias(current_idx, mode):
    # 重力バイアス計算 (Termiusコードより移植)
    sectors = GRAVITY_SECTORS if mode == 'stable' else ANTI_GRAVITY_SECTORS
    
    # 基本候補
    candidates = [{'idx': current_idx, 'score': 1.0}]
    weight = 1.5 if mode == 'stable' else 2.0
    
    # 隣接セクター(-1, 0, +1)への重力影響
    for s in [-1, 1, 0]:
        neighbor_idx = (current_idx + s) % 10
        if neighbor_idx in sectors:
            candidates.append({'idx': neighbor_idx, 'score': weight})
    
    # スコアが高い順に並べて一番良いものを選ぶ（簡易確率）
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    # 完全に固定せず、スコアに基づいて揺らぎを持たせる
    if random.random() < 0.7:
        return candidates[0]['idx']
    else:
        return candidates[-1]['idx']

def generate_windmill_predictions(last_val_str, count):
    # 前回数値を配列化
    try:
        last_nums = [int(d) for d in last_val_str]
    except:
        last_nums = [8, 2, 9, 6] # エラー時デフォルト

    preds = []
    for _ in range(count):
        # 10口分生成するために、Stable/Invertをランダムに切り替えつつ生成
        mode = 'stable' if random.random() > 0.4 else 'invert'
        row_pred = []
        
        for i, col in enumerate(['n1', 'n2', 'n3', 'n4']):
            # 1. 現在の数字の風車盤位置を取得
            curr_idx = INDEX_MAP[col][last_nums[i]]
            
            # 2. スピン（回転）を決定
            # Termiusでは過去データから傾向を出していたが、今回は即時計算のため
            # 「傾向」を模したランダムスピン(0-9)を与え、Invertなら反転させる
            base_spin = random.randint(0, 9)
            spin = base_spin if mode == 'stable' else (base_spin + 5) % 10
            
            # 3. 回転後の位置
            next_idx = (curr_idx + spin) % 10
            
            # 4. 重力バイアス適用（ここがロジックの肝）
            final_idx = apply_gravity_bias(next_idx, mode)
            
            # 5. 数字に戻す
            row_pred.append(str(WINDMILL_MAP[col][final_idx]))
            
        preds.append("".join(row_pred))
    return preds

# --- データ生成実行 ---
# ここで風車盤ロジックを使って10口生成
n4_preds = generate_windmill_predictions(st.session_state.last_val, 10)

# 他のゲームはロック
data_map = {}
for g in ['L7', 'L6', 'ML', 'B5', 'N4', 'N3', 'NM', 'KC']:
    if g == 'N4':
        data_map[g] = n4_preds
    else:
        data_map[g] = ["COMING SOON"] * 10

# --- 【厳守】UI構築 (MIRU-PAD HTML/JS) ---
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
        
        /* 選択中のボタン：セレクト表示 */
        .btn.active {{ 
            filter: brightness(1.3); 
            border: 2px solid #fff !important; 
            box-shadow: 0 0 15px rgba(255,255,255,0.6), inset 0 0 5px rgba(255,255,255,0.4);
            transform: translateY(2px);
        }}

        .btn-loto {{ background: #E91E63; }} 
        .btn-num {{ background: #009688; }} 
        .btn-bingo {{ background: #2196F3; }} 
        .btn-mini {{ background: #FF9800; }} 
        .btn-koo {{ background: #FFEB3B; color: #000; }}
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
                
                // 口数が多いときはフォントを微調整
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
