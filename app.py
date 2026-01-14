import streamlit as st
import random
import requests
import json
import os
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from collections import Counter
import streamlit.components.v1 as components

# =========================
# MIRU-PAD (UI=Perfect HTML / Core=Spec Updated + 20:00 LATEST RULE + FIXED SCRAPE)
# =========================

st.set_page_config(page_title="MIRU-PAD", layout="centered")

STATUS_FILE = "miru_status.json"

# --- 【厳守】風車盤ロジック定数 ---
WINDMILL_MAP = {
    'n1': [0, 7, 4, 1, 8, 5, 2, 9, 6, 3],  # 千の位
    'n2': [0, 9, 8, 7, 6, 5, 4, 3, 2, 1],  # 百の位
    'n3': [0, 3, 6, 9, 2, 5, 8, 1, 4, 7],  # 十の位
    'n4': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]   # 一の位
}
INDEX_MAP = {k: {num: i for i, num in enumerate(arr)} for k, arr in WINDMILL_MAP.items()}

GRAVITY_SECTORS = [4, 5, 6]
ANTI_GRAVITY_SECTORS = [9, 0, 1]

# --- JST基準（22時で切替） ---
def get_target_date_key():
    JST = timezone(timedelta(hours=9), 'JST')
    now = datetime.now(JST)
    target_date = now + timedelta(days=1) if now.hour >= 22 else now
    return target_date.strftime('%Y-%m-%d')

def now_jst_str():
    JST = timezone(timedelta(hours=9), 'JST')
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")

def is_after_20():
    JST = timezone(timedelta(hours=9), 'JST')
    now = datetime.now(JST)
    return now.hour >= 20

