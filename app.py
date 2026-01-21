import streamlit as st
import requests
import json
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup
import streamlit.components.v1 as components
from core.cache import load_results_cache, save_results_cache, cached_items, cache_items_by_round, should_fetch_after_20

from core.config import STATUS_FILE, JST, HEADERS, safe_save_json
from core.fetch import fetch_last_n_results
from core.model import (
    load_pred_store,
    save_pred_store,
    calc_trends_from_history,
    generate_predictions,
    distill_predictions,
    kc_from_n4_preds,
)
from core.mini import nm_drift_unique

st.set_page_config(page_title="MIRU-PAD", layout="centered")

# ---------- UI state (keep non-empty so safe_save_json writes) ----------
def load_ui_state():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return {"game": "N4", "round": None, "mode": "NOW", "updated_at": ""}

def save_ui_state(state: dict):
    state = dict(state)
    state["updated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    safe_save_json(state, STATUS_FILE)

ui_state = load_ui_state()

# ---------- pred store ----------
pred_store = load_pred_store()

def _ensure_game(game: str):
    if "games" not in pred_store:
        pred_store["games"] = {}
    if game not in pred_store["games"]:
        pred_store["games"][game] = {"preds_by_round": {}, "history_limit": 120}
    g = pred_store["games"][game]
    if "preds_by_round" not in g:
        g["preds_by_round"] = {}
    if "history_limit" not in g:
        g["history_limit"] = 120
    return g

def _pad_to_10(preds: list[str], digits: int) -> list[str]:
    preds = [str(x) for x in (preds or []) if str(x).isdigit() and len(str(x)) == digits]
    if len(preds) >= 10:
        return preds[:10]
    seen = set(preds)
    drift = [0, 1, -1, 2, -2, 3, -3, 4, -4, 5]
    base = preds[-1] if preds else ("0" * digits)
    k = 0
    while len(preds) < 10 and k < 5000:
        k += 1
        d = drift[k % len(drift)]
        cc = list(base)
        cc[-1] = str((int(cc[-1]) + d) % 10)
        cand = "".join(cc)
        if cand not in seen:
            seen.add(cand)
            preds.append(cand)
    while len(preds) < 10:
        preds.append("0" * digits)
    return preds[:10]

def ensure_preds(game: str, round_no: int, digits: int, builder):
    g = _ensure_game(game)
    pb = g["preds_by_round"]
    key = str(round_no)
    if key in pb and isinstance(pb[key], list) and len(pb[key]) > 0:
        fixed = _pad_to_10(pb[key], digits)
        if fixed != pb[key]:
            pb[key] = fixed
            save_pred_store(pred_store)
        return fixed

    preds = builder()
    preds = _pad_to_10(preds, digits)
    pb[key] = preds

    # cap
    limit = int(g.get("history_limit", 120))
    keys = [int(k) for k in pb.keys() if str(k).isdigit()]
    keys.sort(reverse=True)
    keep = set(str(k) for k in keys[:limit])
    for k in list(pb.keys()):
        if k not in keep:
            pb.pop(k, None)

    save_pred_store(pred_store)
    return preds

# ---------- dedupe pages by round (fix BACK 3 times issue) ----------
def dedupe_pages(pages: list[dict]) -> list[dict]:
    out = []
    seen = set()
    for p in pages:
        if p.get("mode") == "NOW":
            out.append(p)
            continue
        r = p.get("round")
        if r in seen:
            continue
        seen.add(r)
        out.append(p)
    return out

# ---------- build numbers pages ----------
def build_numbers_pages(game: str, items: list[dict]):
    digits = 4 if game == "N4" else 3
    cols = ["n1","n2","n3","n4"] if digits == 4 else ["n1","n2","n3"]

    items = [dict(x) for x in items if isinstance(x, dict)]
    items.sort(key=lambda x: x.get("round", 0), reverse=True)

    # extra safety: round dedupe
    tmp = []
    seen = set()
    for it in items:
        r = it.get("round")
        if r in seen:
            continue
        seen.add(r)
        tmp.append(it)
    items = tmp

    if not items:
        items = [{"round": 0, "date": "", "num": "0"*digits, "payout": {}}]

    latest = items[0]
    next_round = int(latest.get("round", 0)) + 1

    # NOW trends = full history
    history_nums = [[int(c) for c in it["num"]] for it in items if str(it.get("num","")).isdigit()]
    trends_now = calc_trends_from_history(history_nums, cols)

    def now_builder():
        raw = generate_predictions(game, latest["num"], trends_now)
        return distill_predictions(game, raw, out_n=10)

    now_preds = ensure_preds(game, next_round, digits, now_builder)

    pages = [{
        "mode": "NOW",
        "round": next_round,
        "date": "",
        "result": "",
        "payout": {},
        "preds": now_preds
    }]

    # RESULT pages: per-page trends (sub-history)
    for i, it in enumerate(items):
        sub = items[i:]
        sub_nums = [[int(c) for c in x["num"]] for x in sub if str(x.get("num","")).isdigit()]
        tr = calc_trends_from_history(sub_nums, cols)

        prev = sub[1] if len(sub) > 1 else None
        seed_last = prev["num"] if prev else it["num"]
        rno = int(it.get("round", 0))

        def builder(seed=seed_last, tr2=tr):
            raw = generate_predictions(game, seed, tr2)
            return distill_predictions(game, raw, out_n=10)

        preds = ensure_preds(game, rno, digits, builder)

        pages.append({
            "mode": "RESULT",
            "round": rno,
            "date": it.get("date", ""),
            "result": it.get("num", ""),
            "payout": it.get("payout", {}) or {},
            "preds": preds
        })

    return dedupe_pages(pages)

# ---------- KC: money-plan only, map by date, but round/date synced to N4 ----------
MP_BASE = "https://qoochan.money-plan.net"
MP_ROUND_URL = "https://qoochan.money-plan.net/round/{}/"
KC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
}

