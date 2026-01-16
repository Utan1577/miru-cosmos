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

# =========================
# MIRU-PAD (RAKUTEN ONLY / AUTO / BACK-NEXT-NOW)
# =========================

st.set_page_config(page_title="MIRU-PAD", layout="centered")

# ------------------------------------------------------------
# JSON storage (shared on server)
# ------------------------------------------------------------
def default_status():
    return {
        "games": {
            "N4": {"preds_by_round": {}, "history_limit": 120},
            "N3": {"preds_by_round": {}, "history_limit": 120},
            "NM": {"preds_by_round": {}, "history_limit": 120},
        },
        "kc": {"mode": "random"},
        "updated_at": "",
    }

def load_status():
    if not os.path.exists(STATUS_FILE):
        return default_status()
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        base = default_status()
        for k, v in base.items():
            if k not in data:
                data[k] = v
        if "games" not in data:
            data["games"] = base["games"]
        else:
            for g in base["games"]:
                if g not in data["games"]:
                    data["games"][g] = base["games"][g]
                if "preds_by_round" not in data["games"][g]:
                    data["games"][g]["preds_by_round"] = {}
                if "history_limit" not in data["games"][g]:
                    data["games"][g]["history_limit"] = base["games"][g]["history_limit"]
        if "kc" not in data:
            data["kc"] = base["kc"]
        return data
    except Exception:
        return default_status()

