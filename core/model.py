import random
import itertools
from collections import Counter
import os
import json
from datetime import datetime

from core.config import INDEX_MAP, WINDMILL_MAP, GRAVITY_SECTORS, ANTI_GRAVITY_SECTORS, PRED_FILE, JST, safe_save_json
from core.shuffle import shuffle_recompose

# ============================================================
# VERSION（ここだけ変えると “アップデートで全部変わる”）
# ============================================================
VERSION = "v2026-01-22a"

KC_FRUIT_MAP = {
    "0": "🍎", "1": "🍊", "2": "🍈", "3": "🍇", "4": "🍑",
    "5": "🍎", "6": "🍊", "7": "🍈", "8": "🍇", "9": "🍑"
}

# =========================
# Prediction Store（今回は使っても使わなくてもOK）
# =========================
def default_pred_store():
    return {
        "games": {
            "N4": {"preds_by_round": {}, "history_limit": 120},
            "N3": {"preds_by_round": {}, "history_limit": 120},
            "NM": {"preds_by_round": {}, "history_limit": 120},
            "KC": {"preds_by_round": {}, "history_limit": 120}
        },
        "updated_at": ""
    }

def load_pred_store():
    if os.path.exists(PRED_FILE):
        try:
            with open(PRED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "games" in data:
                base = default_pred_store()
                for g in base["games"]:
                    if g not in data["games"]:
                        data["games"][g] = base["games"][g]
                if "updated_at" not in data:
                    data["updated_at"] = ""
                return data
        except Exception:
            pass
    return default_pred_store()

def save_pred_store(store: dict) -> bool:
    store = dict(store)
    store["updated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    return bool(safe_save_json(store, PRED_FILE))

# =========================
# Trends / Gravity
# =========================
def calc_trends_from_history(nums: list[list[int]], cols: list[str]) -> dict:
    trends = {}
    if not nums or len(nums) < 2:
        for c in cols:
            trends[c] = 0
        return trends

    for i, c in enumerate(cols):
        idxs = [INDEX_MAP[c][row[i]] for row in nums]
        spins = []
        for j in range(len(idxs) - 1):
            a = idxs[j]
            b = idxs[j + 1]
            diff = (a - b) % 10
            if diff > 5:
                diff -= 10
            spins.append(diff)
        trends[c] = Counter(spins).most_common(1)[0][0] if spins else 0
    return trends

def _get_sectors(obj, col: str):
    if isinstance(obj, dict):
        return obj.get(col, []) or []
    if isinstance(obj, (list, tuple, set)):
        return list(obj)
    return []

def apply_gravity_final(col: str, idx: int, role: str, rng: random.Random) -> int:
    """
    重要：グローバル random を使わず rng を使う（再起動固定のため）
    """
    if role == "ace":
        sectors = _get_sectors(GRAVITY_SECTORS, col)
        if sectors:
            if idx in sectors:
                return idx
            if rng.random() < 0.7:
                return rng.choice(sectors)
    elif role == "shift":
        sectors = _get_sectors(ANTI_GRAVITY_SECTORS, col)
        if sectors:
            if idx in sectors:
                return idx
            if rng.random() < 0.7:
                return rng.choice(sectors)
    return idx

# =========================
# Raw generator helpers
# =========================
def _matrix_crossover(raw_preds: list[str]) -> list[str]:
    """
    旧：圧縮が強すぎて素材が潰れることがあったため、
    現運用では generate_predictions() からは呼ばない（残しておくだけ）。
    """
    if not raw_preds:
        return []

    digits = len(raw_preds[0])
    pos_counts = [Counter() for _ in range(digits)]
    global_count = Counter()

    for s in raw_preds:
        for i, ch in enumerate(s):
            pos_counts[i][ch] += 1
            global_count[ch] += 1

    pos_top = []
    for i in range(digits):
        top5 = [d for d, _ in pos_counts[i].most_common(5)]
        pos_top.append(top5)

    global_top = [d for d, _ in global_count.most_common(3)]

    cand_by_pos = []
    for i in range(digits):
        cand = list(dict.fromkeys(pos_top[i] + global_top))
        cand_by_pos.append(cand)

    scored = []
    for c in itertools.product(*cand_by_pos):
        s = "".join(c)
        score_pos = 0
        score_box = 0
        for i, ch in enumerate(c):
            score_pos += pos_counts[i].get(ch, 0)
            score_box += global_count.get(ch, 0)
        scored.append((score_pos + score_box * 1.2, s))

    scored.sort(key=lambda x: x[0], reverse=True)

    out = []
    used = set()
    for _, s in scored:
        if s not in used:
            used.add(s)
            out.append(s)
        if len(out) >= 10:
            break

    if len(out) < 10:
        for s in raw_preds:
            if s not in used:
                used.add(s)
                out.append(s)
            if len(out) >= 10:
                break

    return out[:10]

def _stable_seed(game: str, last_val: str, trends: dict) -> int:
    """
    再起動固定用の seed
    - VERSION を変えればアップデートで全予想が変わる
    - last_val/trends が同じなら再起動しても同じ
    """
    # trends は順序が安定するように key で並べる
    t_items = sorted((str(k), str(v)) for k, v in (trends or {}).items())
    s = VERSION + "|" + game + "|" + str(last_val) + "|" + str(t_items)
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h

def generate_predictions(game: str, last_val: str, trends: dict) -> list[str]:
    """
    - raw_preds をそのまま10本返す（惜しい世界線維持）
    - 乱数は rng=Random(seed) に固定（再起動で変わらない）
    """
    digits = 4 if game == "N4" else 3
    cols = ["n1", "n2", "n3", "n4"] if digits == 4 else ["n1", "n2", "n3"]

    # 決定論乱数
    rng = random.Random(_stable_seed(game, last_val, trends))

    last = [int(x) for x in str(last_val) if str(x).isdigit()]
    if len(last) != digits:
        last = [rng.randint(0, 9) for _ in range(digits)]

    roles = ["ace", "ace", "ace", "shift", "shift", "chaos", "chaos", "ace", "shift", "ace", "chaos", "shift"]
    raw_preds = []

    for attempt, role in enumerate(roles):
        out_digits = []
        for i, col in enumerate(cols):
            curr_digit = last[i]
            curr_idx = INDEX_MAP[col][curr_digit]
            base_spin = int(trends.get(col, 0)) if isinstance(trends, dict) else 0

            jitter = 0
            if attempt >= 6:
                jitter = rng.choice([-2, -1, 0, 1, 2])

            spin = base_spin
            if role == "chaos":
                spin = rng.randint(-5, 5)
            elif role == "shift":
                spin = base_spin + rng.choice([-1, 1, 5, -5])
            else:
                if rng.random() < 0.25:
                    spin = base_spin + rng.choice([-1, 1])

            next_idx = (curr_idx + spin + jitter) % 10
            next_idx = apply_gravity_final(col, next_idx, role, rng)
            out_digits.append(WINDMILL_MAP[col][next_idx])

        raw_preds.append("".join(str(x) for x in out_digits))

    # ここが「惜しい世界線」に戻した核心：圧縮しない
    return raw_preds[:10]

# =========================
# Distill（BOX特化：素材10本をそのまま確定→シャッフル）
# =========================
def distill_predictions(game: str, raw_preds: list[str], out_n: int = 10) -> list[str]:
    if not raw_preds:
        digits = 4 if game == "N4" else 3
        return ["0" * digits] * out_n

    digits = 4 if game == "N4" else 3 if game == "N3" else None
    if digits is None:
        out = raw_preds[:out_n]
        while len(out) < out_n:
            out.append(raw_preds[-1])
        return out

    # sanitize + keep material
    material = []
    for s in raw_preds:
        s = "".join(ch for ch in str(s) if ch.isdigit())
        if len(s) == digits:
            material.append(s)

    if not material:
        return ["0" * digits] * out_n

    out = material[:out_n]
    while len(out) < out_n:
        out.append(out[-1])

    # ★配置だけ変える（BOX特化）
    out = shuffle_recompose(game, out)

    return out[:out_n]

# =========================
# KC mapping
# =========================
def kc_from_n4_preds(n4_preds: list[str]) -> list[str]:
    fruit_preds = []
    for s in n4_preds or []:
        row = ""
        for ch in str(s):
            row += KC_FRUIT_MAP.get(ch, "🍎")
        fruit_preds.append(row)
    while len(fruit_preds) < 10:
        fruit_preds.append(fruit_preds[-1] if fruit_preds else "🍎🍎🍎🍎")
    return fruit_preds[:10]
