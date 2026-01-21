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
from core.model import (
    calc_trends_from_history,
    generate_predictions,
    kc_random_10,
    distill_predictions,
    kc_from_n4_preds,
)
from core.mini import nm_drift_unique

# ============================================================
# MIRU-PAD（UIは app 13.py のものをそのまま使う。中身だけアップデート）
# ============================================================

st.set_page_config(page_title="MIRU-PAD", layout="centered")

# ------------------------------------------------------------
# status（固定化の本体）
# ------------------------------------------------------------
def default_status():
    return {
        "games": {
            "N4": {"preds_by_round": {}, "history_limit": 120},
            "N3": {"preds_by_round": {}, "history_limit": 120},
            "NM": {"preds_by_round": {}, "history_limit": 120},
            "KC": {"preds_by_round": {}, "history_limit": 120},
            "L7": {"preds_by_round": {}, "history_limit": 120},
            "L6": {"preds_by_round": {}, "history_limit": 120},
            "ML": {"preds_by_round": {}, "history_limit": 120},
            "B5": {"preds_by_round": {}, "history_limit": 120},
        },
        "updated_at": "",
    }

def load_status():
    if not os.path.exists(STATUS_FILE):
        return default_status()
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "games" in data:
            # 足りないキーは補完（落ちないように）
            base = default_status()
            for g, v in base["games"].items():
                if g not in data["games"]:
                    data["games"][g] = v
            return data
    except Exception:
        pass
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
# 予想固定（未保存回のみ生成）
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

# ------------------------------------------------------------
# N4 / N3 ページ生成
# ★アップデート核心：原液10本 → 濃縮10本（共起ペア核）
# ------------------------------------------------------------
def build_pages_for_game(game: str, items: list, months_used: list) -> dict:
    digits = 4 if game == "N4" else 3

    def _sanitize_num(val):
        s = re.sub(r"\D", "", str(val or ""))
        if len(s) > digits:
            s = s[-digits:]
        return s

    norm_items = []
    for it in (items or []):
        if isinstance(it, dict):
            d = dict(it)
        else:
            continue

        d["num"] = _sanitize_num(d.get("num", ""))
        if len(d["num"]) != digits:
            continue

        if not isinstance(d.get("payout", {}), dict):
            d["payout"] = {}

        if "round" not in d:
            d["round"] = 0
        if "date" not in d:
            d["date"] = ""

        norm_items.append(d)

    # roundが欠けている場合は推定補完
    has_round_int = any(isinstance(x.get("round"), int) for x in norm_items)
    if not has_round_int:
        preds_by_round = status["games"].get(game, {}).get("preds_by_round", {})
        existing = [int(k) for k in preds_by_round.keys() if str(k).isdigit()]
        base_round = max(existing) if existing else len(norm_items)
        for idx, d in enumerate(norm_items):
            d["round"] = base_round - idx

    for idx, d in enumerate(norm_items):
        if not isinstance(d.get("round"), int):
            d["round"] = int(idx)

    norm_items.sort(key=lambda x: x.get("round", 0), reverse=True)

    if not norm_items:
        norm_items = [{"round": 0, "date": "", "num": "0" * digits, "payout": {}}]

    latest = norm_items[0]
    next_round = int(latest["round"]) + 1

    cols = ["n1", "n2", "n3", "n4"] if game == "N4" else ["n1", "n2", "n3"]
    history_nums = [[int(c) for c in it["num"]] for it in norm_items]
    trends = calc_trends_from_history(history_nums, cols)

    def pred_func_last(last_val: str, tr: dict):
        raw = generate_predictions(game, last_val, tr)          # 原液（既存ロジック）
        return distill_predictions(game, raw, out_n=10)         # 濃縮（追加ロジック）

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

    by_round = {int(it["round"]): it for it in norm_items}

    for it in norm_items:
        rno = int(it["round"])
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
# KC 結果取得（専用サイト）
# 予想は N4濃縮10本の写像（同一風車）
# ------------------------------------------------------------
FRUIT_TEXT_MAP = {
    "リンゴ": "🍎", "ミカン": "🍊", "メロン": "🍈", "ブドウ": "🍇", "モモ": "🍑",
    "りんご": "🍎", "みかん": "🍊", "めろん": "🍈", "ぶどう": "🍇", "もも": "🍑",
    "apple": "🍎", "orange": "🍊", "melon": "🍈", "grape": "🍇", "peach": "🍑"
}