FRUIT_MAP = {
    "リンゴ": "🍎", "ミカン": "🍊", "メロン": "🍈", "ブドウ": "🍇", "モモ": "🍑",
    "りんご": "🍎", "みかん": "🍊", "めろん": "🍈", "ぶどう": "🍇", "もも": "🍑"
}

def norm_date(s: str) -> str:
    s = str(s or "")
    m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}/{mo:02d}/{d:02d}"
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}/{mo:02d}/{d:02d}"
    return ""

def moneyplan_latest_round() -> int | None:
    try:
        r = requests.get(MP_BASE, headers=KC_HEADERS, timeout=15)
        r.encoding = r.apparent_encoding
        rounds = [int(x) for x in re.findall(r"/round/(\d+)/", r.text)]
        return max(rounds) if rounds else None
    except Exception:
        return None

def moneyplan_fetch_round(round_no: int):
    url = MP_ROUND_URL.format(round_no)
    r = requests.get(url, headers=KC_HEADERS, timeout=15)
    r.encoding = r.apparent_encoding
    soup = BeautifulSoup(r.text, "html.parser")

    all_text = soup.get_text(" ", strip=True)
    date = norm_date(all_text)

    table = soup.find("table", class_="numbers")
    if not table:
        return None
    t = table.get_text(" ", strip=True)

    fruits = []
    for m in re.findall(r"(リンゴ|ミカン|メロン|ブドウ|モモ)", t):
        v = FRUIT_MAP.get(m, "")
        if v:
            fruits.append(v)
    fruits = fruits[:4]
    if len(fruits) != 4:
        return None

    payout = {}
    m1 = re.search(r"1等\D*?([\d,]+)\s*円", t)
    m2 = re.search(r"2等\D*?([\d,]+)\s*円", t)
    m3 = re.search(r"3等\D*?([\d,]+)\s*円", t)
    if m1: payout["1等"] = {"yen": m1.group(1)}
    if m2: payout["2等"] = {"yen": m2.group(1)}
    if m3: payout["3等"] = {"yen": m3.group(1)}

    return {"date": date, "result": "".join(fruits), "payout": payout}

