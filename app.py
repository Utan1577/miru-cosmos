import streamlit as st
import requests
import json
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from collections import Counter
import streamlit.components.v1 as components

from core.config import STATUS_FILE, JST, HEADERS
from core.model import calc_trends_from_history, generate_predictions
from core.mini import nm_drift_unique

st.set_page_config(page_title="MIRU-PAD", layout="centered")

# ============================================================
# 固定保存（過去回は絶対変えない）
# ============================================================
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
        "updated_at": ""
    }

def load_status():
    if not os.path.exists(STATUS_FILE):
        return default_status()
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "games" in data:
            base = default_status()
            for g in base["games"]:
                if g not in data["games"]:
                    data["games"][g] = base["games"][g]
            if "updated_at" not in data:
                data["updated_at"] = ""
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

def ensure_predictions_for_round(game: str, round_no: int, build_func):
    preds_by_round = status["games"][game]["preds_by_round"]
    key = str(round_no)
    if key in preds_by_round and isinstance(preds_by_round[key], list) and len(preds_by_round[key]) > 0:
        return preds_by_round[key]

    preds = build_func()
    preds_by_round[key] = preds

    # cap
    limit = int(status["games"][game].get("history_limit", 120))
    if len(preds_by_round) > limit:
        ks = sorted((int(k) for k in preds_by_round.keys() if str(k).isdigit()), reverse=True)
        keep = set(str(k) for k in ks[:limit])
        for k in list(preds_by_round.keys()):
            if k not in keep:
                preds_by_round.pop(k, None)

    return preds

# ============================================================
# 作戦会議：二段蒸留（原液10本→濃縮10本）
# ============================================================
def distill_predictions(game: str, raw_preds: list[str], out_n: int = 10) -> list[str]:
    if not raw_preds:
        return []

    digits = 4 if game == "N4" else 3 if game == "N3" else None
    if digits is None:
        return raw_preds[:out_n]

    freq = Counter()
    pair = Counter()

    for s in raw_preds:
        ds = [ch for ch in str(s) if ch.isdigit()]
        if len(ds) != digits:
            continue
        freq.update(ds)
        uniq = sorted(set(ds))
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                pair[(uniq[i], uniq[j])] += 1

    if not pair:
        # fallback
        top = [d for d, _ in freq.most_common(digits)]
        while len(top) < digits:
            top.append("0")
        base = "".join(top[:digits])
        outs, used = [], set()
        drift = [0, 1, -1, 2, -2, 3, -3, 4, -4, 5]
        for k in range(out_n * 3):
            d = drift[k % len(drift)]
            cc = list(base)
            cc[-1] = str((int(cc[-1]) + d) % 10)
            cand = "".join(cc)
            key = "".join(sorted(set(cand)))
            if key not in used:
                used.add(key)
                outs.append(cand)
            if len(outs) >= out_n:
                break
        return outs[:out_n]

    def pair_score(p):
        a, b = p
        return (pair[p], freq[a] + freq[b], -int(a) - int(b))

    pairs_sorted = sorted(pair.keys(), key=pair_score, reverse=True)
    used_sets = set()
    pair_used = Counter()
    outs = []

    def attach_score(x, a, b):
        aa, bb = (a, x) if a < x else (x, a)
        cc, dd = (b, x) if b < x else (x, b)
        return pair.get((aa, bb), 0) + pair.get((cc, dd), 0) + 0.25 * freq.get(x, 0)

    drift = [0, 1, -1, 2, -2, 3, -3, 4, -4, 5]

    def build_one(core_pair):
        a, b = core_pair
        base = [a, b]
        candidates = [str(i) for i in range(10) if str(i) not in base]
        candidates.sort(key=lambda x: (attach_score(x, a, b), freq.get(x, 0), -int(x)), reverse=True)

        need = digits - 2
        chosen = base + candidates[:need]

        # 並び評価はしない（セット前提）
        rest = sorted(chosen[2:], key=lambda x: (freq.get(x, 0), -int(x)), reverse=True)
        seq = chosen[:2] + rest
        cand = "".join(seq[:digits])

        key = "".join(sorted(set(cand)))
        if key not in used_sets:
            return cand

        for d in drift:
            cc = list(cand)
            cc[-1] = str((int(cc[-1]) + d) % 10)
            cand2 = "".join(cc)
            key2 = "".join(sorted(set(cand2)))
            if key2 not in used_sets:
                return cand2
        return None

    i = 0
    guard = 0
    while len(outs) < out_n and guard < 500:
        guard += 1
        core = pairs_sorted[i % len(pairs_sorted)]
        if pair_used[core] >= 2:  # 核ペア共有 最大2本
            i += 1
            continue
        cand = build_one(core)
        if cand is None:
            i += 1
            continue
        used_sets.add("".join(sorted(set(cand))))
        pair_used[core] += 1
        outs.append(cand)
        i += 1

    return outs[:out_n]

