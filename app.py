import streamlit as st
import random
import requests
from bs4 import BeautifulSoup
import streamlit.components.v1 as components

# --- ページ基本設定 ---
st.set_page_config(page_title="MIRU-PAD", layout="centered")

# --- データ取得ロジック ---
def get_n4():
    try:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        res = requests.get(url, timeout=3)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        val = soup.find('td', class_='alnCenter').find('strong').text.strip()
        return val
    except: return "取得中"

def gen_all_data():
    # 全種目の予測を10口分、先読み生成
    data = {}
    for g in ['L7', 'L6', 'ML', 'B5', 'N4', 'N3', 'NM', 'KC']:
        length = 4 if g == 'N4' else (3 if g in ['N3', 'NM'] else 4)
        data[g] = ["".join([str(random.randint(0,9)) for _ in range(length)]) for _ in range(10)]
    return data

# --- メイン描画 ---
n4_last = get_n4()
all_preds = gen_all_data()

# 究極のHTML/JS（ノーリロード・2カラム自動切替エンジン）
html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        body {{ background-color: #000; color: #fff; font-family: sans-serif; margin: 0; padding: 5px; overflow: hidden; user-select: none; }}
        
        /* 液晶枠 */
        .lcd {{ background-color: #9ea7a6; color: #000; border: 4px solid #555; border-radius: 12px; height: 180px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; box-shadow: inset 0 0 10px rgba(0,0,0,0.5); position: relative; }}
        .lcd-label {{ font-size: 10px; color: #444; font-weight: bold; margin-bottom: 2px; position: absolute; top: 10px; }}
        
        /* 予測数字コンテナ：5口以上で横に並べる */
        .preds-container {{ display: flex; flex-wrap: wrap; justify-content: center; align-content: center; gap: 5px 20px; width: 95%; margin-top: 20px; }}
        .num-text {{ font-family: 'Courier New', monospace; font-weight: bold; letter-spacing: 3px; line-height: 1.0; }}
        
        /* 操作系 */
        .count-bar {{ display: flex; justify-content: space-between; align-items: center; background: #222; padding: 5px 15px; border-radius: 30px; margin: 10px 0; height: 55px; }}
        .btn-round {{ width: 45px; height: 45px; border-radius: 50%; background: #444; color: white; display: flex; justify-content: center; align-items: center; font-size: 28px; font-weight: bold; border: 2px solid #666; cursor: pointer; }}
        
        .pad-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
        .btn {{ height: 50px; border-radius: 15px; color: white; font-weight: bold; font-size: 14px; display: flex; justify-content: center; align-items: center; border: 2px solid rgba(0,0,0,0.2); box-shadow: 0 4px #000; cursor: pointer; }}
        .btn:active {{ transform: translateY(2px); box-shadow: 0 2px #000; }}
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
        <div id="count-display" style="font-size:20px; font-weight:bold;">2 口</div>
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

            // 5口を超えたら文字サイズとレイアウトを調整
            let fontSize = 32;
            if (currentCount > 5) fontSize = 24; 
            if (currentCount > 8) fontSize = 20;

            let html = '';
            for(let i=0; i < currentCount; i++) {{
                // 5口を超えた場合、CSSのflex-wrapで自動的に2カラムになるように調整
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

components.html(html_code, height=600, scrolling=False)
