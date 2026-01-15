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

from core.config import STATUS_FILE, JST, HEADERS, WINDMILL_MAP, INDEX_MAP, GRAVITY_SECTORS, ANTI_GRAVITY_SECTORS
from core.fetch import get_month_urls, parse_month_page, fetch_last_n_results
from core.model import calc_trends_from_history, apply_gravity_final, generate_predictions, generate_unique_mini, kc_random_10, load_pred_store, save_pred_store, ensure_predictions_for_round_store

# =========================
# MIRU-PAD (RAKUTEN ONLY / AUTO / BACK-NEXT-NOW)
# =========================

st.set_page_config(page_title="MIRU-PAD", layout="centered")

# ensure data/ exists (for data/miru_preds.json)
os.makedirs("data", exist_ok=True)

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
        # shallow merge
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
pred_store = load_pred_store()

# ------------------------------------------------------------
# Build "pages" for JS: NOW + history pages (latest -> older)
# ------------------------------------------------------------
def ensure_predictions_for_round(game: str, round_no: int, base_last: str, base_trends: dict, base_pred_func) -> list[str]:
    """
    Persist preds_by_round so that when we go BACK, we show what was predicted for that round.
    If missing, generate and store (first-run backfill).
    """
    limit = int(status["games"][game].get("history_limit", 120))
    def _gen():
        return base_pred_func(base_last, base_trends)
    return ensure_predictions_for_round_store(pred_store, game, round_no, _gen, limit)

def build_pages_for_game(game: str, items: list[dict], months_used: list[int]) -> dict:
    """
    items: last N results, sorted desc
    Returns dict with:
      pages: [NOW_page, RESULT_page1, RESULT_page2...]
    """
    latest = items[0]
    latest_round = latest["round"]
    next_round = latest_round + 1

    # compute trends from last 20
    if game == "N4":
        cols = ["n1", "n2", "n3", "n4"]
    else:
        cols = ["n1", "n2", "n3"]

    history_nums = [[int(c) for c in it["num"]] for it in items]
    trends = calc_trends_from_history(history_nums, cols)

    # NOW preds: for next_round, seed = latest result
    def pred_func_last(last_val: str, tr: dict):
        return generate_predictions(game, last_val, tr)

    now_preds = ensure_predictions_for_round(game, next_round, latest["num"], trends, pred_func_last)

    # NOW page
    pages = [{
        "mode": "NOW",
        "round": next_round,
        "date": "",
        "result": "",
        "payout": {},
        "preds": now_preds,
        "months_used": months_used
    }]

    # history pages (BACK): for each result round, show preds that were made for that round
    # seed for those preds was "previous round result" (round-1). We can approximate by using
    # the correct seed from fetched items if available.
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

# numbers mini from N3: NOW round = N3 next round, history rounds = N3 history rounds
# preds/result = last2 digits
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

# KC random (fixed after first generation)
kc_preds = ensure_predictions_for_round_store(pred_store, "KC", 0, kc_random_10, 120)

# Save updates
save_status(status)
save_pred_store(pred_store)

