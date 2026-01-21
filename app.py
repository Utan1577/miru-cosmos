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

# Safe Import
from core.config import STATUS_FILE, JST, HEADERS, safe_save_json
from core.fetch import fetch_last_n_results
from core.model import calc_trends_from_history, generate_predictions, kc_random_10
from core.mini import nm_drift_unique

# =========================
# MIRU-PAD (RAKUTEN N4/N3 + MIZUHO OFFICIAL KC / AUTO)
# =========================

st.set_page_config(page_title="MIRU-PAD", layout="centered")

# ------------------------------------------------------------
# 1. KC Fetcher (Mizuho Official - Robust)
# ------------------------------------------------------------
FRUIT_MAP = {
    "リンゴ": "🍎", "ミカン": "🍊", "メロン": "🍈", "ブドウ": "🍇", "モモ": "🍑",
    "りんご": "🍎", "みかん": "🍊", "めろん": "🍈", "ぶどう": "🍇", "もも": "🍑",
    "apple": "🍎", "mikan": "🍊", "melon": "🍈", "grape": "🍇", "peach": "🍑",
    "orange": "🍊", "budou": "🍇", "momo": "🍑"
}

def fetch_kc_results_robust(need: int = 20):
    """
    みずほ銀行の着せかえクーちゃんページ（最新月）から
    掲載されている全ての回号を収集する。
    """
    url = "https://www.mizuhobank.co.jp/takarakuji/check/kisekae-qoochan/qoochan/index.html"
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")
        
        items = []
        
        # みずほのページは class="typeTK" のテーブルが複数並んでいることが多い
        # または、大きなテーブルの中に各回が含まれる
        tables = soup.find_all("table", class_="typeTK")
        
        # もし typeTK がなければ、全ての table を走査
        if not tables:
            tables = soup.find_all("table")

        for tbl in tables:
            # 1つのテーブルに1回分の結果が入っているパターンを想定
            text_chunk = tbl.get_text(" ", strip=True)
            
            # 回号を探す "第1234回"
            m_round = re.search(r"第(\d+)回", text_chunk)
            if not m_round:
                continue
            round_no = int(m_round.group(1))

            # 日付を探す
            m_date = re.search(r"(\d{4}年\d{1,2}月\d{1,2}日)", text_chunk)
            date_str = m_date.group(1) if m_date else ""

            # 絵柄を探す
            # "抽せん絵柄" というヘッダの隣のセル、または画像があるセルを探す
            imgs = tbl.find_all("img")
            fruits = []
            for img in imgs:
                alt = img.get("alt", "")
                src = img.get("src", "")
                # alt または src で判定
                check_str = (alt + " " + src).lower()
                
                for k, v in FRUIT_MAP.items():
                    if k in check_str:
                        fruits.append(v)
                        break
                
                if len(fruits) >= 4:
                    break
            
            # 画像で見つからない場合、テキストで探す (altが空の場合など)
            if len(fruits) < 4:
                fruits = []
                # テーブル内の全テキストからフルーツ名を探す
                matches = re.findall(r"(リンゴ|ミカン|メロン|ブドウ|モモ|りんご|みかん|めろん|ぶどう|もも)", text_chunk)
                for m in matches:
                    if m in FRUIT_MAP:
                        fruits.append(FRUIT_MAP[m])
                fruits = fruits[:4]

            if len(fruits) != 4:
                continue
            
            result_str = "".join(fruits)

            # 払戻金
            # "1等 11,400円" のような並びを探す
            payout = {}
            # 1等
            m_p1 = re.search(r"1等.*?([\d,]+)円", text_chunk)
            if m_p1: payout["1等"] = {"yen": m_p1.group(1)}
            
            # 2等
            m_p2 = re.search(r"2等.*?([\d,]+)円", text_chunk)
            if m_p2: payout["2等"] = {"yen": m_p2.group(1)}
            
            # 3等
            m_p3 = re.search(r"3等.*?([\d,]+)円", text_chunk)
            if m_p3: payout["3等"] = {"yen": m_p3.group(1)}

            # 重複チェックしながら追加
            if not any(it["round"] == round_no for it in items):
                items.append({
                    "round": round_no,
                    "date": date_str,
                    "num": result_str,
                    "payout": payout
                })

        # 回号順にソート（新しい順）
        items.sort(key=lambda x: x["round"], reverse=True)
        
        # 1件も取れなかった場合のバックアップ（宝くじLOTOハウス）
        if not items:
            return fetch_kc_backup(need)

        return items[:need], []

    except Exception as e:
        print(f"KC Fetch Error: {e}")
        return [], []

