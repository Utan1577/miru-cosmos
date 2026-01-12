import streamlit as st
import random
import requests
from bs4 import BeautifulSoup
import streamlit.components.v1 as components

# --- ページ基本設定 ---
st.set_page_config(page_title="MIRU-PAD", layout="centered")

# --- データ取得ロジック (強化版) ---
def get_n4():
    # 複数の接続を試みるリトライ機能付き
    urls = [
        "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html",
        "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/backnumber/index.html"
    ]
    for url in urls:
        try:
            res = requests.get(url, timeout=5)
            res.encoding = 'Shift_JIS'
            soup = BeautifulSoup(res.text, 'html.parser')
            # 番号を特定
            val_tag = soup.find('td', class_='alnCenter')
            if val_tag and val_tag.find('strong'):
                return val_tag.find('strong').text.strip()
        except:
            continue
    return "非同期" # 失敗時

def gen_all_data():
    data = {}
    for g in ['L7', 'L6', 'ML', 'B5', 'N4', 'N3', 'NM', 'KC']:
        length = 4 if g == 'N4' else (3 if g in ['N3', 'NM'] else 4)
        data[g] = ["".join([str(random.randint(0,9)) for _ in range(length)]) for _ in range(10)]
    return data

# --- メイン描画 ---
n4_last = get_n4()
all_preds = gen_all_data()

# 究極のHTML/JS
html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <style>
        body {{ background-color: #000; color: #fff; font-family: sans-serif; margin: 0; padding: 4px; overflow: hidden; user-select: none; }}
        .lcd {{ background-color: #9ea7a6; color: #000; border: 4px solid #555; border-radius: 12px; height: 170px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; box-shadow: inset 0 0 10px rgba(0,0,0,0.5); position: relative; }}
        .lcd-label {{ font-size: 10px; color: #444; font-weight: bold; margin-bottom: 2px; position: absolute; top: 8px; }}
        .preds-container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 2px 25px; width: 90%; margin-top: 15px; }}
        .num-text {{ font-family: 'Courier New', monospace; font-weight: bold; letter-spacing: 2px; line-height: 1.1; }}
        .count-bar {{ display: flex; justify-content: space-between; align-items: center; background: #222; padding: 0 15px; border-radius: 30px; margin: 6px 0; height: 45px; }}
        .btn-round {{ width: 36px; height: 36px; border-radius: 50%; background: #444; color: white; display: flex; justify-content: center; align-items: center; font-size: 24px; font-weight: bold; border: 2px solid #666; cursor: pointer; }}
        .pad-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 5px; }}
        .btn {{ height: 42px; border-radius: 12px; color: white; font-weight: bold; font-size: 13px; display: flex; justify-content: center; align-items: center; border: 2px solid rgba(0,0,0,0.2); box-shadow: 0 3px #000; cursor: pointer; }}
        .btn:active {{ transform: translateY(2px); box-shadow: 0 1px #000; }}
        .btn-loto {{ background: #E91E63; }} .btn-num {{ background: #009688; }} .btn-bingo {{ background: #2196F3; }} .btn-mini {{ background: #FF9800; }} .btn-koo {{ background: #FFEB3B; color: #000; }}
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
        <div class="btn btn-loto" onclick="setGame('L7')">LOTO 7</div>
        <div class="btn btn-num" onclick="setGame('N4')">Numbers 4</div>
        <div class="btn btn-loto" onclick="setGame('L6')">LOTO 6</div>
        <div class="btn btn-num" onclick="setGame('N3')">Numbers 3</div>
        <div class="btn btn-loto" onclick="setGame('ML')">MINI LOTO</div>
        <div class="btn btn-mini" onclick="setGame('NM')">Numbers mini</div>
        <div class="btn btn-bingo" onclick="setGame('B5')">BINGO 5</div>
        <div class="btn btn-koo" onclick="setGame('KC')">着替クー</div>
    </div>

    <script>
        const allData = {all_preds};
        let currentGame = 'N4';
        let currentCount = 2;

        function updateDisplay() {{
            const box = document.getElementById('preds-box');
            const countLabel = document.getElementById('count-display');
            const gameLabel = document.getElementById('lcd-game-label');
            
            countLabel.innerText = currentCount + ' 口';
            gameLabel.innerText = (currentGame === 'N4') ? 'LAST RESULT (N4): {n4_last}' : 'SYSTEM ACTIVE: ' + currentGame;

            let fontSize = currentCount > 6 ? 22 : 28;
            if (currentCount > 8) fontSize = 20;

            let html = '';
            for(let i=0; i < currentCount; i++) {{
                html += `<div class="num-text" style="font-size: ${{fontSize}}px;">${{allData[currentGame][i]}}</div>`;
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