# ------------------------------------------------------------
# Prepare data for JS (NO layout change: use existing design)
# ------------------------------------------------------------
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
# UI (keep original look; internal layout only)
# ------------------------------------------------------------
html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <style>
        body {{ background-color: #000; color: #fff; font-family: sans-serif; margin: 0; padding: 4px; overflow: hidden; user-select: none; touch-action: manipulation; }}
        .lcd {{ background-color: #9ea7a6; color: #000; border: 4px solid #555; border-radius: 12px; height: 190px; display: flex; flex-direction: column; justify-content: center; align-items: stretch; box-shadow: inset 0 0 10px rgba(0,0,0,0.5); position: relative; }}
        .lcd-label {{ font-size: 10px; color: #444; font-weight: bold; position: absolute; top: 8px; left: 10px; width:auto; text-align:left; }}
        .lcd-content {{ display:flex; flex-direction:row; width:100%; height:100%; padding-top: 22px; box-sizing:border-box; }}
        .result-panel {{ width:50%; padding: 6px 6px 6px 10px; box-sizing:border-box; display:flex; flex-direction:column; justify-content:flex-start; }}
        .pred-panel {{ width:50%; padding: 6px 10px 6px 6px; box-sizing:border-box; }}
        .result-line {{ font-size: 11px; font-weight: 700; line-height: 1.15; }}
        .result-small {{ font-size: 10px; font-weight: 700; line-height: 1.15; }}
        .result-green {{ color: #1DB954; font-weight: 900; }}
        .preds-grid {{ display:grid; grid-template-columns: 1fr 1fr; column-gap: 12px; row-gap: 2px; width:100%; }}
        .num-text {{ font-family: 'Courier New', monospace; font-weight: bold; letter-spacing: 2px; line-height: 1.05; font-size: 20px; text-align: left; width:100%; }}
        .red {{ color: #ff3b30; }}
        .blue {{ color: #007aff; }}
        .locked {{ font-size: 14px; color: #555; letter-spacing: 1px; text-align: center; width:100%; }}
        .count-bar {{ display: flex; justify-content: space-between; align-items: center; background: #222; padding: 0 12px; border-radius: 30px; margin: 8px 0; height: 45px; gap: 8px; }}
        .btn-round {{ width: 38px; height: 38px; border-radius: 50%; background: #444; color: white; display: flex; justify-content: center; align-items: center; font-size: 24px; font-weight: bold; border: 2px solid #666; cursor: pointer; }}
        .btn-nav {{ height: 36px; border-radius: 18px; background: #fff; color: #000; padding: 0 10px; display:flex; align-items:center; justify-content:center; font-weight: 900; cursor:pointer; border: 2px solid rgba(0,0,0,0.3); font-size: 12px; }}
        .pad-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
        .btn {{ height: 42px; border-radius: 12px; color: white; font-weight: bold; font-size: 12px; display: flex; justify-content: center; align-items: center; border: 2px solid rgba(0,0,0,0.3); box-shadow: 0 3px #000; cursor: pointer; opacity: 0.55; }}
        .btn.active {{ opacity: 1.0; filter: brightness(1.12); border: 2px solid #fff !important; box-shadow: 0 0 15px rgba(255,255,255,0.35); transform: translateY(2px); }}
        .btn-loto {{ background: #E91E63; }}
        .btn-num  {{ background: #009688; }}
        .btn-mini {{ background: #FF9800; }}
        .btn-b5   {{ background: #2196F3; }}
        .btn-kc   {{ background: #FFEB3B; color: #333; }}
    </style>
</head>
<body>
    <div class="lcd">
        <div id="game-label" class="lcd-label"></div>
        <div class="lcd-content">
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

        // UI state
        let curG = 'N4';
        let curC = 10;   // show 10 by default
        // page cursor per game: 0=NOW, 1=latest result, 2=older...
        const cursor = {{'N4':0,'N3':0,'NM':0,'KC':0,'L7':0,'L6':0,'ML':0,'B5':0}};

        function escHtml(s){{
            return String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
        }}

        function payoutLines(payout){{
            const lines = [];
            if(!payout) return lines;
            if(payout.STR && payout.STR.yen) lines.push(["STR", payout.STR.yen]);
            if(payout.BOX && payout.BOX.yen) lines.push(["BOX", payout.BOX.yen]);
            if(payout["SET-S"] && payout["SET-S"].yen) lines.push(["S-S", payout["SET-S"].yen]);
            if(payout["SET-B"] && payout["SET-B"].yen) lines.push(["S-B", payout["SET-B"].yen]);
            if(payout.MINI && payout.MINI.yen) lines.push(["Mini", payout.MINI.yen]);
            return lines;
        }}

        // STR=red (position match), BOX=blue (value match, remaining counts)
        function renderMarkedDigitsSB(pred, result){{
            const res = String(result || "");
            const pr  = String(pred || "");
            const counts = {{}};
            for(const ch of res) counts[ch] = (counts[ch]||0)+1;

            const isRed = Array(pr.length).fill(false);
            const isBlue = Array(pr.length).fill(false);

            for(let i=0; i<Math.min(pr.length, res.length); i++) {{
                if(pr[i] === res[i] && counts[pr[i]] > 0) {{
                    isRed[i] = true;
                    counts[pr[i]]--;
                }}
            }}

            for(let i=0; i<pr.length; i++) {{
                if(isRed[i]) continue;
                const ch = pr[i];
                if(counts[ch] && counts[ch] > 0) {{
                    isBlue[i] = true;
                    counts[ch]--;
                }}
            }}

            let out = "";
            for(let i=0; i<pr.length; i++) {{
                const ch = pr[i];
                if(isRed[i]) {{
                    out += '<span class="red">' + escHtml(ch) + '</span>';
                }} else if(isBlue[i]) {{
                    out += '<span class="blue">' + escHtml(ch) + '</span>';
                }} else {{
                    out += escHtml(ch);
                }}
            }}
            return out;
        }}

        function setActiveBtn() {{
            document.querySelectorAll('.btn').forEach(b=>b.classList.remove('active'));
            const active = document.getElementById('btn-'+curG);
            if(active) active.classList.add('active');
        }}

        function currentPage(){{
            const arr = pagesByGame[curG] || [];
            const idx = Math.max(0, Math.min(arr.length-1, cursor[curG]||0));
            return arr[idx] || null;
        }}

        function renderResultPanel(page){{
            if(!page) return "";
            if(curG === 'L7' || curG === 'L6' || curG === 'ML' || curG === 'B5') {{
                return `<div class="result-line">COMING SOON</div>`;
            }}

            const rno = page.round || 0;
            const dt  = page.date || "";
            const res = page.result || "";
            const pay = page.payout || {{}};

            let h = '';
            h += `<div class="result-line">[RESULT] 第${{escHtml(rno)}}回</div>`;
            if(dt) h += `<div class="result-small">日付: ${{escHtml(dt)}}</div>`;
            h += `<div class="result-small">&nbsp;</div>`;

            if(res) {{
                if(curG === 'NM') {{
                    h += `<div class="result-line">当選: <span class="result-green">${{escHtml(res)}}</span></div>`;
                    // Mini payout: prefer payout.MINI.yen, else fallback STR.yen
                    let miniYen = "";
                    if(pay.MINI && pay.MINI.yen) miniYen = pay.MINI.yen;
                    else if(pay.STR && pay.STR.yen) miniYen = pay.STR.yen;
                    if(miniYen) h += `<div class="result-line">Mini: ${{escHtml(miniYen)}}</div>`;
                }} else {{
                    h += `<div class="result-line">当選: <span class="result-green">${{escHtml(res)}}</span></div>`;
                    h += `<div class="result-small">&nbsp;</div>`;
                    const lines = payoutLines(pay);
                    for(const it of lines) {{
                        if(it[0] === "Mini") continue;
                        h += `<div class="result-line">${{escHtml(it[0])}} ${{escHtml(it[1])}}</div>`;
                    }}
                }}
            }} else {{
                h += `<div class="result-line">[RESULT]</div>`;
            }}

            return h;
        }}

        function renderPredPanel(page){{
            if(!page) return '';
            const preds = page.preds || [];
            const res = page.result || "";
            let h = '<div class="preds-grid">';
            for(let i=0; i<Math.min(curC, preds.length); i++) {{
                const v = preds[i];
                if(curG === 'L7' || curG === 'L6' || curG === 'ML' || curG === 'B5') {{
                    h += `<div class="locked">COMING SOON</div>`;
                    continue;
                }}

                if(page.mode === 'RESULT' && res && (curG === 'N4' || curG === 'N3' || curG === 'NM')) {{
                    h += `<div class="num-text">${{renderMarkedDigitsSB(v, res)}}</div>`;
                }} else {{
                    h += `<div class="num-text">${{escHtml(v)}}</div>`;
                }}
            }}
            h += '</div>';
            return h;
        }}

        function update() {{
            document.getElementById('count-label').innerText = String(curC);

            const page = currentPage();
            setActiveBtn();

            if(!page){{
                document.getElementById('game-label').innerText = '';
                document.getElementById('result-box').innerHTML = '';
                document.getElementById('preds-box').innerHTML = '';
                return;
            }}

            if(page.mode === 'NOW') {{
                document.getElementById('game-label').innerText = 'NOW ('+curG+')';
            }} else {{
                document.getElementById('game-label').innerText = 'BACK ('+curG+')';
            }}

            document.getElementById('result-box').innerHTML = renderResultPanel(page);
            document.getElementById('preds-box').innerHTML = renderPredPanel(page);
        }}

        function changeCount(v) {{
            curC = Math.max(1, Math.min(10, curC+v));
            update();
        }}

        function setG(g) {{
            curG = g;
            if(!pagesByGame[curG]) {{
                pagesByGame[curG] = [{{
                    mode:'NOW', round:0, date:'', result:'', payout:{{}}, preds: Array(10).fill('COMING SOON'), months_used:[]
                }}];
                cursor[curG] = 0;
            }}
            update();
        }}

        function navBack(){{
            const arr = pagesByGame[curG] || [];
            cursor[curG] = Math.min((cursor[curG]||0)+1, Math.max(0, arr.length-1));
            update();
        }}

        function navNext(){{
            cursor[curG] = Math.max((cursor[curG]||0)-1, 0);
            update();
        }}

        function navNow(){{
            cursor[curG] = 0;
            update();
        }}

        // boot
        update();
    </script>
</body>
</html>
"""

components.html(html_code, height=610, scrolling=False)
