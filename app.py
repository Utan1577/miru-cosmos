import streamlit as st
import random
import requests
import json
import os
import re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from collections import Counter
from urllib.parse import urljoin
import streamlit.components.v1 as components

from core.config import STATUS_FILE, JST, HEADERS
from core.fetch import fetch_last_n_results
from core.model import calc_trends_from_history, generate_predictions, kc_random_10

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def load_status():
    if not os.path.exists(STATUS_FILE):
        return {"pages": {}}
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"pages": {}}

def save_status(data):
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def jst_now():
    return datetime.now(JST)

def ymd(dt):
    return dt.strftime("%Y/%m/%d")

# ------------------------------------------------------------
# Streamlit Page
# ------------------------------------------------------------
st.set_page_config(page_title="MIRU-PAD", layout="centered")

status = load_status()
pages = status.get("pages", {})

if not pages:
    pages = {"N4": [], "N3": [], "NM": [], "KC": []}

# ------------------------------------------------------------
# Fetch / Build pages (basic)
# ------------------------------------------------------------
def build_pages_for_game(game_key, n=10):
    results = fetch_last_n_results(game_key, n=n)
    history = []
    for r in results:
        history.append({"round": r.get("round", 0), "date": r.get("date", ""), "result": r.get("result", ""), "payout": r.get("payout", {})})

    trends = calc_trends_from_history(history)

    preds = generate_predictions(game_key, trends, count=10)

    pages_list = []
    for i, h in enumerate(history):
        pages_list.append({
            "mode": "RESULT",
            "round": h["round"],
            "date": h["date"],
            "result": h["result"],
            "payout": h["payout"],
            "preds": preds,
            "months_used": trends.get("months_used", [])
        })

    now_round = history[0]["round"] + 1 if history else 0
    now_date = ymd(jst_now())
    if game_key == "KC":
        kc_preds = kc_random_10()
        pages_list.insert(0, {
            "mode": "NOW",
            "round": 0,
            "date": "",
            "result": "",
            "payout": {},
            "preds": kc_preds,
            "months_used": []
        })
    else:
        pages_list.insert(0, {
            "mode": "NOW",
            "round": now_round,
            "date": now_date,
            "result": "",
            "payout": {},
            "preds": preds,
            "months_used": trends.get("months_used", [])
        })

    return pages_list

# Initial build if empty
for g in ["N4", "N3", "NM", "KC"]:
    if not pages.get(g):
        pages[g] = build_pages_for_game(g, n=10)

status["pages"] = pages
save_status(status)

