import streamlit as st
import random
import requests
import json
import os
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from collections import Counter

# =========================================================
# MIRU-PAD (Spec Updated) - No iframe / Native Streamlit UI
# =========================================================

APP_TITLE = "MIRU-PAD"
STATUS_FILE = "miru_status.json"

# --- ページ設定 ---
st.set_page_config(page_title=APP_TITLE, layout="centered")

# --- 【厳守】風車盤ロジック定数 ---
WINDMILL_MAP = {
    "n1": [0, 7, 4, 1, 8, 5, 2, 9, 6, 3],  # 千の位
    "n2": [0, 9, 8, 7, 6, 5, 4, 3, 2, 1],  # 百の位
    "n3": [0, 3, 6, 9, 2, 5, 8, 1, 4, 7],  # 十の位
    "n4": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],  # 一の位
}
INDEX_MAP = {k: {num: i for i, num in enumerate(arr)} for k, arr in WINDMILL_MAP.items()}

GRAVITY_SECTORS = [4, 5, 6]
ANTI_GRAVITY_SECTORS = [9, 0, 1]

# --- JST日付キー（22時切替） ---
def get_target_date_key() -> str:
    JST = timezone(timedelta(hours=9), "JST")
    now = datetime.now(JST)
    target_date = now + timedelta(days=1) if now.hour >= 22 else now
    return target_date.strftime("%Y-%m-%d")

# --- JSON 永続化（破損修復あり） ---
def default_status() -> dict:
    return {
        "date_key": "",
        "count": 2,
        "game": "N4",
        "N4": {"last": "----", "preds": ["----"] * 10},
        "N3": {"last": "----", "preds": ["---"] * 10},
        "NM": {"last": "--", "preds": ["--"] * 10},
        "KC": {"last": "----", "preds": ["🍎🍊🍈🍇"] * 10},  # placeholder
        "updated_at": "",
    }

def load_status() -> dict:
    if not os.path.exists(STATUS_FILE):
        return default_status()
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 自動修復（キー欠損を埋める）
        base = default_status()
        def deep_merge(dst, src):
            for k, v in src.items():
                if isinstance(v, dict) and isinstance(dst.get(k), dict):
                    deep_merge(dst[k], v)
                else:
                    dst[k] = v
        deep_merge(base, data)
        return base
    except Exception:
        # 壊れてるなら修復（デフォルトで上書き）
        return default_status()

def save_status(data: dict) -> None:
    data["updated_at"] = datetime.now(timezone(timedelta(hours=9), "JST")).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        # 書けない場合でもアプリは落とさない
        pass

# --- みずほ公式から履歴取得（最新〜過去20回） ---
def fetch_history(game_type: str, max_rows: int = 20):
    if game_type == "N4":
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html"
        cols = ["n1", "n2", "n3", "n4"]
        digits = 4
    else:
        url = "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers3/index.html"
        cols = ["n1", "n2", "n3"]
        digits = 3

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    }

    history = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        # みずほは Shift_JIS が多いが揺れるので、まず apparent_encoding を尊重
        if res.encoding is None or res.encoding.lower() == "iso-8859-1":
            res.encoding = res.apparent_encoding or "Shift_JIS"

        soup = BeautifulSoup(res.text, "html.parser")

        # 仕様書：td/th の class alnCenter を全部拾い、桁数一致だけ抽出
        cells = soup.find_all(["td", "th"], class_="alnCenter")
        candidates = []
        for c in cells:
            val = c.get_text(strip=True).replace(" ", "")
            if val.isdigit() and len(val) == digits:
                candidates.append(val)

        # candidates はページ内に色々混ざる可能性があるので、
        # 出現順（上から）を尊重して最新→過去として扱う
        for v in candidates:
            history.append([int(d) for d in v])
            if len(history) >= max_rows:
                break

        if not history:
            raise RuntimeError("No history parsed")

    except Exception:
        # 取得失敗時のフォールバック（落とさない）
        history = [[8, 2, 9, 6], [1, 3, 5, 7]] if game_type == "N4" else [[3, 5, 8], [9, 1, 0]]

    last_val_str = "".join(map(str, history[0]))

    # --- トレンド（最頻スピン量） ---
    trends = {}
    for i, col in enumerate(cols):
        spins = []
        for j in range(len(history) - 1):
            curr_idx = INDEX_MAP[col][history[j][i]]
            prev_idx = INDEX_MAP[col][history[j + 1][i]]
            spins.append((curr_idx - prev_idx) % 10)
        trends[col] = Counter(spins).most_common(1)[0][0] if spins else 0

    return last_val_str, trends, history