def fetch_kc_results_backup(need: int = 20):
    url = "https://takarakuji-loto.jp/qoochan/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")
        items = []
        for tr in soup.find_all("tr"):
            text = tr.get_text(" ", strip=True)
            m_round = re.search(r"第(\d+)回", text)
            if not m_round:
                continue
            round_no = int(m_round.group(1))

            imgs = tr.find_all("img")
            fruits = []
            for img in imgs:
                src = img.get("src", "")
                if "ringo" in src or "apple" in src:
                    fruits.append("🍎")
                elif "mikan" in src or "orange" in src:
                    fruits.append("🍊")
                elif "melon" in src:
                    fruits.append("🍈")
                elif "budou" in src or "grape" in src:
                    fruits.append("🍇")
                elif "momo" in src or "peach" in src:
                    fruits.append("🍑")
            if len(fruits) != 4:
                continue

            payout = {}
            m_p1 = re.search(r"1等.*?([\d,]+)円", text)
            m_p2 = re.search(r"2等.*?([\d,]+)円", text)
            m_p3 = re.search(r"3等.*?([\d,]+)円", text)
            if m_p1: payout["1等"] = {"yen": m_p1.group(1)}
            if m_p2: payout["2等"] = {"yen": m_p2.group(1)}
            if m_p3: payout["3等"] = {"yen": m_p3.group(1)}

            items.append({"round": round_no, "date": "", "num": "".join(fruits), "payout": payout})
            if len(items) >= need:
                break
        return items
    except Exception:
        return []

def fetch_kc_results_robust(need: int = 20):
    url = "https://www.takarakujinet.co.jp/kisekae/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")

        items = []
        for tr in soup.find_all("tr"):
            text = tr.get_text(" ", strip=True)
            if "回号" in text and "等級" in text:
                continue

            m_round = re.search(r"第?(\d+)回", text)
            if not m_round:
                continue
            round_no = int(m_round.group(1))

            m_date = re.search(r"(\d{4}[年/]\d{1,2}[月/]\d{1,2}日?)", text)
            date_str = m_date.group(1) if m_date else ""

            fruits = []
            for img in tr.find_all("img"):
                alt = img.get("alt", "")
                for k, v in FRUIT_TEXT_MAP.items():
                    if k in alt:
                        fruits.append(v)
                        break

            if len(fruits) != 4:
                fruits = []
                matches = re.findall(r"(リンゴ|ミカン|メロン|ブドウ|モモ|りんご|みかん|めろん|ぶどう|もも)", text)
                for m in matches:
                    v = FRUIT_TEXT_MAP.get(m, "")
                    if v:
                        fruits.append(v)
                fruits = fruits[:4]

            if len(fruits) != 4:
                continue

            payout = {}
            m_p1 = re.search(r"1等\D*?([\d,]+)円", text)
            m_p2 = re.search(r"2等\D*?([\d,]+)円", text)
            m_p3 = re.search(r"3等\D*?([\d,]+)円", text)
            if m_p1: payout["1等"] = {"yen": m_p1.group(1)}
            if m_p2: payout["2等"] = {"yen": m_p2.group(1)}
            if m_p3: payout["3等"] = {"yen": m_p3.group(1)}

            items.append({"round": round_no, "date": date_str, "num": "".join(fruits), "payout": payout})
            if len(items) >= need:
                break

        if not items:
            items = fetch_kc_results_backup(need)
        return items
    except Exception:
        return fetch_kc_results_backup(need)

def _norm_date(s: str) -> str:
    if not s:
        return ""
    ds = re.sub(r"[^0-9]", "", s)
    return ds[:8] if len(ds) >= 8 else ds

