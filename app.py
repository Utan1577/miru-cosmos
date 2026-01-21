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
from core.model import calc_trends_from_history, generate_predictions, kc_random_10, distill_predictions, kc_from_n4_preds
from core.mini import nm_drift_unique

st.set_page_config(page_title="MIRU-PAD", layout="centered")

# ------------------------------------------------------------
# Load / Save Status
# ------------------------------------------------------------
def load_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "games" in data:
                return data
        except Exception:
            pass
    return {
        "games": {
            "N4": {"preds_by_round": {}, "history_limit": 120},
            "N3": {"preds_by_round": {}, "history_limit": 120},
            "NM": {"preds_by_round": {}, "history_limit": 120},
            "KC": {"preds_by_round": {}, "history_limit": 120}
        },
        "updated_at": ""
    }

def save_status(status_obj):
    status_obj["updated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    safe_save_json(STATUS_FILE, status_obj)

status = load_status()

# ------------------------------------------------------------
# 1. KC Fetcher (Takarakuji Net for History)
# ------------------------------------------------------------
FRUIT_TEXT_MAP = {
    "リンゴ": "🍎", "ミカン": "🍊", "メロン": "🍈", "ブドウ": "🍇", "モモ": "🍑",
    "りんご": "🍎", "みかん": "🍊", "めろん": "🍈", "ぶどう": "🍇", "もも": "🍑",
    "apple": "🍎", "orange": "🍊", "melon": "🍈", "grape": "🍇", "peach": "🍑"
}

def fetch_kc_results_backup(need: int = 20):
    """バックアップソース: 宝くじロトハウス"""
    url = "https://takarakuji-loto.jp/qoochan/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")
        items = []
        rows = soup.find_all("tr")
        for tr in rows:
            text = tr.get_text()
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

            row_text = tr.get_text(" ", strip=True)
            payout = {}
            m_p1 = re.search(r"1等.*?([\d,]+)円", row_text)
            m_p2 = re.search(r"2等.*?([\d,]+)円", row_text)
            m_p3 = re.search(r"3等.*?([\d,]+)円", row_text)

            if m_p1:
                payout["1等"] = {"yen": m_p1.group(1)}
            if m_p2:
                payout["2等"] = {"yen": m_p2.group(1)}
            if m_p3:
                payout["3等"] = {"yen": m_p3.group(1)}

            items.append({
                "round": round_no,
                "date": "",
                "num": "".join(fruits),
                "payout": payout
            })
            if len(items) >= need:
                break
        return items, []
    except Exception:
        return [], []

def fetch_kc_results_robust(need: int = 20):
    """
    着せかえクーちゃんの過去データを「宝くじネット」から取得
    """
    url = "https://www.takarakujinet.co.jp/kisekae/"

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")

        items = []
        rows = soup.find_all("tr")

        for tr in rows:
            text = tr.get_text()
            if "回号" in text and "等級" in text:
                continue

            m_round = re.search(r"第?(\d+)回", text)
            if not m_round:
                continue

            round_no = int(m_round.group(1))
            m_date = re.search(r"(\d{4}[年/]\d{1,2}[月/]\d{1,2}日?)", text)
            date_str = m_date.group(1) if m_date else ""

            # 絵柄抽出 (画像alt または テキスト)
            imgs = tr.find_all("img")
            fruits = []
            for img in imgs:
                alt = img.get("alt", "")
                for k, v in FRUIT_TEXT_MAP.items():
                    if k in alt:
                        fruits.append(v)
                        break

            # 画像で取れない場合はテキスト判定
            if len(fruits) != 4:
                fruits = []
                row_text = tr.get_text(" ", strip=True)
                matches = re.findall(r"(リンゴ|ミカン|メロン|ブドウ|モモ|りんご|みかん|めろん|ぶどう|もも)", row_text)
                for m in matches:
                    if m in FRUIT_TEXT_MAP:
                        fruits.append(FRUIT_TEXT_MAP[m])
                fruits = fruits[:4]

            if len(fruits) != 4:
                continue

            result_str = "".join(fruits)

            # 払戻金抽出
            payout = {}
            row_text_clean = tr.get_text(" ", strip=True)
            m_p1 = re.search(r"1等\D*?([\d,]+)円", row_text_clean)
            m_p2 = re.search(r"2等\D*?([\d,]+)円", row_text_clean)
            m_p3 = re.search(r"3等\D*?([\d,]+)円", row_text_clean)

            if m_p1:
                payout["1等"] = {"yen": m_p1.group(1)}
            if m_p2:
                payout["2等"] = {"yen": m_p2.group(1)}
            if m_p3:
                payout["3等"] = {"yen": m_p3.group(1)}

            items.append({
                "round": round_no,
                "date": date_str,
                "num": result_str,
                "payout": payout
            })

            if len(items) >= need:
                break

        if not items:
            return fetch_kc_results_backup(need)

        return items, []

    except Exception as e:
        print(f"KC Fetch Error: {e}")
        return fetch_kc_results_backup(need)

