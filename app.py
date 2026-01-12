import streamlit as st
import random
import requests
from bs4 import BeautifulSoup
import streamlit.components.v1 as components

# --- ページ設定 ---
st.set_page_config(page_title="MIRU-PAD", layout="centered")

# --- データ取得 (Python側でしっかり取得) ---
def get_n4_result():
    try:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        res = requests.get(url, timeout=5)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        val = soup.find('td', class_='alnCenter').find('strong').text.strip()
        return val
    except:
        return "取得中..."

n4_last = get_n4_result()

# 各種目の予測データを生成 (N4以外は"LOCKED"にする)
data = {}
games = ['L7', 'L6', 'ML', 'B5', 'N4', 'N3', 'NM', 'KC']
for g in games:
    if g == 'N4':
        data[g] = ["".join([str(random.randint(0,9)) for _ in range(4)]) for _ in range(10)]
    else:
        data[g] = ["COMING SOON" for _ in range(10)]

# --- UI構築 (JS/CSS) ---
html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <style>
        body {{ background-color: #000; color: #fff; font-family: sans-serif; margin: 0; padding: 4px; overflow: hidden; user-select: none; }}
        
        .lcd {{ background-color: #9ea7a6; color: #000; border: 4px solid #555; border-radius: 12px; height: 170px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; box-shadow: inset 0 0 10px rgba(0,0,0,0.5); position: relative; }}
        .lcd-label {{ font-size: 10px; color: #444; font-weight: bold; position: absolute; top: 8px; }}
        
        .preds-container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 2px 20px; width: 90%; margin-top: 15px; }}
        .num-text {{ font-family: 'Courier New', monospace; font-weight: bold; letter-spacing: 2px; line-height: 1.1; font-size: 24px; }}
        .locked {{ font-size: 14px; color: #555; letter-spacing: 1px; }}

        .count-bar {{ display: flex; justify-content: space-between; align-items: center; background: #222; padding: 0 15px; border-radius: 30px; margin: 8px 0; height: 45px; }}
        .btn-round {{ width: 38px; height: 38px; border-radius: 50%; background: #444; color: white; display: flex; justify-content: center; align-items: center; font-size: 24px; font-weight: bold; border: 2px solid #666; cursor: pointer; }}
        
        .pad-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
        .btn {{ height: 42px; border-radius: 12px; color: white; font-weight: bold; font-size: 12px; display: flex; justify-content: center; align-items: center; border: 2px solid rgba(0,0,0,0.3); box-shadow: 0 3px #000; cursor: pointer; transition: 0.2s; }}
        
        /* 選択中の状態：光らせて少し凹ませる */
        .btn.active {{ 
            filter: brightness(1.5); 
            border: 2px solid #fff !important; 
            box-shadow: inset 0 0 10px rgba(255,255,255,0.5), 0 1px #000;
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
        <div id="lcd-game-label" class="lcd-label">LAST RESULT (N4): {n4_last}</div>
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
        const allData = {data};
        let currentGame = 'N4';
        let currentCount = 2;

        function updateDisplay() {{
            const box = document.getElementById('preds-box');
            const countLabel = document.getElementById('count-display');
            
            countLabel.innerText = currentCount + ' 口';

            // ボタンの選択状態を更新
            document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
            document.getElementById('btn-' + currentGame).classList.add('active');

            let html = '';
            for(let i=0; i < currentCount; i++) {{
                let val = allData[currentGame][i];
                let className = (val === 'COMING SOON') ? 'locked' : 'num-text';
                html += `<div class="${{className}}">${{val}}</div>`;
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
