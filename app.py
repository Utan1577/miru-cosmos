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
from core.model import calc_trends_from_history, generate_predictions, kc_random_10, distill_predictions, kc_from_n4_preds
from core.mini import nm_drift_unique

# ============================================================
# MIRU-PAD（UIは app 13.py を絶対基準。中身だけアップデート）
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
        if isinstance(data, dict) and "games" in data:
            base = default_status()
            for g in base["games"].keys():
                if g not in data["games"]:
                    data["games"][g] = base["games"][g]
            if "kc" not in data:
                data["kc"] = base["kc"]
            if "updated_at" not in data:
                data["updated_at"] = ""
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
# Fetch fallback (in case core.fetch returns 0 items)
# ------------------------------------------------------------
ROUND_RE = re.compile(r"(?:回号\s*)?第(\d+)回")
DATE_RE  = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")
NUM4_RE  = re.compile(r"当せん番号\s*([0-9]{4})")
NUM3_RE  = re.compile(r"当せん番号\s*([0-9]{3})")

def _fetch_last_n_results_fallback(game: str, need: int = 20):
    if game == "N4":
        past_url = "https://takarakuji.rakuten.co.jp/backnumber/numbers4/"
        digits = 4
    else:
        past_url = "https://takarakuji.rakuten.co.jp/backnumber/numbers3/"
        digits = 3

    try:
        r = requests.get(past_url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")

        month_urls = []
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if not href:
                continue
            u = urljoin(past_url, href)
            if "backnumber" in u or "numbers" in u:
                month_urls.append(u)

        seen = set()
        month_urls2 = []
        for u in month_urls:
            if u not in seen:
                seen.add(u)
                month_urls2.append(u)
        if not month_urls2:
            month_urls2 = [past_url]

        used = []
        out = []

        for mu in month_urls2:
            if len(out) >= need:
                break
            try:
                rr = requests.get(mu, headers=HEADERS, timeout=20)
                rr.raise_for_status()
                rr.encoding = rr.apparent_encoding
                txt = BeautifulSoup(rr.text, "html.parser").get_text("\n", strip=True)

                parts = re.split(r"(?:回号\s*)?(第\d+回)", txt)
                blocks = []
                cur = ""
                for p in parts:
                    if p.startswith("第") and p.endswith("回"):
                        if cur:
                            blocks.append(cur)
                        cur = p
                    else:
                        cur += "\n" + p
                if cur:
                    blocks.append(cur)

                got_any = False
                for b in blocks:
                    m_round = ROUND_RE.search(b)
                    if not m_round:
                        continue
                    round_no = int(m_round.group(1))

                    m_date = DATE_RE.search(b)
                    date_str = ""
                    if m_date:
                        y, mo, d = int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3))
                        date_str = f"{y:04d}/{mo:02d}/{d:02d}"

                    m_num = NUM4_RE.search(b) if digits == 4 else NUM3_RE.search(b)
                    if not m_num:
                        continue
                    num = m_num.group(1)

                    payout = {}
                    for k in ["ストレート", "ボックス", "セット-ストレート", "セット-ボックス", "ミニ"]:
                        mm = re.search(rf"{k}\s*([0-9,]+)円", b)
                        if mm:
                            payout[k] = {"yen": mm.group(1)}

                    out.append({"round": round_no, "date": date_str, "num": num, "payout": payout})
                    got_any = True
                    if len(out) >= need:
                        break

                if got_any:
                    used.append(mu)
            except Exception:
                continue

        out.sort(key=lambda x: x.get("round", 0), reverse=True)
        return out[:need], used
    except Exception:
        return [], []

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
        if not isinstance(it, dict):
            continue
        d = dict(it)
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
        raw = generate_predictions(game, last_val, tr)      # 原液
        return distill_predictions(game, raw, out_n=10)     # 濃縮

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
# KC 結果取得（専用サイト） + 予想はN4濃縮10本を写像
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
                for m2 in matches:
                    v = FRUIT_TEXT_MAP.get(m2, "")
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
# Fetch N4/N3（0件ならフォールバック）
# ------------------------------------------------------------
n4_items, n4_used = fetch_last_n_results("N4", need=20)
if not n4_items:
    n4_items, n4_used = _fetch_last_n_results_fallback("N4", need=20)

n3_items, n3_used = fetch_last_n_results("N3", need=20)
if not n3_items:
    n3_items, n3_used = _fetch_last_n_results_fallback("N3", need=20)

n4_bundle = build_pages_for_game("N4", n4_items, n4_used)
n3_bundle = build_pages_for_game("N3", n3_items, n3_used)

# ------------------------------------------------------------
# NM（ミニ）= N3の下2桁（重複のみ決定論ドリフト）
# ------------------------------------------------------------
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

