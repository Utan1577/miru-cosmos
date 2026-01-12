import streamlit as st
import random
import requests
from bs4 import BeautifulSoup
import streamlit.components.v1 as components

# --- ページ設定 ---
st.set_page_config(page_title="MIRU-PAD", layout="centered")

# --- セッション管理 ---
if 'g' not in st.session_state: st.session_state.g = 'N4'
if 'c' not in st.session_state: st.session_state.c = 2

# URLパラメータで状態を更新
params = st.query_params
if "g" in params: st.session_state.g = params["g"]
if "a" in params:
    if params["a"] == "p" and st.session_state.c < 10: st.session_state.c += 1
    elif params["a"] == "m" and st.session_state.c > 1: st.session_state.c -= 1
    st.query_params.clear()

# --- データ取得 ---
def get_n4():
    try:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        res = requests.get(url, timeout=3)
        res.encoding = 'Shift_JIS'
        soup = BeautifulSoup(res.text, 'html.parser')
        val = soup.find('td', class_='alnCenter').find('strong').text.strip()
        return val
    except: return "取得中"

def gen_p(g, c):
    l = 4 if g == 'N4' else (3 if g in ['N3','NM'] else 4)
    return ["".join([str(random.randint(0,9)) for _ in range(l)]) for _ in range(c)]

# --- UI構築 ---
game = st.session_state.g
last = get_n4() if game == 'N4' else "----"
preds = gen_p(game, st.session_state.c)
preds_html = "".join([f'<div style="font-size:32px; font-weight:bold; letter-spacing:5px; line-height:1.1;">{p}</div>' for p in preds])

# 画面全体を構築するHTML（ズームロック命令入り）
html_string = f"""
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <style>
        body {{ background-color: #000; color: #fff; font-family: sans-serif; margin: 0; padding: 5px; overflow: hidden; touch-action: manipulation; }}
        .lcd {{ background-color: #9ea7a6; color: #000; border: 4px solid #555; border-radius: 12px; height: 180px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; box-shadow: inset 0 0 10px rgba(0,0,0,0.5); }}
        .count-bar {{ display: flex; justify-content: space-between; align-items: center; background: #222; padding: 5px 15px; border-radius: 30px; margin: 10px 0; height: 60px; }}
        .btn-round {{ width: 48px; height: 48px; border-radius: 50%; background: #444; color: white; text-decoration: none; display: flex; justify-content: center; align-items: center; font-size: 28px; font-weight: bold; border: 2px solid #666; -webkit-tap-highlight-color: transparent; }}
        .pad-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
        .btn {{ height: 55px; border-radius: 15px; color: white; font-weight: bold; font-size: 14px; display: flex; justify-content: center; align-items: center; text-decoration: none; border: 2px solid rgba(0,0,0,0.2); box-shadow: 0 4px #000; -webkit-tap-highlight-color: transparent; }}
        .btn:active {{ transform: translateY(2px); box-shadow: 0 2px #000; }}
        .btn-loto {{ background: #E91E63; }} .btn-num {{ background: #009688; }} .btn-bingo {{ background: #2196F3; }} .btn-mini {{ background: #FF9800; }} .btn-koo {{ background: #FFEB3B; color: #000; }}
    </style>
</head>
<body>
    <div class="lcd">
        <div style="font-size:11px; color:#444; font-weight:bold;">LAST RESULT ({game}): {last}</div>
        <div style="width:70%; border-top:1.5px solid #777; margin:6px 0;"></div>
        {preds_html}
    </div>

    <div class="count-bar">
        <a href="?a=m&g={game}" target="_self" class="btn-round">－</a>
        <div style="font-size:20px; font-weight:bold;">{st.session_state.c} 口</div>
        <a href="?a=p&g={game}" target="_self" class="btn-round">＋</a>
    </div>

    <div class="pad-grid">
        <a href="?g=L7" target="_self" class="btn btn-loto">LOTO 7</a>
        <a href="?g=N4" target="_self" class="btn btn-num">Numbers 4</a>
        <a href="?g=L6" target="_self" class="btn btn-loto">LOTO 6</a>
        <a href="?g=N3" target="_self" class="btn btn-num">Numbers 3</a>
        <a href="?g=ML" target="_self" class="btn btn-loto">MINI LOTO</a>
        <a href="?g=NM" target="_self" class="btn btn-mini">Numbers mini</a>
        <a href="?g=B5" target="_self" class="btn btn-bingo">BINGO 5</a>
        <a href="?g=KC" target="_self" class="btn btn-koo">着替クー</a>
    </div>
</body>
</html>
"""

components.html(html_string, height=650, scrolling=False)