def fetch_kc_backup(need: int = 20):
    """バックアップ: 宝くじロトハウス（構造がシンプル）"""
    url = "https://takarakuji-loto.jp/qoochan/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")
        items = []
        
        # trタグを走査
        for tr in soup.find_all("tr"):
            text = tr.get_text()
            m_round = re.search(r"第(\d+)回", text)
            if not m_round: continue
            round_no = int(m_round.group(1))

            # 画像判定
            imgs = tr.find_all("img")
            fruits = []
            for img in imgs:
                src = img.get("src", "")
                if "ringo" in src or "apple" in src: fruits.append("🍎")
                elif "mikan" in src or "orange" in src: fruits.append("🍊")
                elif "melon" in src: fruits.append("🍈")
                elif "budou" in src or "grape" in src: fruits.append("🍇")
                elif "momo" in src or "peach" in src: fruits.append("🍑")
            
            if len(fruits) != 4: continue
            
            # 金額
            payout = {}
            row_text = tr.get_text(" ", strip=True)
            m_p1 = re.search(r"1等.*?([\d,]+)円", row_text)
            m_p2 = re.search(r"2等.*?([\d,]+)円", row_text)
            m_p3 = re.search(r"3等.*?([\d,]+)円", row_text)
            
            if m_p1: payout["1等"] = {"yen": m_p1.group(1)}
            if m_p2: payout["2等"] = {"yen": m_p2.group(1)}
            if m_p3: payout["3等"] = {"yen": m_p3.group(1)}

            items.append({
                "round": round_no,
                "date": "",
                "num": "".join(fruits),
                "payout": payout
            })
        
        items.sort(key=lambda x: x["round"], reverse=True)
        return items[:need], []
    except:
        return [], []