# --- 重力エンジン（最終インデックス補正） ---
def apply_gravity_final(idx: int, role: str) -> int:
    if role == "chaos":
        return random.randint(0, 9)

    # Ace=引力、Shift=反発（仕様書のイメージに合わせる）
    sectors = GRAVITY_SECTORS if role == "ace" else ANTI_GRAVITY_SECTORS

    candidates = [{"idx": idx, "score": 1.0}]
    for s in (-1, 1, 0):
        n_idx = (idx + s) % 10
        if n_idx in sectors:
            candidates.append({"idx": n_idx, "score": 1.5})

    candidates.sort(key=lambda x: x["score"], reverse=True)
    # 70%で“強い方”、30%で“弱い方”＝ちょい揺らぎ
    return candidates[0]["idx"] if random.random() < 0.7 else candidates[-1]["idx"]

# --- 予測生成（10口） ---
def generate_predictions(game_type: str, last_val: str, trends: dict) -> list[str]:
    cols = ["n1", "n2", "n3", "n4"] if game_type == "N4" else ["n1", "n2", "n3"]
    last_nums = [int(d) for d in last_val]

    # 役割分担（仕様書）
    roles = ["ace", "shift", "chaos", "ace", "shift", "ace", "shift", "ace", "shift", "chaos"]

    preds = []
    seen = set()

    for role in roles:
        chosen = None
        for attempt in range(30):
            row = ""
            for i, col in enumerate(cols):
                curr_idx = INDEX_MAP[col][last_nums[i]]
                base_spin = trends[col]

                # attemptが進むほど“揺れ”を少し足す（同一回避）
                jitter = 0
                if attempt > 0:
                    jitter = random.choice([1, -1, 2, -2, 5])

                if role == "chaos":
                    spin = random.randint(0, 9)
                elif role == "shift":
                    spin = (base_spin + random.choice([1, -1, 5])) % 10
                else:
                    spin = base_spin if random.random() > 0.2 else (base_spin + 1) % 10

                spin = (spin + jitter) % 10
                final_idx = apply_gravity_final((curr_idx + spin) % 10, role)
                row += str(WINDMILL_MAP[col][final_idx])

            if row not in seen:
                chosen = row
                break

        if chosen is None:
            chosen = row  # 最悪でも何か入れる
        seen.add(chosen)
        preds.append(chosen)

    return preds

# --- mini（Numbers3の下2桁）をユニーク化 ---
def generate_unique_mini(n3_preds: list[str], n3_last_val: str, n3_trends: dict) -> list[str]:
    mini_preds = []
    seen = set()

    cols = ["n2", "n3"]
    last_nums = [int(d) for d in n3_last_val[-2:]]
    roles = ["ace", "shift", "chaos", "ace", "shift", "ace", "shift", "ace", "shift", "chaos"]

    for i, n3v in enumerate(n3_preds):
        cand = n3v[-2:]
        role = roles[i]

        if cand in seen:
            # 被ったら作り直す
            for attempt in range(30):
                row = ""
                for j, col in enumerate(cols):
                    curr_idx = INDEX_MAP[col][last_nums[j]]
                    base_spin = n3_trends[col]
                    jitter = random.choice([1, -1, 2, -2, 5]) + attempt

                    if role == "chaos":
                        spin = random.randint(0, 9)
                    elif role == "shift":
                        spin = (base_spin + random.choice([1, -1, 5])) % 10
                    else:
                        spin = base_spin if random.random() > 0.2 else (base_spin + 1) % 10

                    spin = (spin + jitter) % 10
                    final_idx = apply_gravity_final((curr_idx + spin) % 10, role)
                    row += str(WINDMILL_MAP[col][final_idx])

                if row not in seen:
                    cand = row
                    break

        seen.add(cand)
        mini_preds.append(cand)

    return mini_preds

# --- KC（着せ替クーちゃん）プレースホルダー（仕様書通り：スクレイプしない） ---
def generate_kc_predictions() -> list[str]:
    fruits = ["🍎", "🍊", "🍈", "🍇", "🍑"]
    out = []
    for _ in range(10):
        out.append("".join(random.choice(fruits) for _ in range(4)))
    return out