# ------------------------------------------------------------
# Normalize Items
# ------------------------------------------------------------
def normalize_items(game: str, items: list[dict]) -> list[dict]:
    norm_items = []
    for d in items:
        d = dict(d)
        if game in ["N4", "N3"] and "num" in d:
            d["num"] = re.sub(r"\D", "", str(d["num"]))
        if "round" not in d:
            d["round"] = 0
        if "date" not in d:
            d["date"] = ""
        if "payout" not in d or not isinstance(d["payout"], dict):
            d["payout"] = {}
        norm_items.append(d)

    has_round_int = any(isinstance(x.get("round"), int) for x in norm_items)
    if not has_round_int and norm_items:
        preds_by_round = status["games"].get(game, {}).get("preds_by_round", {})
        existing = [int(k) for k in preds_by_round.keys() if str(k).isdigit()]
        base_round = max(existing) if existing else 0
        if base_round <= 0:
            base_round = len(norm_items)
        for idx, d in enumerate(norm_items):
            d["round"] = base_round - idx

    for idx, d in enumerate(norm_items):
        if not isinstance(d.get("round"), int):
            d["round"] = int(idx)

    norm_items.sort(key=lambda x: x.get("round", 0), reverse=True)
    return norm_items

# ------------------------------------------------------------
# Ensure Predictions for round
# ------------------------------------------------------------
def ensure_predictions_for_round(game: str, round_no: int, base_last: str, base_trends: dict, base_pred_func) -> list[str]:
    preds_by_round = status["games"][game]["preds_by_round"]
    key = str(round_no)

    # KCはN4の写像で動的生成する（予想固定資産は持たない）
    if game == "KC":
        return base_pred_func(base_last, base_trends)

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

    save_status(status)
    return preds

# ------------------------------------------------------------
# Build Pages Logic
# ------------------------------------------------------------
def build_pages_for_game(game: str, items: list[dict], months_used: list[str]) -> dict:
    norm_items = normalize_items(game, items)

    if not norm_items:
        dummy_num = "0000" if game != "KC" else "🍎🍎🍎🍎"
        norm_items = [{"round": 0, "date": "", "num": dummy_num, "payout": {}}]

    latest = norm_items[0]
    next_round = latest["round"] + 1

    trends = {}
    if game in ["N4", "N3"]:
        cols = ["n1", "n2", "n3", "n4"] if game == "N4" else ["n1", "n2", "n3"]
        history_nums = [[int(c) for c in it["num"]] for it in norm_items]
        trends = calc_trends_from_history(history_nums, cols)

    def pred_func_wrapper(last_val, tr):
        if game == "KC":
            return kc_random_10()
        raw = generate_predictions(game, last_val, tr)
        return distill_predictions(game, raw, out_n=10)

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

    for idx, it in enumerate(norm_items):
        rno = it["round"]
        if game in ["N4", "N3"]:
            cols = ["n1", "n2", "n3", "n4"] if game == "N4" else ["n1", "n2", "n3"]
            sub_hist = norm_items[idx:]
            history_nums = [[int(c) for c in x["num"]] for x in sub_hist]
            tr = calc_trends_from_history(history_nums, cols)
            prev = sub_hist[1] if len(sub_hist) > 1 else None
            seed_last = prev["num"] if prev else it["num"]

            preds = ensure_predictions_for_round(game, rno, seed_last, tr, pred_func_wrapper)
        else:
            preds = ensure_predictions_for_round(game, rno, "", {}, pred_func_wrapper)

        pages.append({
            "mode": "RESULT",
            "round": rno,
            "date": it.get("date", ""),
            "result": it.get("num", ""),
            "payout": it.get("payout", {}),
            "preds": preds,
            "months_used": months_used
        })

    return {"pages": pages}