save_status(status)

data_for_js = {
    "N4": n4_bundle["pages"],
    "N3": n3_bundle["pages"],
    "NM": nm_pages,
    "KC": kc_pages
}

# ------------------------------------------------------------
# UI（app 13.py の html_code をそのまま採用）
# ※ JS template literal は ${ { } } を使っているため f-string安全
# ------------------------------------------------------------
html_code = f"""
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <style>
    body {{ background:#000; color:#fff; font-family:sans-serif; margin:0; overflow:hidden; user-select:none; touch-action:manipulation; }}
    /* ==== UI は app 13.py そのまま ==== */
    .lcd {{ background:#bfc4c8; border-radius:18px; width:92vw; max-width:720px; height:270px; margin:16px auto 10px auto; box-shadow:0 6px 14px rgba(0,0,0,.55); padding:14px 18px; position:relative; color:#111; }}
    .lcd-title {{ text-align:center; font-weight:800; font-size:16px; margin-top:4px; margin-bottom:8px; color:#2a2a2a; }}
    .lcd-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; height:210px; }}
    .left {{ position:relative; padding-left:4px; }}
    .right {{ position:relative; padding-left:6px; }}
    .label {{ font-weight:800; font-size:15px; margin-bottom:6px; }}
    .win {{ font-size:28px; font-weight:900; letter-spacing:6px; margin-top:6px; margin-bottom:6px; }}
    .pay {{ font-size:14px; line-height:1.25; margin-top:8px; white-space:pre; }}
    .predline {{ font-size:22px; font-weight:900; letter-spacing:6px; margin:8px 0; white-space:nowrap; }}
    .legend {{ position:absolute; bottom:10px; right:14px; font-size:12px; color:#222; display:flex; gap:8px; align-items:center; font-weight:800; }}
    .legend .sq {{ width:14px; height:14px; display:inline-block; border-radius:2px; margin-right:4px; }}
    .sq-red {{ background:#e53935; }}
    .sq-blue {{ background:#1e88e5; }}
    .ctl {{ display:flex; justify-content:flex-start; align-items:center; gap:10px; width:92vw; max-width:720px; margin:0 auto 12px auto; }}
    .pill {{ background:#333; border-radius:16px; padding:8px 10px; display:flex; align-items:center; gap:10px; }}
    .pill .pm {{ width:44px; height:44px; border-radius:22px; font-size:26px; font-weight:900; border:2px solid #555; background:#222; color:#fff; }}
    .pill .count {{ color:#fff; font-weight:900; font-size:22px; width:40px; text-align:center; }}
    .nav {{ display:flex; justify-content:center; gap:14px; margin:10px auto 10px auto; width:92vw; max-width:720px; }}
    .btn {{ background:#fff; border:none; border-radius:12px; font-weight:900; font-size:15px; padding:10px 0; width:110px; box-shadow:0 6px 10px rgba(0,0,0,.45); }}
    .btn:active {{ transform:scale(0.98); }}
    .grid {{ width:92vw; max-width:720px; margin:0 auto; display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
    .gbtn {{ padding:18px 0; border-radius:12px; font-weight:900; font-size:16px; border:2px solid rgba(255,255,255,.18); box-shadow:0 10px 14px rgba(0,0,0,.45); text-align:center; color:#fff; }}
    .gbtn.sel {{ border-color:#fff; }}
    .btn-l7 {{ background:#7d1d34; }}
    .btn-l6 {{ background:#7d1d34; opacity:.82; }}
    .btn-ml {{ background:#7d1d34; opacity:.62; }}
    .btn-b5 {{ background:#2a5a86; }}
    .btn-n4 {{ background:#2a6d6e; }}
    .btn-n3 {{ background:#3aa39e; }}
    .btn-nm {{ background:#aa7a1c; }}
    .btn-kc {{ background:#f3f377; color:#111; }}
    .hitBox {{ color:#e53935; }}
    .hitPos {{ color:#1e88e5; }}
  </style>
</head>
<body>
  <div class="lcd">
    <div class="lcd-title" id="hdr">---</div>
    <div class="lcd-grid">
      <div class="left">
        <div class="label">当せん番号</div>
        <div class="win" id="res">----</div>
        <div class="pay" id="pay">--</div>
      </div>
      <div class="right">
        <div class="label">予想（10本）</div>
        <div id="preds"></div>
        <div class="legend">
          <span><span class="sq sq-red"></span>BX</span>
          <span><span class="sq sq-blue"></span>STR</span>
        </div>
      </div>
    </div>
  </div>

  <div class="ctl">
    <div class="pill">
      <button class="pm" onclick="decC()">−</button>
      <div class="count" id="cnt">10</div>
      <button class="pm" onclick="incC()">＋</button>
    </div>

    <div class="nav">
      <button class="btn" onclick="navBack()">BACK</button>
      <button class="btn" onclick="navNow()">NOW</button>
      <button class="btn" onclick="navNext()">NEXT</button>
    </div>
  </div>

  <div class="grid">
    <div class="gbtn btn-l7" onclick="setG('L7')">LOTO 7</div>
    <div class="gbtn btn-n4" onclick="setG('N4')">Numbers 4</div>
    <div class="gbtn btn-l6" onclick="setG('L6')">LOTO 6</div>
    <div class="gbtn btn-n3" onclick="setG('N3')">Numbers 3</div>
    <div class="gbtn btn-ml" onclick="setG('ML')">MINI LOTO</div>
    <div class="gbtn btn-nm" onclick="setG('NM')">Numbers mini</div>
    <div class="gbtn btn-b5" onclick="setG('B5')">BINGO 5</div>
    <div class="gbtn btn-kc" onclick="setG('KC')">着替クー</div>
  </div>

<script>
  const DATA = {json.dumps(data_for_js, ensure_ascii=False)};

  let curG = "N4";
  let cursor = {{"N4":0,"N3":0,"NM":0,"KC":0,"L7":0,"L6":0,"ML":0,"B5":0}};
  let curC = 10;

  function pickPage(game, idx) {{
    const pages = DATA[game] || [];
    if (pages.length === 0) return null;
    const i = Math.max(0, Math.min(idx, pages.length-1));
    return pages[i];
  }}

  function setSelBtn() {{
    document.querySelectorAll('.gbtn').forEach(el=>el.classList.remove('sel'));
    if(curG==='N4') document.querySelector('.btn-n4').classList.add('sel');
    if(curG==='N3') document.querySelector('.btn-n3').classList.add('sel');
    if(curG==='NM') document.querySelector('.btn-nm').classList.add('sel');
    if(curG==='KC') document.querySelector('.btn-kc').classList.add('sel');
  }}

  function setG(g) {{
    curG = g;
    setSelBtn();
    render();
  }}

  function incC() {{
    curC = Math.min(20, curC+1);
    document.getElementById('cnt').innerText = String(curC);
    render();
  }}
  function decC() {{
    curC = Math.max(1, curC-1);
    document.getElementById('cnt').innerText = String(curC);
    render();
  }}

  function navNow() {{
    cursor[curG] = 0;
    render();
  }}
  function navBack() {{
    cursor[curG] = Math.min((DATA[curG]||[]).length-1, cursor[curG] + 1);
    render();
  }}
  function navNext() {{
    cursor[curG] = Math.max((cursor[curG]||0)-1,0);
    render();
  }}

  function getHitMarkup(pred, result) {{
    if (!result) return pred;
    let out = "";
    const res = String(result);
    const used = {{}};
    for (let i=0;i<pred.length;i++) {{
      const ch = pred[i];
      let cntRes = (res.match(new RegExp(ch, 'g'))||[]).length;
      let cntUsed = used[ch]||0;
      if (cntUsed < cntRes) {{
        out += '<span class="hitBox">'+ch+'</span>';
        used[ch] = cntUsed + 1;
      }} else {{
        out += ch;
      }}
    }}
    return out;
  }}

  function render() {{
    const page = pickPage(curG, cursor[curG]);
    if (!page) return;

    const mode = page.mode || "";
    const round = page.round || "";
    const date = page.date || "";
    const title = date ? (date + "　第" + round + "回　結果／予想結果") : ("第" + round + "回　結果／予想結果");
    document.getElementById("hdr").innerText = title;

    const result = page.result || "";
    document.getElementById("res").innerText = result ? result : "----";

    const pay = page.payout || {{}};
    let payTxt = "";
    if (curG === "NM") {{
      if (pay["ミニ"] && pay["ミニ"].yen) {{
        payTxt += "ミニ　　　 " + String(pay["ミニ"].yen) + "円\\n";
      }}
    }} else {{
      const keys = Object.keys(pay);
      keys.forEach(k => {{
        const v = pay[k];
        if (v && v.yen) {{
          payTxt += String(k) + "\\n" + String(v.yen) + "円\\n";
        }}
      }});
    }}
    document.getElementById("pay").innerText = payTxt || "--";

    const preds = (page.preds || []).slice(0, curC);
    let html = "";
    preds.forEach(p => {{
      const s = String(p);
      const box = getHitMarkup(s, result);
      html += '<div class="predline">' + box + '</div>';
    }});
    document.getElementById("preds").innerHTML = html;
  }}

  setSelBtn();
  render();
</script>
</body>
</html>
"""

components.html(html_code, height=820, scrolling=False)