# ---------------------------
# 初期化＆日付キー切替
# ---------------------------
status = load_status()
target_key = get_target_date_key()

# 日付キーが変わったら再計算（固定化）
if status.get("date_key") != target_key or status["N4"]["last"] in ("----", "", None):
    n4_last, n4_trends, _ = fetch_history("N4", 20)
    n3_last, n3_trends, _ = fetch_history("N3", 20)

    n4_preds = generate_predictions("N4", n4_last, n4_trends)
    n3_preds = generate_predictions("N3", n3_last, n3_trends)
    nm_preds = generate_unique_mini(n3_preds, n3_last, n3_trends)

    status["date_key"] = target_key
    status["N4"]["last"] = n4_last
    status["N4"]["preds"] = n4_preds

    status["N3"]["last"] = n3_last
    status["N3"]["preds"] = n3_preds

    status["NM"]["last"] = n3_last[-2:]
    status["NM"]["preds"] = nm_preds

    status["KC"]["last"] = "----"
    status["KC"]["preds"] = generate_kc_predictions()

    save_status(status)

# ---------------------------
# Session State（UI状態）
# ---------------------------
if "game" not in st.session_state:
    st.session_state.game = status.get("game", "N4")
if "count" not in st.session_state:
    st.session_state.count = int(status.get("count", 2))

def persist_ui_state():
    status["game"] = st.session_state.game
    status["count"] = st.session_state.count
    save_status(status)