# --- JSON 永続化（破損修復あり） ---
def default_status():
    return {
        "date_key": "",
        "fetched_at": "",  # Active世代を作った時間

        # Active（LCDが使う世代）
        "N4_R": "----",
        "N3_R": "---",
        "N4_INFO": "",
        "N3_INFO": "",

        "N4_P": ["----"]*10,
        "N3_P": ["---"]*10,
        "NM_P": ["--"]*10,
        "KC_P": ["🍎🍊🍈🍇"]*10,

        # Latest（答え合わせ用：20:00以降に自動更新）
        "N4_LATEST_R": "----",
        "N3_LATEST_R": "---",
        "N4_LATEST_INFO": "",
        "N3_LATEST_INFO": "",
        "LATEST_AT": ""
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
        return data
    except Exception:
        return default_status()

def save_status(s):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# =========================================================
# 【重要】最新がズレる原因を潰す：alnCenter総当たりをやめる
# みずほのブロック（回別/抽せん日/抽せん数字）からだけ抜く
# =========================================================
def _get_table_text(td_or_th):
    return td_or_th.get_text(" ", strip=True).replace("\u3000", " ").replace("\xa0", " ")

def _find_value_in_same_table(soup, key_text):
    # key_text を含むセルを探し、同じ行の「値セル（次のtd）」を返す
    for cell in soup.find_all(["th", "td"]):
        t = _get_table_text(cell)
        if key_text in t:
            row = cell.find_parent("tr")
            if not row:
                continue
            tds = row.find_all("td")
            if not tds:
                continue
            # thが先頭、tdが後続の想定で「最後のtd」を値として採用
            return _get_table_text(tds[-1])
    return None

def _parse_blocks_numbers(soup, digits, max_rows):
    """
    ページ内の「抽せん数字」行を上から順に拾って history を作る。
    同時に先頭（最新）の回別/日付も取る。
    """
    history = []
    first_info = {"round": "", "date": ""}

    # 「抽せん数字」行を上から順に探す
    # 1ブロックは(回別/抽せん日/抽せん数字)のセットなので、
    # 「抽せん数字」が出るたびに、その周辺ブロックから情報を拾う
    for cell in soup.find_all(["th", "td"]):
        t = _get_table_text(cell)
        if "抽せん数字" not in t and "抽選数字" not in t:
            continue

        row = cell.find_parent("tr")
        if not row:
            continue

        # 同じ行の値（数字）を取得
        tds = row.find_all("td")
        if not tds:
            continue
        num = _get_table_text(tds[-1]).replace(" ", "")
        if not (num.isdigit() and len(num) == digits):
            continue

        history.append([int(d) for d in num])

        # 先頭だけ info を拾う（同じテーブル内で回別/抽せん日を探す）
        if len(history) == 1:
            table = row.find_parent("table")
            if table:
                # 回別：例「第6896回」
                r = _find_value_in_same_table(table, "回別")
                # 抽せん日：例「2026年1月13日」
                d = _find_value_in_same_table(table, "抽せん日") or _find_value_in_same_table(table, "抽選日")
                first_info["round"] = r or ""
                first_info["date"] = d or ""

        if len(history) >= max_rows:
            break

    return history, first_info

def fetch_history(game_type, max_rows=20):
    if game_type == 'N4':
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        cols = ['n1', 'n2', 'n3', 'n4']
        digits = 4
    else:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers3/index.html"
        cols = ['n1', 'n2', 'n3']
        digits = 3

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.encoding is None or res.encoding.lower() == "iso-8859-1":
            res.encoding = res.apparent_encoding or "Shift_JIS"
        soup = BeautifulSoup(res.text, 'html.parser')

        history, info = _parse_blocks_numbers(soup, digits, max_rows)
        if not history:
            raise RuntimeError("history empty")

        last_val = "".join(map(str, history[0]))

        # 表示用info（第xxxx回 / yyyy年m月d日）
        round_txt = info.get("round", "")
        date_txt = info.get("date", "")
        info_str = ""
        if round_txt or date_txt:
            # 例：第6896回 2026年1月13日
            info_str = f"{round_txt} {date_txt}".strip()

    except Exception:
        # フォールバック（落とさない）
        history = [[8,2,9,6], [1,3,5,7]] if game_type == 'N4' else [[3,5,8], [9,1,0]]
        last_val = "".join(map(str, history[0]))
        info_str = ""

    # --- トレンド（最頻スピン量） ---
    trends = {}
    for i, col in enumerate(cols):
        spins = []
        for j in range(len(history) - 1):
            curr_idx = INDEX_MAP[col][history[j][i]]
            prev_idx = INDEX_MAP[col][history[j+1][i]]
            spins.append((curr_idx - prev_idx) % 10)
        trends[col] = Counter(spins).most_common(1)[0][0] if spins else 0

    return last_val, info_str, trends, history

# --- 重力エンジン ---
def apply_gravity_final(idx, role):
    if role == 'chaos':
        return random.randint(0, 9)
    sectors = GRAVITY_SECTORS if role == 'ace' else ANTI_GRAVITY_SECTORS
    candidates = [{'idx': idx, 'score': 1.0}]
    for s in (-1, 1, 0):
        n_idx = (idx + s) % 10
        if n_idx in sectors:
            candidates.append({'idx': n_idx, 'score': 1.5})
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[0]['idx'] if random.random() < 0.7 else candidates[-1]['idx']

# --- 予測（10口・役割分担） ---
def generate_predictions(game_type, last_val, trends):
    cols = ['n1', 'n2', 'n3', 'n4'] if game_type == 'N4' else ['n1', 'n2', 'n3']
    last_nums = [int(d) for d in last_val]
    roles = ['ace', 'shift', 'chaos', 'ace', 'shift', 'ace', 'shift', 'ace', 'shift', 'chaos']
    preds = []
    seen_full = set()
    for role in roles:
        chosen = None
        for attempt in range(30):
            row = ""
            for i, col in enumerate(cols):
                curr_idx = INDEX_MAP[col][last_nums[i]]
                base_spin = trends[col]
                jitter = 0
                if attempt > 0:
                    jitter = random.choice([1, -1, 2, -2, 5])
                if role == 'chaos':
                    spin = random.randint(0, 9)
                elif role == 'shift':
                    spin = (base_spin + random.choice([1, -1, 5])) % 10
                else:
                    spin = base_spin if random.random() > 0.2 else (base_spin + 1) % 10
                spin = (spin + jitter) % 10
                final_idx = apply_gravity_final((curr_idx + spin) % 10, role)
                row += str(WINDMILL_MAP[col][final_idx])
            if row not in seen_full:
                chosen = row
                break
        if chosen is None:
            chosen = row
        seen_full.add(chosen)
        preds.append(chosen)
    return preds

def generate_unique_mini(n3_preds, n3_last_val, n3_trends):
    mini_preds = []
    seen_mini = set()
    cols = ['n2', 'n3']
    last_nums = [int(d) for d in n3_last_val[-2:]]
    roles = ['ace', 'shift', 'chaos', 'ace', 'shift', 'ace', 'shift', 'ace', 'shift', 'chaos']
    for i, n3_val in enumerate(n3_preds):
        candidate = n3_val[-2:]
        role = roles[i]
        if candidate in seen_mini:
            for attempt in range(30):
                new_row = ""
                for j, col in enumerate(cols):
                    curr_idx = INDEX_MAP[col][last_nums[j]]
                    base_spin = n3_trends[col]
                    jitter = random.choice([1, -1, 2, -2, 5]) + attempt
                    if role == 'chaos':
                        spin = random.randint(0, 9)
                    elif role == 'shift':
                        spin = (base_spin + random.choice([1, -1, 5])) % 10
                    else:
                        spin = base_spin if random.random() > 0.2 else (base_spin + 1) % 10
                    spin = (spin + jitter) % 10
                    final_idx = apply_gravity_final((curr_idx + spin) % 10, role)
                    new_row += str(WINDMILL_MAP[col][final_idx])
                if new_row not in seen_mini:
                    candidate = new_row
                    break
        seen_mini.add(candidate)
        mini_preds.append(candidate)
    return mini_preds

def generate_kc_predictions():
    fruits = ["🍎", "🍊", "🍈", "🍇", "🍑"]
    return ["".join(random.choice(fruits) for _ in range(4)) for _ in range(10)]

# --- クエリ（CALCだけで世代交代） ---
q = st.query_params
force_calc = str(q.get("calc", "0")) == "1"

status = load_status()
target_key = get_target_date_key()

# -----------------------------
# 20:00以降：最新結果だけ更新（LCDは更新しない）
# -----------------------------
if is_after_20():
    n4_latest, n4_latest_info, _, _ = fetch_history('N4', 20)
    n3_latest, n3_latest_info, _, _ = fetch_history('N3', 20)

    changed = False
    if n4_latest and n4_latest != status.get("N4_LATEST_R", "----"):
        status["N4_LATEST_R"] = n4_latest
        status["N4_LATEST_INFO"] = n4_latest_info
        changed = True
    if n3_latest and n3_latest != status.get("N3_LATEST_R", "---"):
        status["N3_LATEST_R"] = n3_latest
        status["N3_LATEST_INFO"] = n3_latest_info
        changed = True

    if changed:
        status["LATEST_AT"] = now_jst_str()
        save_status(status)

# -----------------------------
# CALC：ユーザーが納得したらここで世代交代（LCDを最新へ）
# -----------------------------
if force_calc:
    # 最新（latest）を確実に取得
    n4_latest, n4_latest_info, n4_t, _ = fetch_history('N4', 20)
    n3_latest, n3_latest_info, n3_t, _ = fetch_history('N3', 20)

    status["N4_LATEST_R"] = n4_latest
    status["N3_LATEST_R"] = n3_latest
    status["N4_LATEST_INFO"] = n4_latest_info
    status["N3_LATEST_INFO"] = n3_latest_info
    status["LATEST_AT"] = now_jst_str()

    # 世代交代：Active LASTをlatestへ
    status["N4_R"] = n4_latest
    status["N3_R"] = n3_latest
    status["N4_INFO"] = n4_latest_info
    status["N3_INFO"] = n3_latest_info

    # 予想再計算（ここだけ変わる）
    n4_p = generate_predictions('N4', status["N4_R"], n4_t)
    n3_p = generate_predictions('N3', status["N3_R"], n3_t)
    nm_p = generate_unique_mini(n3_p, status["N3_R"], n3_t)

    status["date_key"] = target_key
    status["fetched_at"] = now_jst_str()
    status["N4_P"] = n4_p
    status["N3_P"] = n3_p
    status["NM_P"] = nm_p
    status["KC_P"] = generate_kc_predictions()

    save_status(status)
    st.query_params.clear()
    st.rerun()

# -----------------------------
# 日次初回のみ：予想世代を作る（コロコロ変わらない）
# -----------------------------
need_refresh = (
    status.get("date_key") != target_key
    or status.get("N4_R", "----") in ("----", "", None)
)

if need_refresh:
    n4_l, n4_info, n4_t, _ = fetch_history('N4', 20)
    n3_l, n3_info, n3_t, _ = fetch_history('N3', 20)

    status["date_key"] = target_key
    status["fetched_at"] = now_jst_str()
    status["N4_R"] = n4_l
    status["N3_R"] = n3_l
    status["N4_INFO"] = n4_info
    status["N3_INFO"] = n3_info

    status["N4_P"] = generate_predictions('N4', n4_l, n4_t)
    status["N3_P"] = generate_predictions('N3', n3_l, n3_t)
    status["NM_P"] = generate_unique_mini(status["N3_P"], n3_l, n3_t)
    status["KC_P"] = generate_kc_predictions()

    save_status(status)

# -----------------------------
# LAST RESULT 表示：20:00以降は latest（番号+回別+日付）を表示
# -----------------------------
def make_label(num, info):
    if not num:
        return "----"
    if info:
        return f"{num} | {info}"
    return num

# 20:00前：Activeを表示
n4_label = make_label(status.get("N4_R", "----"), status.get("N4_INFO", ""))
n3_label = make_label(status.get("N3_R", "---"), status.get("N3_INFO", ""))

# 20:00以降：Latestを表示（LCDはまだActiveのまま）
if is_after_20():
    n4_label = make_label(status.get("N4_LATEST_R", status.get("N4_R", "----")), status.get("N4_LATEST_INFO", ""))
    n3_label = make_label(status.get("N3_LATEST_R", status.get("N3_R", "---")), status.get("N3_LATEST_INFO", ""))

# --- UI用データ（JSへ） ---
d_map = {
    'N4': status['N4_P'],
    'N3': status['N3_P'],
    'NM': status['NM_P'],
    'KC': status['KC_P'],
    'L7': ["COMING SOON"]*10,
    'L6': ["COMING SOON"]*10,
    'ML': ["COMING SOON"]*10,
    'B5': ["COMING SOON"]*10
}

l_map = {
    'N4': n4_label,
    'N3': n3_label,
    'NM': (n3_label[-2:] if len(n3_label) >= 2 else "--"),
    'KC': "----",
    'L7': "----", 'L6': "----", 'ML': "----", 'B5': "----"
}

d_json = json.dumps(d_map, ensure_ascii=False)
l_json = json.dumps(l_map, ensure_ascii=False)

# --- レイアウトは絶対に変えない（ここから下はUI固定） ---
html_code = f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<style>
    body {{
        background-color: #000; color: #fff; font-family: sans-serif;
        margin: 0; padding: 4px; overflow: hidden;
        user-select: none; touch-action: manipulation;
    }}
    .lcd {{
        background-color: #9ea7a6; color: #000; border: 4px solid #555; border-radius: 12px;
        height: 170px; display: flex; flex-direction: column; justify-content: center; align-items: center;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.5); position: relative;
    }}
    .lcd-label {{
        font-size: 10px; color: #444; font-weight: bold; position: absolute; top: 8px;
        width:100%; text-align:center;
    }}
    .preds-container {{
        display: grid; grid-template-columns: 1fr 1fr; gap: 2px 20px; width: 90%; margin-top: 15px;
    }}
    .num-text {{
        font-family: 'Courier New', monospace; font-weight: bold; letter-spacing: 2px; line-height: 1.1;
        font-size: 24px; text-align: center; width:100%;
    }}
    .locked {{
        font-size: 14px; color: #555; letter-spacing: 1px; text-align: center; width:100%;
    }}
    .count-bar {{
        display: flex; justify-content: space-between; align-items: center;
        background: #222; padding: 0 15px; border-radius: 30px;
        margin: 8px 0; height: 45px;
        gap: 10px;
    }}
    .btn-round {{
        width: 38px; height: 38px; border-radius: 50%;
        background: #444; color: white; display: flex; justify-content: center; align-items: center;
        font-size: 24px; font-weight: bold; border: 2px solid #666; cursor: pointer;
    }}
    .btn-calc {{
        height: 38px; border-radius: 18px; background: #fff; color: #000;
        padding: 0 18px; display:flex; align-items:center; justify-content:center;
        font-weight: 900; cursor:pointer;
        border: 2px solid rgba(0,0,0,0.3);
    }}
    .pad-grid {{
        display: grid; grid-template-columns: 1fr 1fr; gap: 6px;
    }}
    .btn {{
        height: 42px; border-radius: 12px; color: white; font-weight: bold; font-size: 12px;
        display: flex; justify-content: center; align-items: center;
        border: 2px solid rgba(0,0,0,0.3); box-shadow: 0 3px #000; cursor: pointer;
        opacity: 0.55;
    }}
    .btn.active {{
        opacity: 1.0;
        filter: brightness(1.12);
        border: 2px solid #fff !important;
        box-shadow: 0 0 15px rgba(255,255,255,0.35);
        transform: translateY(2px);
    }}
    .btn-loto {{ background: #E91E63; }}
    .btn-num  {{ background: #009688; }}
    .btn-mini {{ background: #FF9800; }}
    .btn-b5   {{ background: #2196F3; }}
    .btn-kc   {{ background: #FFEB3B; color: #333; }}
</style>
</head>
<body>
<div class="lcd">
    <div id="game-label" class="lcd-label">LAST RESULT</div>
    <div id="preds-box" class="preds-container"></div>
</div>

<div class="count-bar">
    <div class="btn-round" onclick="changeCount(-1)">－</div>
    <div id="count-label" style="font-size:18px; font-weight:bold;">2 口</div>
    <div class="btn-round" onclick="changeCount(1)">＋</div>
    <div class="btn-calc" onclick="doCalc()">CALC</div>
</div>

<div class="pad-grid">
    <div id="btn-L7" class="btn btn-loto" onclick="setG('L7')">LOTO 7</div>
    <div id="btn-N4" class="btn btn-num" onclick="setG('N4')">Numbers 4</div>

    <div id="btn-L6" class="btn btn-loto" onclick="setG('L6')">LOTO 6</div>
    <div id="btn-N3" class="btn btn-num" onclick="setG('N3')">Numbers 3</div>

    <div id="btn-ML" class="btn btn-loto" onclick="setG('ML')">MINI LOTO</div>
    <div id="btn-NM" class="btn btn-mini" onclick="setG('NM')">Numbers mini</div>

    <div id="btn-B5" class="btn btn-b5" onclick="setG('B5')">BINGO 5</div>
    <div id="btn-KC" class="btn btn-kc" onclick="setG('KC')">着替クー</div>
</div>

<script>
    const d = {d_json};
    const l = {l_json};

    let curG = 'N4';
    let curC = 2;

    function update() {{
        document.getElementById('count-label').innerText = curC + ' 口';
        const last = (l[curG] !== undefined) ? l[curG] : '----';
        document.getElementById('game-label').innerText = 'LAST RESULT ('+curG+'): ' + last;

        document.querySelectorAll('.btn').forEach(b=>b.classList.remove('active'));
        const active = document.getElementById('btn-'+curG);
        if(active) active.classList.add('active');

        let h = '';
        for(let i=0; i<curC; i++) {{
            let v = (d[curG] && d[curG][i] !== undefined) ? d[curG][i] : '----';
            let c = (v === 'COMING SOON') ? 'locked' : 'num-text';
            h += `<div class="${{c}}">${{v}}</div>`;
        }}
        document.getElementById('preds-box').innerHTML = h;
    }}

    function changeCount(v) {{
        curC = Math.max(1, Math.min(10, curC+v));
        update();
    }}

    function setG(g) {{
        curG = g;
        update();
    }}

    function doCalc() {{
        try {{
            const p = window.top.location.pathname;
            window.top.location.href = p + '?calc=1';
        }} catch(e) {{
            window.location.reload();
        }}
    }}

    update();
</script>
</body>
</html>
"""

components.html(html_code, height=580, scrolling=False)