def save_status(s):
    s["updated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

status = load_status()

# ------------------------------------------------------------
# Build pages (fixed by miru_status.json)
# ------------------------------------------------------------
def ensure_predictions_for_round(game: str, round_no: int, base_last: str, base_trends: dict, base_pred_func) -> list[str]:
    preds_by_round = status["games"][game]["preds_by_round"]
    key = str(round_no)
    if key in preds_by_round and isinstance(preds_by_round[key], list) and len(preds_by_round[key]) > 0:
        return preds_by_round[key]

    preds = base_pred_func(base_last, base_trends)
    preds_by_round[key] = preds

    limit = int(status["games"][game].get("history_limit", 120))
    if len(preds_by_round) > limit:
        ks = sorted((int(k) for k in preds_by_round.keys()), reverse=True)
        keep = set(str(k) for k in ks[:limit])
        for k in list(preds_by_round.keys()):
            if k not in keep:
                preds_by_round.pop(k, None)

    return preds

def build_pages_for_game(game: str, items: list[dict], months_used: list[int]) -> dict:
    # ★ items が空なら落とさない
    if not items:
        return {
            "pages": [{
                "mode": "NOW",
                "round": 0,
                "date": "",
                "result": "",
                "payout": {},
                "preds": ["NO DATA"] * 10,
                "months_used": months_used
            }]
        }

    latest = items[0]
    latest_round = latest["round"]
    next_round = latest_round + 1

    cols = ["n1", "n2", "n3", "n4"] if game == "N4" else ["n1", "n2", "n3"]
    history_nums = [[int(c) for c in it["num"]] for it in items]
    trends = calc_trends_from_history(history_nums, cols)

    def pred_func_last(last_val: str, tr: dict):
        return generate_predictions(game, last_val, tr)

    now_preds = ensure_predictions_for_round(game, next_round, latest["num"], trends, pred_func_last)

    pages = [{
        "mode": "NOW",
        "round": next_round,
        "date": "",
        "result": "",
        "payout": {},
        "preds": now_preds,
        "months_used": months_used
    }]

    by_round = {it["round"]: it for it in items}

    for it in items:
        rno = it["round"]
        prev = by_round.get(rno - 1)
        seed_last = prev["num"] if prev else it["num"]
        preds = ensure_predictions_for_round(game, rno, seed_last, trends, pred_func_last)
        pages.append({
            "mode": "RESULT",
            "round": rno,
            "date": it.get("date", ""),
            "result": it.get("num", ""),
            "payout": it.get("payout", {}) or {},
            "preds": preds,
            "months_used": months_used
        })

    return {"pages": pages}

# ------------------------------------------------------------
# Fetch latest results from Rakuten (N4/N3), build NM from N3
# ------------------------------------------------------------
n4_items, n4_used = fetch_last_n_results("N4", need=20)
n3_items, n3_used = fetch_last_n_results("N3", need=20)

n4_bundle = build_pages_for_game("N4", n4_items, n4_used)
n3_bundle = build_pages_for_game("N3", n3_items, n3_used)

# NM: result = N3 last2
n3_pages = n3_bundle["pages"]
nm_pages = []
for p in n3_pages:
    if p["mode"] == "NOW":
        nm_pages.append({
            "mode": "NOW",
            "round": p["round"],
            "date": "",
            "result": "",
            "payout": p.get("payout", {}) or {},
            "preds": [x[-2:] for x in p["preds"]],
            "months_used": p.get("months_used", [])
        })
    else:
        nm_pages.append({
            "mode": "RESULT",
            "round": p["round"],
            "date": p["date"],
            "result": (p["result"][-2:] if p["result"] else ""),
            "payout": p.get("payout", {}) or {},
            "preds": [x[-2:] for x in p["preds"]],
            "months_used": p.get("months_used", [])
        })

kc_preds = kc_random_10()

save_status(status)

data_for_js = {
    "N4": n4_bundle["pages"],
    "N3": n3_bundle["pages"],
    "NM": nm_pages,
    "KC": [{
        "mode": "NOW",
        "round": 0,
        "date": "",
        "result": "",
        "payout": {},
        "preds": kc_preds,
        "months_used": []
    }]
}

# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
html_code = f"""
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <style>
    body {{ background:#000; color:#fff; font-family:sans-serif; margin:0; padding:4px; overflow:hidden; user-select:none; touch-action:manipulation; }}

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

    .result-panel {{ width:50%; display:flex; flex-direction:column; justify-content:flex-start; }}
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
    .payout-k {{ width:42px; text-align:left; flex:0 0 auto; }}
    .payout-v {{ flex:1 1 auto; text-align:right; font-variant-numeric: tabular-nums; letter-spacing:0.2px; }}

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
      row-gap:2px;
      width:100%;
      align-content:center;
    }}

    .num-text {{
      font-family:'Courier New', monospace;
      font-weight:bold;
      letter-spacing:2px;
      line-height:1.05;
      font-size:20px;
      text-align:left;
      width:100%;
    }}

    .red {{ color:#ff3b30; }}
    .blue {{ color:#007aff; }}

    .lcd.mode-now .result-panel {{ display:none; }}
    .lcd.mode-now .pred-panel {{ width:100%; }}
    .lcd.mode-now .preds-grid {{
      width:75%;
      margin:0 auto;
      justify-items:center;
    }}
    .lcd.mode-now .num-text {{ text-align:center; }}

    .count-bar {{ display:flex; justify-content:space-between; align-items:center; background:#222; padding:0 12px; border-radius:30px; margin:8px 0; height:45px; gap:8px; }}
    .btn-round {{ width:38px; height:38px; border-radius:50%; background:#444; color:#fff; display:flex; justify-content:center; align-items:center; font-size:24px; font-weight:bold; border:2px solid #666; cursor:pointer; }}
    .btn-nav {{ height:36px; border-radius:18px; background:#fff; color:#000; padding:0 10px; display:flex; align-items:center; justify-content:center; font-weight:900; cursor:pointer; border:2px solid rgba(0,0,0,0.3); font-size:12px; }}
    .pad-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:6px; }}
    .btn {{ height:42px; border-radius:12px; color:#fff; font-weight:bold; font-size:12px; display:flex; justify-content:center; align-items:center; border:2px solid rgba(0,0,0,0.3); box-shadow:0 3px #000; cursor:pointer; opacity:0.55; }}
    .btn.active {{ opacity:1.0; filter:brightness(1.12); border:2px solid #fff !important; box-shadow:0 0 15px rgba(255,255,255,0.35); transform: translateY(2px); }}
    .btn-loto {{ background:#E91E63; }}
    .btn-num  {{ background:#009688; }}
    .btn-mini {{ background:#FF9800; }}
    .btn-b5   {{ background:#2196F3; }}
    .btn-kc   {{ background:#FFEB3B; color:#333; }}
  </style>
</head>
<body>
  <div class="lcd" id="lcd">
    <div id="game-label" class="lcd-label"></div>
    <div class="lcd-inner">
      <div id="result-box" class="result-panel"></div>
      <div id="preds-box" class="pred-panel"></div>
    </div>
  </div>

  <div class="count-bar">
    <div class="btn-round" onclick="changeCount(-1)">－</div>
    <div id="count-label" style="font-size:18px; font-weight:bold;">10</div>
    <div class="btn-round" onclick="changeCount(1)">＋</div>
    <div class="btn-nav" onclick="navBack()">BACK</div>
    <div class="btn-nav" onclick="navNext()">NEXT</div>
    <div class="btn-nav" onclick="navNow()">NOW</div>
  </div>

  <div class="pad-grid">
    <div class="btn btn-loto" onclick="setG('L7')">LOTO 7</div>
    <div id="btn-N4" class="btn btn-num" onclick="setG('N4')">Numbers 4</div>

    <div class="btn btn-loto" onclick="setG('L6')">LOTO 6</div>
    <div id="btn-N3" class="btn btn-num" onclick="setG('N3')">Numbers 3</div>

    <div class="btn btn-loto" onclick="setG('ML')">MINI LOTO</div>
    <div id="btn-NM" class="btn btn-mini" onclick="setG('NM')">Numbers mini</div>

    <div class="btn btn-b5" onclick="setG('B5')">BINGO 5</div>
    <div id="btn-KC" class="btn btn-kc" onclick="setG('KC')">着替クー</div>
  </div>

  <script>
    const pagesByGame = {json.dumps(data_for_js, ensure_ascii=False)};
    let curG='N4';
    let curC=10;
    const cursor={{'N4':0,'N3':0,'NM':0,'KC':0,'L7':0,'L6':0,'ML':0,'B5':0}};

    function escHtml(s){{
      return String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
    }}

    function setActiveBtn(){{
      document.querySelectorAll('.btn').forEach(b=>b.classList.remove('active'));
      const active=document.getElementById('btn-'+curG);
      if(active) active.classList.add('active');
    }}

    function currentPage(){{
      const arr=pagesByGame[curG]||[];
      const idx=Math.max(0, Math.min(arr.length-1, cursor[curG]||0));
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
        const miniY=payoutYen(pay,"MINI") || payoutYen(pay,"Mini") || payoutYen(pay,"ミニ") || "—";
        h+=`<div class="payout-row"><span class="payout-k">Mini</span><span class="payout-v">${{escHtml(miniY)}}</span></div>`;
        return h;
      }}

      const strY=payoutYen(pay,"STR");
      const boxY=payoutYen(pay,"BOX");
      const ssY=payoutYen(pay,"SET-S");
      const sbY=payoutYen(pay,"SET-B");
      const miniY=payoutYen(pay,"MINI") || payoutYen(pay,"Mini") || payoutYen(pay,"ミニ");
      if(strY) h+=`<div class="payout-row"><span class="payout-k">STR</span><span class="payout-v">${{escHtml(strY)}}</span></div>`;
      if(boxY) h+=`<div class="payout-row"><span class="payout-k">BOX</span><span class="payout-v">${{escHtml(boxY)}}</span></div>`;
      if(ssY)  h+=`<div class="payout-row"><span class="payout-k">S-S</span><span class="payout-v">${{escHtml(ssY)}}</span></div>`;
      if(sbY)  h+=`<div class="payout-row"><span class="payout-k">S-B</span><span class="payout-v">${{escHtml(sbY)}}</span></div>`;
      if(curG==='N3')
               h+=`<div class="payout-row"><span class="payout-k">Mini</span><span class="payout-v">${{escHtml(miniY || "—")}}</span></div>`;

      if(curG==='N4' || curG==='N3'){{
        h+=`<div class="legend">🟥BX&nbsp;&nbsp;🟦STR</div>`;
      }}
      return h;
    }}

    function renderMarkedDigitsSB(pred,result){{
      const res=String(result||"");
      const pr=String(pred||"");

      if(curG==='NM'){{
        let out="";
        for(let i=0;i<pr.length;i++) {{
          const ch=pr[i];
          if(i<res.length && pr[i]===res[i]) out+=`<span class="blue">${{escHtml(ch)}}</span>`;
          else out+=escHtml(ch);
        }}
        return out;
      }}

      const counts={{}};
      for(const ch of res) counts[ch]=(counts[ch]||0)+1;

      const isStr=Array(pr.length).fill(false);
      const isBx=Array(pr.length).fill(false);

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

      document.getElementById('game-label').innerText = '第'+page.round+'回 予想';
      if(page.mode==='NOW') {{
        document.getElementById('result-box').innerHTML='';
      }} else {{
        document.getElementById('result-box').innerHTML=renderResultPanel(page);
      }}
      document.getElementById('preds-box').innerHTML=renderPredPanel(page);
    }}

    function changeCount(v){{ curC=Math.max(1,Math.min(10,curC+v)); update(); }}
    function setG(g){{ curG=g; if(!pagesByGame[curG]) pagesByGame[curG]=[{{mode:'NOW',round:0,date:'',result:'',payout:{{}},preds:Array(10).fill('COMING SOON')}}]; cursor[curG]=0; update(); }}
    function navBack(){{ const arr=pagesByGame[curG]||[]; cursor[curG]=Math.min((cursor[curG]||0)+1, Math.max(0,arr.length-1)); update(); }}
    function navNext(){{ cursor[curG]=Math.max((cursor[curG]||0)-1,0); update(); }}
    function navNow(){{ cursor[curG]=0; update(); }}

    update();
  </script>
</body>
</html>
"""

components.html(html_code, height=610, scrolling=False)