# ---------------------------
# CSS（モバイル2列固定＆LCD再現）
# ---------------------------
st.markdown(
    """
<style>
/* ページ背景を黒っぽく */
.stApp { background: #000; }

/* モバイルで2列縦崩れを防止（仕様書B） */
@media (max-width: 640px) {
  div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; }
  div[data-testid="column"] { min-width: 0 !important; width: 50% !important; }
}

/* LCD */
.miru-lcd {
  background-color: #9ea7a6;
  color: #000;
  border: 4px solid #555;
  border-radius: 12px;
  height: 170px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
  position: relative;
  margin-bottom: 10px;
}
.miru-lcd-label {
  font-size: 10px;
  color: #444;
  font-weight: bold;
  position: absolute;
  top: 8px;
  width: 100%;
  text-align: center;
}
.miru-preds {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px 20px;
  width: 90%;
  margin-top: 25px;
}
.miru-num {
  font-family: "Courier New", monospace;
  font-weight: bold;
  letter-spacing: 2px;
  line-height: 1.1;
  font-size: 24px;
  text-align: center;
  width: 100%;
}
.miru-locked {
  font-size: 14px;
  color: #555;
  letter-spacing: 1px;
  text-align: center;
  width: 100%;
}

/* コントロールバー風 */
.miru-bar {
  background: #222;
  border-radius: 30px;
  padding: 10px 14px;
  margin: 8px 0 12px 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.miru-bar-title {
  color: #fff;
  font-weight: 800;
  font-size: 16px;
}

/* Streamlit button ざっくりPAD風（全部同系で寄せる） */
div.stButton > button {
  height: 42px !important;
  border-radius: 12px !important;
  font-weight: 800 !important;
  border: 2px solid rgba(255,255,255,0.15) !important;
  box-shadow: 0 3px #000 !important;
}

/* +/- を丸っぽく */
.miru-round div.stButton > button {
  width: 42px !important;
  height: 42px !important;
  border-radius: 999px !important;
}

/* CALC白 */
.miru-calc div.stButton > button {
  background: #fff !important;
  color: #000 !important;
}

/* PAD系（デフォは緑寄せ） */
.miru-pad div.stButton > button {
  background: #009688 !important;
  color: #fff !important;
}

/* ピンク寄せ（LOTO側の雰囲気） */
.miru-loto div.stButton > button {
  background: #E91E63 !important;
  color: #fff !important;
}

/* ミニオレンジ */
.miru-mini div.stButton > button {
  background: #FF9800 !important;
  color: #fff !important;
}

/* 黄色（着替クー風） */
.miru-kc div.stButton > button {
  background: #FFEB3B !important;
  color: #333 !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------
# 表示データ
# ---------------------------
data_map = {
    "N4": status["N4"]["preds"],
    "N3": status["N3"]["preds"],
    "NM": status["NM"]["preds"],
    "KC": status["KC"]["preds"],
}
last_map = {
    "N4": status["N4"]["last"],
    "N3": status["N3"]["last"],
    "NM": status["NM"]["last"],
    "KC": status["KC"]["last"],
}

# ---------------------------
# LCD 描画
# ---------------------------
curG = st.session_state.game
curC = st.session_state.count

preds = data_map.get(curG, ["----"] * 10)
lastv = last_map.get(curG, "----")

lcd_items = []
for i in range(curC):
    v = preds[i] if i < len(preds) else "----"
    cls = "miru-locked" if ("COMING SOON" in str(v) or v in ("----", "---", "--")) else "miru-num"
    lcd_items.append(f'<div class="{cls}">{v}</div>')

st.markdown(
    f"""
<div class="miru-lcd">
  <div class="miru-lcd-label">LAST RESULT ({curG}): {lastv}</div>
  <div class="miru-preds">
    {''.join(lcd_items)}
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------
# コントロールバー（+- と CALC）
# ---------------------------
c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
with c1:
    st.markdown('<div class="miru-round">', unsafe_allow_html=True)
    if st.button("－", key="minus"):
        st.session_state.count = max(1, st.session_state.count - 1)
        persist_ui_state()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with c2:
    st.markdown(f'<div class="miru-bar"><div class="miru-bar-title">{st.session_state.count} 口</div></div>', unsafe_allow_html=True)

with c3:
    st.markdown('<div class="miru-calc">', unsafe_allow_html=True)
    if st.button("CALC", key="calc"):
        # 同日内の再計算（固定化は崩さない＝同じdate_keyでも再計算したい場合）
        # → 仕様書にないが便利なので、押したら“今日キー”のまま再生成して保存する
        n4_last, n4_trends, _ = fetch_history("N4", 20)
        n3_last, n3_trends, _ = fetch_history("N3", 20)

        status["N4"]["last"] = n4_last
        status["N4"]["preds"] = generate_predictions("N4", n4_last, n4_trends)

        status["N3"]["last"] = n3_last
        status["N3"]["preds"] = generate_predictions("N3", n3_last, n3_trends)

        status["NM"]["last"] = n3_last[-2:]
        status["NM"]["preds"] = generate_unique_mini(status["N3"]["preds"], n3_last, n3_trends)

        status["KC"]["preds"] = generate_kc_predictions()
        save_status(status)
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with c4:
    st.markdown('<div class="miru-round">', unsafe_allow_html=True)
    if st.button("＋", key="plus"):
        st.session_state.count = min(10, st.session_state.count + 1)
        persist_ui_state()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------
# PAD（2列グリッド）
# ---------------------------
st.markdown('<div class="miru-pad">', unsafe_allow_html=True)

r1a, r1b = st.columns(2)
with r1a:
    st.markdown('<div class="miru-loto">', unsafe_allow_html=True)
    st.button("LOTO 7", disabled=True)
    st.markdown("</div>", unsafe_allow_html=True)
with r1b:
    if st.button("Numbers 4", key="btnN4"):
        st.session_state.game = "N4"
        persist_ui_state()
        st.rerun()

r2a, r2b = st.columns(2)
with r2a:
    st.markdown('<div class="miru-loto">', unsafe_allow_html=True)
    st.button("LOTO 6", disabled=True)
    st.markdown("</div>", unsafe_allow_html=True)
with r2b:
    if st.button("Numbers 3", key="btnN3"):
        st.session_state.game = "N3"
        persist_ui_state()
        st.rerun()

r3a, r3b = st.columns(2)
with r3a:
    st.markdown('<div class="miru-loto">', unsafe_allow_html=True)
    st.button("MINI LOTO", disabled=True)
    st.markdown("</div>", unsafe_allow_html=True)
with r3b:
    st.markdown('<div class="miru-mini">', unsafe_allow_html=True)
    if st.button("Numbers mini", key="btnNM"):
        st.session_state.game = "NM"
        persist_ui_state()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

r4a, r4b = st.columns(2)
with r4a:
    st.markdown('<div class="miru-loto">', unsafe_allow_html=True)
    st.button("BINGO 5", disabled=True)
    st.markdown("</div>", unsafe_allow_html=True)
with r4b:
    st.markdown('<div class="miru-kc">', unsafe_allow_html=True)
    if st.button("着替クー", key="btnKC"):
        st.session_state.game = "KC"
        persist_ui_state()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