def moneyplan_build_date_map(target_dates: set[str], max_scan: int = 400):
    latest = moneyplan_latest_round()
    if latest is None:
        return {}
    out = {}
    scanned = 0
    rno = latest
    while rno >= 1 and scanned < max_scan and len(out) < len(target_dates):
        scanned += 1
        try:
            item = moneyplan_fetch_round(rno)
            if item and item.get("date") and item["date"] in target_dates and item["date"] not in out:
                out[item["date"]] = item
        except Exception:
            pass
        rno -= 1
    return out

# ---------- Fetch + Build (CACHE FIRST) ----------
results_cache = load_results_cache()

# N4
if should_fetch_after_20(results_cache, "N4"):
    n4_items_fresh, _ = fetch_last_n_results("N4", need=120)
    cache_items_by_round(results_cache, "N4", n4_items_fresh)
    save_results_cache(results_cache)

n4_items = cached_items(results_cache, "N4", limit=40)

# N3
if should_fetch_after_20(results_cache, "N3"):
    n3_items_fresh, _ = fetch_last_n_results("N3", need=120)
    cache_items_by_round(results_cache, "N3", n3_items_fresh)
    save_results_cache(results_cache)

n3_items = cached_items(results_cache, "N3", limit=40)

# build pages (UIは従来どおり)
n4_pages = build_numbers_pages("N4", n4_items)
n3_pages = build_numbers_pages("N3", n3_items)

# NM (payout uses N3's MINI if present)
nm_pages = []
for p in n3_pages:
    preds2 = [str(x)[-2:] for x in (p.get("preds", []) or [])]
    pay = dict(p.get("payout", {}) or {})
    mini_y = ""
    if isinstance(pay.get("MINI"), dict) and pay["MINI"].get("yen"):
        mini_y = pay["MINI"]["yen"]
    # if fetch used MINI only, ok; else try nothing
    nm_payout = {}
    if mini_y:
        nm_payout["MINI"] = {"yen": mini_y}
    nm_pages.append({
        "mode": p["mode"],
        "round": p["round"],
        "date": p.get("date", ""),
        "result": (p.get("result", "")[-2:] if p.get("result", "") else ""),
        "payout": nm_payout,
        "preds": nm_drift_unique(preds2),
    })

# KC pages synced to N4
target_dates = set()
for p in n4_pages:
    if p["mode"] == "RESULT":
        d = norm_date(p.get("date",""))
        if d:
            target_dates.add(d)
kc_by_date = moneyplan_build_date_map(target_dates, max_scan=400)

kc_pages = []
kc_pages.append({
    "mode": "NOW",
    "round": n4_pages[0]["round"],
    "date": "",
    "result": "",
    "payout": {},
    "preds": kc_from_n4_preds(n4_pages[0].get("preds", []))
})
for p in n4_pages[1:]:
    d = norm_date(p.get("date",""))
    kc = kc_by_date.get(d)
    kc_pages.append({
        "mode": "RESULT",
        "round": p["round"],
        "date": p.get("date",""),
        "result": kc["result"] if kc else "",
        "payout": kc["payout"] if kc else {},
        "preds": kc_from_n4_preds(p.get("preds", []))
    })

dummy = [{"mode":"NOW","round":0,"date":"","result":"","payout":{},"preds":["COMING SOON"]*10}]
data_for_js = {
    "N4": n4_pages,
    "N3": n3_pages,
    "NM": nm_pages,
    "KC": kc_pages,
    "L7": dummy,
    "L6": dummy,
    "ML": dummy,
    "B5": dummy,
}

# write non-empty ui state once
save_ui_state({"game":"N4","round":n4_pages[0]["round"],"mode":"NOW"})

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