# ------------------------------------------------------------
# Fetch & Build
# ------------------------------------------------------------
n4_items, n4_used = fetch_last_n_results("N4", need=20)
n3_items, n3_used = fetch_last_n_results("N3", need=20)
kc_items, kc_used = fetch_kc_results_robust(need=20)

n4_bundle = build_pages_for_game("N4", n4_items, n4_used)
n3_bundle = build_pages_for_game("N3", n3_items, n3_used)
kc_bundle = build_pages_for_game("KC", kc_items, [])

# ------------------------------------------------------------
# KC preds are derived from N4 preds (same windmill)  ※STRはおまけ
# ------------------------------------------------------------
def _norm_date(s: str) -> str:
    if not s:
        return ""
    ds = re.sub(r"[^0-9]", "", s)
    if len(ds) >= 8:
        return ds[:8]
    return ds

_n4_date_to_preds = {}
_n4_fallback_preds = None
for _p in n4_bundle.get("pages", []):
    if _p.get("mode") == "RESULT" and _p.get("preds"):
        dkey = _norm_date(_p.get("date", ""))
        if dkey and dkey not in _n4_date_to_preds:
            _n4_date_to_preds[dkey] = _p["preds"]
        if _n4_fallback_preds is None:
            _n4_fallback_preds = _p["preds"]

_n4_now_preds = None
for _p in n4_bundle.get("pages", []):
    if _p.get("mode") == "NOW" and _p.get("preds"):
        _n4_now_preds = _p["preds"]
        break

for _kp in kc_bundle.get("pages", []):
    if _kp.get("mode") == "NOW":
        src = _n4_now_preds or _n4_fallback_preds or _kp.get("preds", [])
    else:
        src = _n4_date_to_preds.get(_norm_date(_kp.get("date", "")), None) or _n4_fallback_preds or _kp.get("preds", [])
    _kp["preds"] = kc_from_n4_preds(src) if src else _kp.get("preds", [])

# ------------------------------------------------------------
# NM (Mini) from N3 (last 2 digits)
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# Build JS Data
# ------------------------------------------------------------
data_for_js = {
    "N4": n4_bundle["pages"],
    "N3": n3_bundle["pages"],
    "NM": nm_pages,
    "KC": kc_bundle["pages"]
}

# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.2rem; padding-bottom: 1.2rem; max-width: 760px; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("MIRU-PAD")