# ============================================================
# N4 → KC 写像（同一風車。表示はフルーツ）
# ============================================================
KC_FRUIT_MAP = {
    "0": "🍎", "1": "🍊", "2": "🍈", "3": "🍇", "4": "🍑",
    "5": "🍎", "6": "🍊", "7": "🍈", "8": "🍇", "9": "🍑"
}

def kc_from_n4_preds(n4_preds: list[str]) -> list[str]:
    out = []
    for s in n4_preds or []:
        row = ""
        for ch in str(s):
            row += KC_FRUIT_MAP.get(ch, "🍎")
        out.append(row)
    return out

# ============================================================
# 結果取得（N4/N3：楽天バックナンバーを堅牢にパース）
# payoutキーは Frontend が読む STR/BOX/SET-S/SET-B を作る
# ============================================================
ROUND_RE = re.compile(r"(?:回号\s*)?第(\d+)回")
DATE_RE  = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")
NUM4_RE  = re.compile(r"当せん番号\s*([0-9]{4})")
NUM3_RE  = re.compile(r"当せん番号\s*([0-9]{3})")

def fetch_numbers(game: str, need: int = 20):
    if game == "N4":
        past_url = "https://takarakuji.rakuten.co.jp/backnumber/numbers4/"
        digits = 4
        num_re = NUM4_RE
    else:
        past_url = "https://takarakuji.rakuten.co.jp/backnumber/numbers3/"
        digits = 3
        num_re = NUM3_RE

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

        # dedup preserve order
        seen = set()
        mu2 = []
        for u in month_urls:
            if u not in seen:
                seen.add(u)
                mu2.append(u)
        if not mu2:
            mu2 = [past_url]

        used = []
        out = []

        for mu in mu2:
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
                        y = int(m_date.group(1))
                        mo = int(m_date.group(2))
                        d = int(m_date.group(3))
                        date_str = f"{y:04d}/{mo:02d}/{d:02d}"

                    m_num = num_re.search(b)
                    if not m_num:
                        continue
                    num = m_num.group(1)

                    payout = {}

                    def pick(key, label):
                        mm = re.search(rf"{label}\s*([0-9,]+)円", b)
                        if mm:
                            payout[key] = {"yen": mm.group(1)}

                    pick("STR", "ストレート")
                    pick("BOX", "ボックス")
                    pick("SET-S", "セット-ストレート")
                    pick("SET-B", "セット-ボックス")
                    pick("ミニ", "ミニ")

                    out.append({
                        "round": round_no,
                        "date": date_str,
                        "num": num,
                        "payout": payout
                    })
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

# ============================================================
# KC結果取得（専用サイト）
# ============================================================
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
            m1 = re.search(r"1等.*?([\d,]+)円", text)
            m2 = re.search(r"2等.*?([\d,]+)円", text)
            m3 = re.search(r"3等.*?([\d,]+)円", text)
            if m1: payout["1等"] = {"yen": m1.group(1)}
            if m2: payout["2等"] = {"yen": m2.group(1)}
            if m3: payout["3等"] = {"yen": m3.group(1)}

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
            m1 = re.search(r"1等\D*?([\d,]+)円", text)
            m2 = re.search(r"2等\D*?([\d,]+)円", text)
            m3 = re.search(r"3等\D*?([\d,]+)円", text)
            if m1: payout["1等"] = {"yen": m1.group(1)}
            if m2: payout["2等"] = {"yen": m2.group(1)}
            if m3: payout["3等"] = {"yen": m3.group(1)}

            items.append({"round": round_no, "date": date_str, "num": "".join(fruits), "payout": payout})
            if len(items) >= need:
                break

        if not items:
            items = fetch_kc_results_backup(need)
        return items
    except Exception:
        return fetch_kc_results_backup(need)

def norm_date(s: str) -> str:
    ds = re.sub(r"[^0-9]", "", str(s or ""))
    return ds[:8] if len(ds) >= 8 else ds