# ------------------------------------------------------------
# Fetch N4/N3 + build pages
# ------------------------------------------------------------
n4_items, n4_used = fetch_last_n_results("N4", need=20)
n3_items, n3_used = fetch_last_n_results("N3", need=20)

n4_bundle = build_pages_for_game("N4", n4_items, n4_used)
n3_bundle = build_pages_for_game("N3", n3_items, n3_used)

# ------------------------------------------------------------
# NM（ミニ）= N3の下2桁（重複のみ決定論ドリフト）
# ------------------------------------------------------------
nm_pages = []
for p in n3_bundle["pages"]:
    if p["mode"] == "NOW":
        nm_pages.append({
            "mode": "NOW",
            "round": p["round"],
            "date": "",
            "result": "",
            "payout": p.get("payout", {}) or {},
            "preds": nm_drift_unique([x[-2:] for x in p["preds"]]),
            "months_used": p.get("months_used", [])
        })
    else:
        nm_pages.append({
            "mode": "RESULT",
            "round": p["round"],
            "date": p["date"],
            "result": (p["result"][-2:] if p["result"] else ""),
            "payout": p.get("payout", {}) or {},
            "preds": nm_drift_unique([x[-2:] for x in p["preds"]]),
            "months_used": p.get("months_used", [])
        })

# ------------------------------------------------------------
# KC pages（結果はKCサイト、予想はN4濃縮10本を写像）
# ------------------------------------------------------------
kc_items = fetch_kc_results_robust(need=20)
kc_items = sorted(kc_items, key=lambda x: x.get("round", 0), reverse=True)

# N4 preds by date for RESULT pages
n4_date_to_preds = {}
n4_fallback_preds = None
for p in n4_bundle["pages"]:
    if p.get("mode") == "RESULT" and p.get("preds"):
        dk = _norm_date(p.get("date", ""))
        if dk and dk not in n4_date_to_preds:
            n4_date_to_preds[dk] = p["preds"]
        if n4_fallback_preds is None:
            n4_fallback_preds = p["preds"]

n4_now_preds = None
for p in n4_bundle["pages"]:
    if p.get("mode") == "NOW" and p.get("preds"):
        n4_now_preds = p["preds"]
        break

kc_pages = []
kc_pages.append({
    "mode": "NOW",
    "round": (kc_items[0]["round"] + 1) if kc_items else 0,
    "date": "",
    "result": "",
    "payout": {},
    "preds": kc_from_n4_preds(n4_now_preds or n4_fallback_preds or []),
    "months_used": []
})

for it in kc_items:
    dk = _norm_date(it.get("date", ""))
    src = n4_date_to_preds.get(dk) or n4_fallback_preds or []
    preds = kc_from_n4_preds(src) if src else kc_random_10()
    kc_pages.append({
        "mode": "RESULT",
        "round": it.get("round", 0),
        "date": it.get("date", ""),
        "result": it.get("num", ""),
        "payout": it.get("payout", {}) or {},
        "preds": preds,
        "months_used": []
    })

# L7/L6/ML/B5はUIのボタンだけ残す（中身はダミー）
dummy_pages = [{"mode": "NOW", "round": 0, "date": "", "result": "", "payout": {}, "preds": [], "months_used": []}]

save_status(status)

data_for_js = {
    "N4": n4_bundle["pages"],
    "N3": n3_bundle["pages"],
    "NM": nm_pages,
    "KC": kc_pages,
    "L7": dummy_pages,
    "L6": dummy_pages,
    "ML": dummy_pages,
    "B5": dummy_pages,
}

# ============================================================
# ここから下はUI（app 13.py の html_code をそのまま使う）
# ============================================================