# ------------------------------------------------------------
# UI (NOW: result hide + preds centered, BACK: centered, win number black bigger)
# ------------------------------------------------------------
html_code = f"""
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <style>
    body {{ background:#000; color:#fff; font-family:sans-serif; margin:0; padding:0; overflow:hidden; user-select:none; touch-action:manipulation; }}

    .lcd {{
      background-color:#9ea7a6; color:#000;
      border:4px solid #555; border-radius:12px;
      height:190px; box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
      position:relative; padding-top:18px; box-sizing:border-box;
    }}

    .lcd-label {{
      font-size:10px; color:#444; font-weight:bold;
      position:absolute; top:8px; width:100%; text-align:center;
    }}

    .lcd-inner {{
      display:flex; width:100%; height:100%;
      box-sizing:border-box; padding:0 10px 10px 10px; gap:8px;
      align-items:center;
    }}

    .result-panel {{ width:50%; display:flex; flex-direction:column; justify-content:flex-start; position:relative; }}
    .pred-panel {{ width:50%; display:flex; justify-content:center; }}

    .result-line {{ font-size:11px; font-weight:800; line-height:1.15; white-space:nowrap; }}
    .result-spacer {{ height:6px; }}

    .payout-row {{
      display:flex;
      align-items:baseline;
      gap:8px;
      font-size:11px;
      font-weight:800;
      line-height:1.15;
      white-space:nowrap;
    }}
    .payout-k {{
      width:42px;
      text-align:left;
      flex:0 0 auto;
    }}
    .payout-v {{
      flex:1 1 auto;
      text-align:right;
      font-variant-numeric: tabular-nums;
      letter-spacing:0.2px;
    }}

    .legend {{
      position:absolute;
      right:10px;
      bottom:10px;
      font-size:9px;
      font-weight:900;
      opacity:0.85;
      white-space:nowrap;
    }}

    .result-win {{
      color:#000;
      font-weight:900;
      font-size:13px;
      letter-spacing:0.5px;
    }}

    .preds-grid {{
      display:grid;
      grid-template-columns:1fr 1fr;
      column-gap:14px;
      row-gap:10px;
      width:100%;
      justify-items:center;
    }}

    .num-text {{
      font-size:16px;
      font-weight:900;
      letter-spacing:2px;
      color:#000;
      text-shadow:0 1px 0 rgba(255,255,255,0.25);
    }}

    .red {{ color:#d90000; }}
    .blue {{ color:#003ad9; }}

    .nav {{
      display:flex; justify-content:center; gap:10px;
      margin-top:10px;
    }}

    .btn {{
      background:#2b2b2b; color:#fff;
      padding:8px 12px; border-radius:10px; font-weight:800;
      font-size:12px;
      border:2px solid #555;
      cursor:pointer;
    }}
    .btn.active {{ border-color:#fff; }}

    .game-row {{
      display:flex; justify-content:center; gap:10px; margin-top:10px;
    }}

    .count-row {{
      display:flex; justify-content:center; align-items:center; gap:8px; margin-top:10px;
    }}

    .mini-btn {{
      width:34px; height:34px; border-radius:10px;
      display:flex; align-items:center; justify-content:center;
      background:#1f1f1f; border:2px solid #555; color:#fff; font-weight:900; cursor:pointer;
    }}
    .mini-btn:active {{ transform:scale(0.98); }}

    .count-label {{
      width:34px; height:34px; border-radius:10px;
      display:flex; align-items:center; justify-content:center;
      background:#333; border:2px solid #777; color:#fff; font-weight:900;
    }}

    .mode-now .result-panel {{ display:none; }}
    .mode-now .pred-panel {{ width:100%; }}

  </style>
</head>
<body>
  <div class="lcd" id="lcd">
    <div class="lcd-label" id="game-label">NOW</div>
    <div class="lcd-inner">
      <div class="result-panel" id="result-panel"></div>
      <div class="pred-panel" id="pred-panel"></div>
    </div>
  </div>

  <div class="nav">
    <div class="btn" id="btn-back" onclick="navBack()">BACK</div>
    <div class="btn" id="btn-now" onclick="navNow()">NOW</div>
    <div class="btn" id="btn-next" onclick="navNext()">NEXT</div>
  </div>

  <div class="game-row">
    <div class="btn" id="g-n4" onclick="setG('N4')">N4</div>
    <div class="btn" id="g-n3" onclick="setG('N3')">N3</div>
    <div class="btn" id="g-nm" onclick="setG('NM')">NM</div>
    <div class="btn" id="g-kc" onclick="setG('KC')">KC</div>
  </div>

  <div class="count-row">
    <div class="mini-btn" onclick="changeCount(-1)">-</div>
    <div class="count-label" id="count-label">6</div>
    <div class="mini-btn" onclick="changeCount(1)">+</div>
  </div>

  <script>
    const pagesByGame = {json.dumps(pages, ensure_ascii=False)};
    let curG = 'N4';
    let curC = 6;
    const cursor = {{ 'N4': 0, 'N3': 0, 'NM': 0, 'KC': 0 }};

    function escHtml(s){{
      return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
    }}

    function setActiveBtn(){{
      document.getElementById('g-n4').classList.toggle('active', curG==='N4');
      document.getElementById('g-n3').classList.toggle('active', curG==='N3');
      document.getElementById('g-nm').classList.toggle('active', curG==='NM');
      document.getElementById('g-kc').classList.toggle('active', curG==='KC');

      const page=currentPage();
      document.getElementById('btn-back').classList.toggle('active', page && page.mode==='RESULT');
      document.getElementById('btn-now').classList.toggle('active', page && page.mode==='NOW');
      document.getElementById('btn-next').classList.toggle('active', false);
    }}

    function currentPage(){{
      const arr=pagesByGame[curG]||[];
      const idx=cursor[curG]||0;
      return arr[idx]||null;
    }}

    function payoutYen(payout,key){{
      if(!payout) return "";
      if(payout[key] && payout[key].yen) return payout[key].yen;
      return "";
    }}

    function renderResultPanel(page){{
      if(!page) return "";
      const rno=page.round||0;
      const dt=page.date||"";
      const res=page.result||"";
      const pay=page.payout||{{}};

      let h="";
      h+=`<div class="result-line">第${{escHtml(rno)}}回</div>`;
      if(dt) h+=`<div class="result-line">${{escHtml(dt)}}</div>`;

      if(res) {{
        h+=`<div class="result-spacer"></div>`;
        h+=`<div class="result-line">当せん番号</div>`;
        h+=`<div class="result-win">${{escHtml(res)}}</div>`;
      }}

      h+=`<div class="result-spacer"></div>`;

      if(curG==='NM'){{
        const miniY=payoutYen(pay,"MINI") || payoutYen(pay,"Mini") || payoutYen(pay,"ミニ") || payoutYen(pay,"STR");
        h+=`<div class="payout-row"><span class="payout-k">Mini</span><span class="payout-v">${{escHtml(miniY)}}</span></div>`;
        return h;
      }}

      const strY=payoutYen(pay,"STR");
      const boxY=payoutYen(pay,"BOX");
      const ssY=payoutYen(pay,"SET-S");
      const sbY=payoutYen(pay,"SET-B");
      if(strY) h+=`<div class="payout-row"><span class="payout-k">STR</span><span class="payout-v">${{escHtml(strY)}}</span></div>`;
      if(boxY) h+=`<div class="payout-row"><span class="payout-k">BOX</span><span class="payout-v">${{escHtml(boxY)}}</span></div>`;
      if(ssY)  h+=`<div class="payout-row"><span class="payout-k">S-S</span><span class="payout-v">${{escHtml(ssY)}}</span></div>`;
      if(sbY)  h+=`<div class="payout-row"><span class="payout-k">S-B</span><span class="payout-v">${{escHtml(sbY)}}</span></div>`;
      if(curG==='N4' || curG==='N3'){{ h+=`<div class="legend">🟥BX&nbsp;&nbsp;🟦STR</div>`; }}
      return h;
    }}

    function renderMarkedDigitsSB(pred,result){{
      const res=String(result||"");
      const pr=String(pred||"");

      // NM (mini): only STR match (position) -> blue. No BOX (red) used.
      if(curG==='NM'){{
        let out="";
        for(let i=0;i<pr.length;i++) {{
          const ch=pr[i];
          if(i<res.length && pr[i]===res[i]) out+=`<span class="blue">${{escHtml(ch)}}</span>`;
          else out+=escHtml(ch);
        }}
        return out;
      }}

      // N4 / N3: BX -> red, STR -> blue
      const counts={{}};
      for(const ch of res) counts[ch]=(counts[ch]||0)+1;

      const isStr=Array(pr.length).fill(false); // position match
      const isBx=Array(pr.length).fill(false);  // digit match (any position)

      for(let i=0;i<Math.min(pr.length,res.length);i++) {{
        if(pr[i]===res[i] && counts[pr[i]]>0) {{
          isStr[i]=true; counts[pr[i]]--;
        }}
      }}
      for(let i=0;i<pr.length;i++) {{
        if(isStr[i]) continue;
        const ch=pr[i];
        if(counts[ch] && counts[ch]>0) {{
          isBx[i]=true; counts[ch]--;
        }}
      }}

      let out="";
      for(let i=0;i<pr.length;i++) {{
        const ch=pr[i];
        if(isBx[i]) out+=`<span class="red">${{escHtml(ch)}}</span>`;
        else if(isStr[i]) out+=`<span class="blue">${{escHtml(ch)}}</span>`;
        else out+=escHtml(ch);
      }}
      return out;
    }}

    function renderPredPanel(page){{
      if(!page) return "";
      const preds=page.preds||[];
      const res=page.result||"";
      let h='<div class="preds-grid">';
      for(let i=0;i<Math.min(curC,preds.length);i++) {{
        const v=preds[i];
        if(page.mode==='RESULT' && res && (curG==='N4'||curG==='N3'||curG==='NM')) {{
          h+=`<div class="num-text">${{renderMarkedDigitsSB(v,res)}}</div>`;
        }} else {{
          h+=`<div class="num-text">${{escHtml(v)}}</div>`;
        }}
      }}
      h+='</div>';
      return h;
    }}

    function update(){{
      document.getElementById('count-label').innerText=String(curC);
      const page=currentPage();
      setActiveBtn();
      if(!page) return;

      const lcd=document.getElementById('lcd');
      if(page.mode==='NOW') lcd.classList.add('mode-now');
      else lcd.classList.remove('mode-now');

      document.getElementById('game-label').innerText = (page.mode==='NOW' ? 'NOW ('+curG+')' : 'BACK ('+curG+')');

      document.getElementById('result-panel').innerHTML = (page.mode==='RESULT' ? renderResultPanel(page) : "");
      document.getElementById('pred-panel').innerHTML = renderPredPanel(page);
    }}

    function changeCount(v){{ curC=Math.max(1,Math.min(10,curC+v)); update(); }}
    function setG(g){{ curG=g; if(!pagesByGame[curG]) pagesByGame[curG] = [{{mode:'NOW',round:0,date:'',result:'',payout:{{}},preds:Array(10).fill('COMING SOON')}}]; cursor[curG]=0; update(); }}
    function navBack(){{ const arr=pagesByGame[curG]||[]; cursor[curG]=Math.min((cursor[curG]||0)+1, Math.max(0,arr.length-1)); update(); }}
    function navNext(){{ cursor[curG]=Math.max((cursor[curG]||0)-1,0); update(); }}
    function navNow(){{ cursor[curG]=0; update(); }}

    update();
  </script>
</body>
</html>
"""

components.html(html_code, height=610, scrolling=False)