# ----- HTML/JS UI (LCD) -----
html_code = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial;
    margin: 0; padding: 0;
    background: transparent;
  }}
  .wrap {{
    width: 100%;
    max-width: 740px;
    margin: 0 auto;
  }}
  .topbar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }}
  .btn {{
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid #444;
    background: #111;
    color: #fff;
    font-weight: 700;
    cursor: pointer;
    user-select: none;
    text-align: center;
    flex: 1;
  }}
  .btn:active {{ transform: scale(0.98); }}
  .lcd {{
    border-radius: 16px;
    padding: 14px;
    background: #0b0f0b;
    border: 2px solid #1b2a1b;
    color: #d7ffd7;
  }}
  .title {{
    text-align: center;
    font-weight: 800;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
  }}
  .grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }}
  .panel {{
    border: 1px solid #203b20;
    border-radius: 12px;
    padding: 10px;
    background: #050805;
  }}
  .panel h3 {{
    margin: 0 0 6px 0;
    font-size: 14px;
    opacity: 0.9;
  }}
  .big {{
    font-size: 26px;
    font-weight: 900;
    letter-spacing: 2px;
    text-align: center;
    margin: 10px 0 6px 0;
  }}
  .payout {{
    font-size: 12px;
    line-height: 1.4;
    white-space: pre;
  }}
  .pred {{
    font-size: 18px;
    font-weight: 800;
    letter-spacing: 1px;
    margin: 6px 0;
  }}
  .pred .hit {{ color: #ff4b4b; }}
  .pred .pos {{ color: #5aa9ff; }}
  .legend {{
    font-size: 12px;
    opacity: 0.85;
    margin-top: 8px;
  }}
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div class="btn" onclick="navBack()">BACK</div>
    <div class="btn" onclick="navNow()">NOW</div>
    <div class="btn" onclick="navNext()">NEXT</div>
  </div>

  <div class="lcd">
    <div class="title" id="hdr">--</div>
    <div class="grid">
      <div class="panel">
        <h3>当せん番号</h3>
        <div class="big" id="res">----</div>
        <div class="payout" id="pay">--</div>
      </div>
      <div class="panel">
        <h3>予想（10本）</h3>
        <div id="preds"></div>
        <div class="legend">赤=一致（位置不問） / 青=位置一致（STR）</div>
      </div>
    </div>
  </div>
</div>

<script>
  const DATA = {json.dumps(data_for_js, ensure_ascii=False)};

  let curG = "N4";
  let cursor = {{"N4":0,"N3":0,"NM":0,"KC":0}};

  function pickPage(game, idx) {{
    const pages = DATA[game] || [];
    if (pages.length === 0) return null;
    const i = Math.max(0, Math.min(idx, pages.length-1));
    return pages[i];
  }}

  function getHitMarkup(pred, result) {{
    if (!result) return pred;
    // BOX hit: digits (or fruits) contained in result
    let out = "";
    const res = String(result);
    const used = {{}};
    for (let i=0;i<pred.length;i++) {{
      const ch = pred[i];
      // count occurrences in result
      let cntRes = (res.match(new RegExp(ch, 'g'))||[]).length;
      let cntUsed = used[ch]||0;
      if (cntUsed < cntRes) {{
        out += '<span class="hit">'+ch+'</span>';
        used[ch] = cntUsed + 1;
      }} else {{
        out += ch;
      }}
    }}
    // STR (pos) highlight separately
    let out2 = "";
    for (let i=0;i<out.length;i++) {{
      out2 += out[i];
    }}
    return out;
  }}

  function getPosMarkup(pred, result) {{
    if (!result) return pred;
    let out = "";
    for (let i=0;i<pred.length;i++) {{
      const ch = pred[i];
      if (String(result).length === pred.length && String(result)[i] === ch) {{
        out += '<span class="pos">'+ch+'</span>';
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
    document.getElementById("res").innerText = result ? ("  " + result) : "----";

    const pay = page.payout || {{}};
    let payTxt = "";
    if (curG === "NM") {{
      if (pay["ミニ"] && pay["ミニ"].yen) {{
        payTxt += "ミニ　　　 " + pay["ミニ"].yen + "円\\n";
      }}
    }} else {{
      const keys = Object.keys(pay);
      keys.forEach(k => {{
        const v = pay[k];
        if (v && v.yen) {{
          payTxt += (k + "　" + v.yen + "円\\n");
        }}
      }});
    }}
    document.getElementById("pay").innerText = payTxt || "--";

    const preds = page.preds || [];
    const boxWrap = (s) => getHitMarkup(s, result);
    const posWrap = (s) => getPosMarkup(s, result);

    let html = "";
    preds.forEach(p => {{
      const s = String(p);
      const box = boxWrap(s);
      const pos = posWrap(s);
      html += '<div class="pred">' + box + '</div>';
    }});
    document.getElementById("preds").innerHTML = html;
  }}

  function navBack() {{
    cursor[curG] = Math.min((DATA[curG]||[]).length-1, cursor[curG] + 1);
    render();
  }}
  function navNext() {{
    cursor[curG] = Math.max((cursor[curG]||0)-1,0);
    render();
  }}
  function navNow() {{
    cursor[curG] = 0;
    render();
  }}

  render();
</script>
</body>
</html>
"""

components.html(html_code, height=610, scrolling=False)