# ------------------------------------------------------------
# JSON storage
# ------------------------------------------------------------
def default_status():
    return {
        "games": {
            "N4": {"preds_by_round": {}, "history_limit": 120},
            "N3": {"preds_by_round": {}, "history_limit": 120},
            "NM": {"preds_by_round": {}, "history_limit": 120},
            "KC": {"preds_by_round": {}, "history_limit": 120},
        },
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
        return data
    except Exception:
        return default_status()

def save_status(s):
    s["updated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    safe_save_json(s, STATUS_FILE)

status = load_status()

# ------------------------------------------------------------
# Build Pages Logic
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
        ks = sorted((int(k) for k in preds_by_round.keys() if str(k).isdigit()), reverse=True)
        keep = set(str(k) for k in ks[:limit])
        for k in list(preds_by_round.keys()):
            if k not in keep:
                preds_by_round.pop(k, None)

    return preds

def build_pages_for_game(game: str, items: list, months_used: list[int]) -> dict:
    digits = 4 if game == "N4" else 3

    norm_items = []
    for it in (items or []):
        d = dict(it)
        if game != "KC":
            s = re.sub(r"\D", "", str(d.get("num", "")))
            if len(s) > digits: s = s[-digits:]
            d["num"] = s
            if len(s) != digits: continue
        else:
            # KCは4文字(絵文字4つ)
            if len(d.get("num", "")) != 4:
                continue

        if not isinstance(d.get("payout", {}), dict):
            d["payout"] = {}
        norm_items.append(d)

    has_round_int = any(isinstance(x.get("round"), int) for x in norm_items)
    if not has_round_int and norm_items:
        preds_by_round = status["games"].get(game, {}).get("preds_by_round", {})
        existing = [int(k) for k in preds_by_round.keys() if str(k).isdigit()]
        base_round = max(existing) if existing else 0
        if base_round <= 0: base_round = len(norm_items)
        for idx, d in enumerate(norm_items):
            d["round"] = base_round - idx

    for idx, d in enumerate(norm_items):
        if not isinstance(d.get("round"), int):
            d["round"] = int(idx) * -1
    
    uniq = {d["round"]: d for d in norm_items}
    norm_items = sorted(uniq.values(), key=lambda x: x["round"], reverse=True)

    if not norm_items:
        # データがない場合はダミー
        dummy_num = "0"*digits if game!="KC" else "🍎🍎🍎🍎"
        norm_items = [{"round": 0, "date": "", "num": dummy_num, "payout": {}}]

    latest = norm_items[0]
    next_round = latest["round"] + 1

    trends = {}
    if game in ["N4", "N3"]:
        cols = ["n1", "n2", "n3", "n4"] if game == "N4" else ["n1", "n2", "n3"]
        history_nums = [[int(c) for c in it["num"]] for it in norm_items]
        trends = calc_trends_from_history(history_nums, cols)

    def pred_func_wrapper(last_val, tr):
        if game == "KC": return kc_random_10()
        return generate_predictions(game, last_val, tr)

    now_preds = ensure_predictions_for_round(game, next_round, latest["num"], trends, pred_func_wrapper)
    
    pages = [{
        "mode": "NOW",
        "round": next_round,
        "date": "",
        "result": "",
        "payout": {},
        "preds": now_preds,
        "months_used": months_used
    }]

    by_round = {it["round"]: it for it in norm_items}
    for it in norm_items:
        rno = it["round"]
        prev = by_round.get(rno - 1)
        seed_last = prev["num"] if prev else it["num"]
        use_trends = trends if game!="KC" else {} 
        preds = ensure_predictions_for_round(game, rno, seed_last, use_trends, pred_func_wrapper)
        
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
# Fetch & Build
# ------------------------------------------------------------
n4_items, n4_used = fetch_last_n_results("N4", need=20)
n3_items, n3_used = fetch_last_n_results("N3", need=20)
# KCはみずほ公式から取得
kc_items, kc_used = fetch_kc_results_robust(need=20)

n4_bundle = build_pages_for_game("N4", n4_items, n4_used)
n3_bundle = build_pages_for_game("N3", n3_items, n3_used)
kc_bundle = build_pages_for_game("KC", kc_items, [])

n3_pages = n3_bundle["pages"]
nm_pages = []
for p in n3_pages:
    nm_result = p["result"][-2:] if p["result"] else ""
    nm_preds = nm_drift_unique([x[-2:] for x in p["preds"]])
    nm_pages.append({
        "mode": p["mode"],
        "round": p["round"],
        "date": p.get("date", ""),
        "result": nm_result,
        "payout": p.get("payout", {}),
        "preds": nm_preds,
        "months_used": p.get("months_used", [])
    })

save_status(status)

data_for_js = {
    "N4": n4_bundle["pages"],
    "N3": n3_bundle["pages"],
    "NM": nm_pages,
    "KC": kc_bundle["pages"]
}

# ------------------------------------------------------------
# Frontend (JS/HTML)
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
      display:flex; align-items:baseline; gap:8px;
      font-size:11px; font-weight:800; line-height:1.15; white-space:nowrap;
    }}
    .payout-k {{ width:92px; text-align:left; flex:0 0 auto; }}
    .payout-v {{ flex:1 1 auto; text-align:right; font-variant-numeric: tabular-nums; letter-spacing:0.2px; padding-right:6px; }}

    .legend {{
      position:absolute; right:10px; bottom:10px;
      font-size:9px; font-weight:900; opacity:0.85; white-space:nowrap;
    }}

    .result-win {{
      color:#000; font-weight:900; font-size:13px; letter-spacing:0.5px;
    }}

    .preds-grid {{
      display:grid; grid-template-columns:1fr 1fr;
      column-gap:14px; row-gap:2px; width:100%; align-content:center;
    }}

    .num-text {{
      font-family:'Courier New', monospace; font-weight:bold;
      letter-spacing:2px; line-height:1.05; font-size:20px;
      text-align:left; width:100%;
    }}

    /* KC用フォント調整：サイズを16pxにし、letter-spacingを調整 */
    .kc-font {{
      font-family: "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif;
      letter-spacing: 0.1em !important; 
      font-size: 16px !important;
    }}

    .red {{ color:#ff3b30; }}
    .blue {{ color:#007aff; }}
    
    .blue-kc {{ text-shadow: 0 0 5px rgba(0, 122, 255, 0.8); }}
    .red-kc  {{ text-shadow: 0 0 5px rgba(255, 59, 48, 0.8); }}

    .lcd.mode-now .result-panel {{ display:none; }}
    .lcd.mode-now .pred-panel {{ width:100%; }}
    .lcd.mode-now .preds-grid {{ width:75%; margin:0 auto; justify-items:center; }}
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
    let viewRound = null;
    let viewMode  = 'NOW';

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
    function findIndexByRound(game, roundNo){{
      const arr = pagesByGame[game] || [];
      if(arr.length === 0) return 0;
      if(roundNo === null || roundNo === undefined) return 0;
      let bestIdx = 0;
      let bestDiff = 1e18;
      for(let i=0;i<arr.length;i++) {{
        const r = arr[i] && (arr[i].round||0);
        const diff = Math.abs((r||0) - roundNo);
        if(diff < bestDiff) {{
          bestDiff = diff;
          bestIdx = i;
          if(diff === 0) break;
        }}
      }}
      return bestIdx;
    }}
    function payoutYen(payout,key){{
      if(!payout) return "";
      if(payout[key] && payout[key].yen) return payout[key].yen;
      return "";
    }}
    function renderResultPanel(page){{
      if(!page) return "";
      const res=page.result||"";
      const pay=page.payout||{{}};
      let h="";
      if(res) {{
        h+=`<div class="result-spacer"></div>`;
        h+=`<div style="text-align:center;">`;
        h+=`<div class="result-line">当せん番号</div>`;
        const cls = (curG==='KC') ? "result-win kc-font" : "result-win";
        h+=`<div class="${{cls}}" style="font-size:18px;font-weight:900;">${{escHtml(res)}}</div>`;
        h+=`</div>`;
      }}
      h+=`<div class="result-spacer"></div>`;
      if(curG==='NM'){{
        const miniY=payoutYen(pay,"MINI") || payoutYen(pay,"Mini") || payoutYen(pay,"ミニ") || payoutYen(pay,"STR");
        h+=`<div class="payout-row"><span class="payout-k">ミニ</span><span class="payout-v">${{escHtml(miniY)}}</span></div>`;
      }} else if(curG==='KC') {{
        const k1=payoutYen(pay,"1等");
        const k2=payoutYen(pay,"2等");
        const k3=payoutYen(pay,"3等");
        if(k1) h+=`<div class="payout-row"><span class="payout-k">1等</span><span class="payout-v">${{escHtml(k1)}}</span></div>`;
        if(k2) h+=`<div class="payout-row"><span class="payout-k">2等</span><span class="payout-v">${{escHtml(k2)}}</span></div>`;
        if(k3) h+=`<div class="payout-row"><span class="payout-k">3等</span><span class="payout-v">${{escHtml(k3)}}</span></div>`;
      }} else {{
        const strY=payoutYen(pay,"STR");
        const boxY=payoutYen(pay,"BOX");
        const ssY=payoutYen(pay,"SET-S");
        const sbY=payoutYen(pay,"SET-B");
        if(strY) h+=`<div class="payout-row"><span class="payout-k">ストレート</span><span class="payout-v">${{escHtml(strY)}}</span></div>`;
        if(boxY) h+=`<div class="payout-row"><span class="payout-k">ボックス</span><span class="payout-v">${{escHtml(boxY)}}</span></div>`;
        if(ssY)  h+=`<div class="payout-row"><span class="payout-k">Set-ストレート</span><span class="payout-v">${{escHtml(ssY)}}</span></div>`;
        if(sbY)  h+=`<div class="payout-row"><span class="payout-k">Set-ボックス</span><span class="payout-v">${{escHtml(sbY)}}</span></div>`;
      }}
      h+=`<div class="legend">🟥BX&nbsp;&nbsp;🟦STR</div>`;
      return h;
    }}
    function renderMarkedDigitsSB(pred,result){{
      const resArr = [...(result||"")];
      const prArr  = [...(pred||"")];
      if(curG==='NM'){{
        let out="";
        for(let i=0;i<prArr.length;i++) {{
          const ch=prArr[i];
          if(i<resArr.length && prArr[i]===resArr[i]) out+=`<span class="blue">${{ch}}</span>`;
          else out+=ch;
        }}
        return out;
      }}
      const counts={{}};
      for(const ch of resArr) counts[ch]=(counts[ch]||0)+1;
      const isStr=Array(prArr.length).fill(false);
      const isBx=Array(prArr.length).fill(false);
      for(let i=0;i<Math.min(prArr.length,resArr.length);i++) {{
        if(prArr[i]===resArr[i] && counts[prArr[i]]>0) {{
          isStr[i]=true; counts[prArr[i]]--;
        }}
      }}
      for(let i=0;i<prArr.length;i++) {{
        if(isStr[i]) continue;
        const ch=prArr[i];
        if(counts[ch] && counts[ch]>0) {{
          isBx[i]=true; counts[ch]--;
        }}
      }}
      let out="";
      for(let i=0;i<prArr.length;i++) {{
        const ch=prArr[i];
        const clsStr = (curG==='KC') ? 'blue-kc' : 'blue';
        const clsBx  = (curG==='KC') ? 'red-kc' : 'red';
        if(isStr[i]) out+=`<span class="${{clsStr}}">${{ch}}</span>`;
        else if(isBx[i]) out+=`<span class="${{clsBx}}">${{ch}}</span>`;
        else out+=ch;
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
        const cls = (curG==='KC') ? "num-text kc-font" : "num-text";
        if(page.mode==='RESULT' && res && (curG==='N4'||curG==='N3'||curG==='NM'||curG==='KC')) {{
          h+=`<div class="${{cls}}">${{renderMarkedDigitsSB(v,res)}}</div>`;
        }} else {{
          h+=`<div class="${{cls}}">${{escHtml(v)}}</div>`;
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
      viewRound = page.round || viewRound;
      viewMode  = (page.mode==='NOW' ? 'NOW' : 'BACK');
      const lcd=document.getElementById('lcd');
      if(page.mode==='NOW') lcd.classList.add('mode-now');
      else lcd.classList.remove('mode-now');
      document.getElementById('game-label').innerText = (page.mode==='NOW' ? 'NOW ('+curG+')' : 'BACK ('+curG+')');
      if(page.mode==='NOW') {{
        document.getElementById('game-label').innerText = '第' + String(page.round) + '回 予想';
      }} else {{
        const dt = page.date || '';
        const rno = page.round || 0;
        document.getElementById('game-label').innerText = (dt ? (dt + '　') : '') + '第' + String(rno) + '回　結果／予想結果';
        document.getElementById('result-box').innerHTML=renderResultPanel(page);
      }}
      document.getElementById('preds-box').innerHTML=renderPredPanel(page);
    }}
    function changeCount(v){{ curC=Math.max(1,Math.min(10,curC+v)); update(); }}
    function setG(g){{
      curG = g;
      if(!pagesByGame[curG]) {{
        pagesByGame[curG] = [{{mode:'NOW',round:0,date:'',result:'',payout:{{}},preds:Array(10).fill('COMING SOON')}}];
      }}
      if(viewMode === 'NOW') {{
        cursor[curG] = 0;
      }} else {{
        cursor[curG] = findIndexByRound(curG, viewRound);
      }}
      update();
    }}
    function navBack(){{ const arr=pagesByGame[curG]||[]; cursor[curG]=Math.min((cursor[curG]||0)+1, Math.max(0,arr.length-1)); update(); }}
    function navNext(){{ cursor[curG]=Math.max((cursor[curG]||0)-1,0); update(); }}
    function navNow(){{ cursor[curG]=0; update(); }}
    update();
  </script>
</body>
</html>
"""

components.html(html_code, height=610, scrolling=False)