# ============================================================
# Build pages
# ============================================================
def build_pages_for_numbers(game: str, items: list[dict]):
    digits = 4 if game == "N4" else 3
    cols = ["n1", "n2", "n3", "n4"] if game == "N4" else ["n1", "n2", "n3"]

    items = sorted(items, key=lambda x: x.get("round", 0), reverse=True)
    if not items:
        items = [{"round": 0, "date": "", "num": "0"*digits, "payout": {}}]

    latest = items[0]
    next_round = int(latest["round"]) + 1

    history_nums = [[int(c) for c in it["num"]] for it in items]
    trends = calc_trends_from_history(history_nums, cols)

    def make_preds(last_val: str):
        raw = generate_predictions(game, last_val, trends)   # 原液（10本）
        return distill_predictions(game, raw, out_n=10)      # 濃縮（10本）

    now_preds = ensure_predictions_for_round(game, next_round, lambda: make_preds(latest["num"]))

    pages = [{
        "mode": "NOW",
        "round": next_round,
        "date": "",
        "result": "",
        "payout": {},
        "preds": now_preds
    }]

    by_round = {int(it["round"]): it for it in items}
    for it in items:
        rno = int(it["round"])
        prev = by_round.get(rno - 1)
        seed_last = prev["num"] if prev else it["num"]
        preds = ensure_predictions_for_round(game, rno, lambda sl=seed_last: make_preds(sl))
        pages.append({
            "mode": "RESULT",
            "round": rno,
            "date": it.get("date", ""),
            "result": it.get("num", ""),
            "payout": it.get("payout", {}) or {},
            "preds": preds
        })
    return pages

# fetch N4/N3
n4_items, _ = fetch_numbers("N4", need=30)
n3_items, _ = fetch_numbers("N3", need=30)

n4_pages = build_pages_for_numbers("N4", n4_items)
n3_pages = build_pages_for_numbers("N3", n3_items)

# NM = N3 last2 (deterministic drift)
nm_pages = []
for p in n3_pages:
    preds2 = [str(x)[-2:] for x in (p.get("preds", []) or [])]
    nm_pages.append({
        "mode": p["mode"],
        "round": p["round"],
        "date": p.get("date", ""),
        "result": (p.get("result","")[-2:] if p.get("result","") else ""),
        "payout": p.get("payout", {}) or {},
        "preds": nm_drift_unique(preds2)
    })

# KC pages: results from KC site, preds from N4 preds mapping
kc_items = fetch_kc_results_robust(need=30)
kc_items = sorted(kc_items, key=lambda x: x.get("round", 0), reverse=True)

# map N4 preds by date
n4_date_to_preds = {}
n4_fallback = None
for p in n4_pages:
    if p["mode"] == "RESULT" and p.get("preds"):
        dk = norm_date(p.get("date", ""))
        if dk and dk not in n4_date_to_preds:
            n4_date_to_preds[dk] = p["preds"]
        if n4_fallback is None:
            n4_fallback = p["preds"]

n4_now = n4_pages[0].get("preds", []) if n4_pages else []

kc_pages = [{
    "mode": "NOW",
    "round": (kc_items[0]["round"] + 1) if kc_items else 0,
    "date": "",
    "result": "",
    "payout": {},
    "preds": kc_from_n4_preds(n4_now or n4_fallback or [])
}]

for it in kc_items:
    dk = norm_date(it.get("date", ""))
    src = n4_date_to_preds.get(dk) or n4_fallback or []
    kc_pages.append({
        "mode": "RESULT",
        "round": it.get("round", 0),
        "date": it.get("date", ""),
        "result": it.get("num", ""),
        "payout": it.get("payout", {}) or {},
        "preds": kc_from_n4_preds(src) if src else []
    })

# dummy games
dummy_page = [{"mode":"NOW","round":0,"date":"","result":"","payout":{},"preds":["COMING SOON"]*10}]
pagesByGame = {
    "N4": n4_pages,
    "N3": n3_pages,
    "NM": nm_pages,
    "KC": kc_pages,
    "L7": dummy_page,
    "L6": dummy_page,
    "ML": dummy_page,
    "B5": dummy_page
}

# save status once
save_status(status)

data_for_js = pagesByGame

# ============================================================
# Frontend (JS/HTML) ＝ ゴールデンマスター（あなたの貼ったやつを1文字も変更しない）
# ============================================================
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