html_code = f"""
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <style>
    body {{ background:#000; color:#fff; font-family:sans-serif; margin:0; overflow:hidden; user-select:none; touch-action:manipulation; }}

    .container {{
      display:flex; width:100%; height:100%;
      box-sizing:border-box;
      padding:14px 12px;
      gap:12px;
      justify-content:center;
    }}

    .lcd {{
      width: 92vw;
      max-width: 720px;
      height: 270px;
      background: #c6c9cc;
      border-radius: 18px;
      box-shadow: 0 8px 18px rgba(0,0,0,.55);
      padding: 10px 14px;
      box-sizing:border-box;
      position: relative;
      margin: 14px auto 8px auto;
      color: #111;
    }}

    .lcdTop {{
      display:flex;
      justify-content:space-between;
      align-items:center;
      font-weight:800;
      font-size:16px;
      color:#2a2a2a;
      padding: 4px 6px;
    }}

    .lcdBody {{
      display:grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      height: 215px;
      padding: 6px 6px 0 6px;
      box-sizing:border-box;
    }}

    .leftPane {{
      position: relative;
      padding-left: 4px;
    }}

    .rightPane {{
      position: relative;
      padding-left: 6px;
    }}

    .label {{
      font-weight:800;
      font-size:16px;
      margin-bottom:8px;
    }}

    .winNum {{
      font-size:30px;
      font-weight:900;
      letter-spacing: 6px;
      color: #111;
      margin-top: 10px;
    }}

    .payout {{
      font-size:14px;
      line-height:1.25;
      margin-top: 8px;
      white-space:pre;
    }}

    .predLine {{
      font-size:24px;
      font-weight:900;
      letter-spacing: 6px;
      margin: 8px 0;
      white-space:nowrap;
    }}

    .red {{ color:#ff3b30; }}
    .blue {{ color:#007aff; }}

    .legend {{
      position:absolute;
      bottom: 10px;
      right: 14px;
      display:flex;
      align-items:center;
      gap:10px;
      font-size:12px;
      color:#1f1f1f;
      font-weight:800;
    }}

    .legendBox {{
      display:flex;
      align-items:center;
      gap:6px;
    }}

    .boxSq {{
      width:14px;
      height:14px;
      background:#ff3b30;
      border-radius:2px;
    }}

    .strSq {{
      width:14px;
      height:14px;
      background:#007aff;
      border-radius:2px;
    }}

    .controls {{
      width: 92vw;
      max-width: 720px;
      margin: 8px auto 10px auto;
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap: 10px;
    }}

    .pill {{
      display:flex;
      align-items:center;
      gap:10px;
      background:#2a2a2a;
      padding: 8px 10px;
      border-radius: 18px;
    }}

    .pm {{
      width:46px;
      height:46px;
      border-radius: 23px;
      border: 2px solid #4a4a4a;
      background:#1b1b1b;
      color:#fff;
      font-size: 28px;
      font-weight: 900;
    }}

    .count {{
      width: 44px;
      text-align:center;
      color:#fff;
      font-weight:900;
      font-size: 22px;
    }}

    .nav {{
      display:flex;
      align-items:center;
      gap: 12px;
    }}

    .navBtn {{
      width: 160px;
      height: 52px;
      border:none;
      border-radius: 14px;
      font-size: 18px;
      font-weight: 900;
      background:#fff;
      color:#1773ff;
      box-shadow: 0 8px 14px rgba(0,0,0,.45);
    }}

    .grid {{
      width: 92vw;
      max-width: 720px;
      margin: 0 auto;
      display:grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}

    .gbtn {{
      padding: 18px 0;
      border-radius: 14px;
      font-size: 18px;
      font-weight: 900;
      text-align:center;
      border: 2px solid rgba(255,255,255,.18);
      box-shadow: 0 10px 16px rgba(0,0,0,.45);
      color:#fff;
    }}

    .sel {{ border-color:#fff; }}

    .btn-l7 {{ background:#7d1d34; }}
    .btn-l6 {{ background:#7d1d34; opacity:.82; }}
    .btn-ml {{ background:#7d1d34; opacity:.62; }}
    .btn-b5 {{ background:#2a5a86; }}
    .btn-n4 {{ background:#2a6d6e; }}
    .btn-n3 {{ background:#3aa39e; }}
    .btn-nm {{ background:#aa7a1c; }}
    .btn-kc {{ background:#f3f377; color:#111; }}

  </style>
</head>
<body>

  <div class="lcd">
    <div class="lcdTop">
      <div id="hdr">---</div>
    </div>

    <div class="lcdBody">
      <div class="leftPane">
        <div class="label">当せん番号</div>
        <div class="winNum" id="win">----</div>
        <div class="payout" id="pay">--</div>
      </div>

      <div class="rightPane">
        <div class="label">予想（10本）</div>
        <div id="preds"></div>

        <div class="legend">
          <div class="legendBox"><span class="boxSq"></span>BX</div>
          <div class="legendBox"><span class="strSq"></span>STR</div>
        </div>
      </div>
    </div>
  </div>

  <div class="controls">
    <div class="pill">
      <button class="pm" onclick="decC()">−</button>
      <div class="count" id="cnt">10</div>
      <button class="pm" onclick="incC()">＋</button>
    </div>

    <div class="nav">
      <button class="navBtn" onclick="navBack()">BACK</button>
      <button class="navBtn" onclick="navNext()">NEXT</button>
    </div>
  </div>

  <div class="grid">
    <div id="btnL7" class="gbtn btn-l7" onclick="setG('L7')">LOTO 7</div>
    <div id="btnN4" class="gbtn btn-n4" onclick="setG('N4')">Numbers 4</div>

    <div id="btnL6" class="gbtn btn-l6" onclick="setG('L6')">LOTO 6</div>
    <div id="btnN3" class="gbtn btn-n3" onclick="setG('N3')">Numbers 3</div>

    <div id="btnML" class="gbtn btn-ml" onclick="setG('ML')">MINI LOTO</div>
    <div id="btnNM" class="gbtn btn-nm" onclick="setG('NM')">Numbers mini</div>

    <div id="btnB5" class="gbtn btn-b5" onclick="setG('B5')">BINGO 5</div>
    <div id="btnKC" class="gbtn btn-kc" onclick="setG('KC')">着替クー</div>
  </div>

  <script>
    const pagesByGame = {json.dumps(data_for_js, ensure_ascii=False)};

    let curG='N4';
    let curC=10;
    const cursor={{'N4':0,'N3':0,'NM':0,'KC':0,'L7':0,'L6':0,'ML':0,'B5':0}};

    let viewRound = null;
    let viewMode  = 'NOW'; // 'NOW' or 'BACK'

    function setSel() {{
      const ids=['btnN4','btnN3','btnNM','btnKC','btnL7','btnL6','btnML','btnB5'];
      ids.forEach(id=>document.getElementById(id).classList.remove('sel'));
      if(curG==='N4') document.getElementById('btnN4').classList.add('sel');
      if(curG==='N3') document.getElementById('btnN3').classList.add('sel');
      if(curG==='NM') document.getElementById('btnNM').classList.add('sel');
      if(curG==='KC') document.getElementById('btnKC').classList.add('sel');
      if(curG==='L7') document.getElementById('btnL7').classList.add('sel');
      if(curG==='L6') document.getElementById('btnL6').classList.add('sel');
      if(curG==='ML') document.getElementById('btnML').classList.add('sel');
      if(curG==='B5') document.getElementById('btnB5').classList.add('sel');
    }}

    function escHtml(s){{
      return String(s||'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
    }}

    function getPageByIndex(game, idx){{
      const arr=pagesByGame[game]||[];
      if(arr.length===0) return null;
      const i=Math.max(0, Math.min(arr.length-1, idx));
      return arr[i];
    }}

    function findPageByRound(game, round){{
      const arr=pagesByGame[game]||[];
      for(let i=0;i<arr.length;i++){{
        if(String(arr[i].round)===String(round)) return i;
      }}
      return null;
    }}

    function pickPage(game){{
      const arr=pagesByGame[game]||[];
      if(arr.length===0) return null;

      // viewRound維持（グローバル）
      if(viewRound!==null){{
        const idx=findPageByRound(game, viewRound);
        if(idx!==null) {{
          cursor[game]=idx;
        }} else {{
          // 近いroundへ寄せ
          let best=0;
          let bestDiff=1e18;
          for(let i=0;i<arr.length;i++){{
            const r=Number(arr[i].round||0);
            const diff=Math.abs(r-Number(viewRound));
            if(diff<bestDiff) {{ bestDiff=diff; best=i; }}
          }}
          cursor[game]=best;
        }}
      }}

      // NOW/BACK
      if(viewMode==='NOW'){{
        cursor[game]=0;
      }}

      return getPageByIndex(game, cursor[game]);
    }}

    function payoutYen(pay, key){{
      if(!pay) return "";
      if(pay[key] && pay[key].yen) return pay[key].yen;
      return "";
    }}

    function renderResultPanel(page){{
      if(!page) return "";
      const pay = page.payout || {{}};

      if(curG==='NM') {{
        const miniY = payoutYen(pay,"ミニ") || payoutYen(pay,"MINI") || payoutYen(pay,"Mini") || "";
        if(miniY) return `ミニ　　　 ${escHtml(miniY)}円`;
        return "";
      }}

      let out="";
      const keys = Object.keys(pay);
      for(let i=0;i<keys.length;i++){{
        const k=keys[i];
        const v=pay[k];
        if(v && v.yen){{
          out += `${escHtml(k)}\\n${escHtml(v.yen)}円\\n`;
        }}
      }}
      return out.trim();
    }}

    function markBx(pr, win){{
      if(!win) return pr;
      const counts={{}};
      for(let i=0;i<win.length;i++) {{
        const ch=win[i];
        counts[ch]=(counts[ch]||0)+1;
      }}
      let out="";
      for(let i=0;i<pr.length;i++) {{
        const ch=pr[i];
        if(counts[ch] && counts[ch]>0) {{
          out += `<span class="red">${escHtml(ch)}</span>`;
          counts[ch]--;
        }} else {{
          out += escHtml(ch);
        }}
      }}
      return out;
    }}

    function markStr(pr, win){{
      if(!win) return pr;
      if(win.length!==pr.length) return pr;
      let out="";
      for(let i=0;i<pr.length;i++) {{
        const ch=pr[i];
        if(win[i]===ch) out += `<span class="blue">${escHtml(ch)}</span>`;
        else out += escHtml(ch);
      }}
      return out;
    }}

    function renderPredPanel(page){{
      if(!page) return "";
      const win = page.result || "";
      const preds = (page.preds||[]).slice(0, curC);

      let html="";
      for(let i=0;i<preds.length;i++) {{
        const pr = String(preds[i]||"");
        // 旧UI挙動：赤（BX）を優先表示
        const bx = markBx(pr, win);
        html += `<div class="predLine">${bx}</div>`;
      }}
      return html;
    }}

    function render(){{
      const page = pickPage(curG);
      if(!page) return;

      const date = page.date || "";
      const round = page.round || "";
      const title = (date ? date + "　" : "") + "第" + round + "回　結果／予想結果";

      document.getElementById('hdr').innerText = title;

      const win = page.result || "";
      document.getElementById('win').innerText = win ? win : "----";

      document.getElementById('pay').innerText = renderResultPanel(page) || "--";
      document.getElementById('preds').innerHTML = renderPredPanel(page);

      document.getElementById('cnt').innerText = String(curC);
      setSel();
    }}

    function setG(g){{
      curG=g;
      render();
    }}

    function incC() {{
      curC=Math.min(20, curC+1);
      render();
    }}
    function decC() {{
      curC=Math.max(1, curC-1);
      render();
    }}

    function navBack(){{
      viewMode='BACK';
      const arr=pagesByGame[curG]||[];
      cursor[curG]=Math.min(arr.length-1, (cursor[curG]||0)+1);
      const page=getPageByIndex(curG, cursor[curG]);
      if(page) viewRound=page.round;
      render();
    }}

    function navNext(){{
      viewMode='BACK';
      cursor[curG]=Math.max(0, (cursor[curG]||0)-1);
      const page=getPageByIndex(curG, cursor[curG]);
      if(page) viewRound=page.round;
      render();
    }}

    // init
    setSel();
    render();
  </script>
</body>
</html>
"""

components.html(html_code, height=820, scrolling=False)
