import random
import itertools
from collections import Counter
import os
import json
from datetime import datetime

from core.config import INDEX_MAP, WINDMILL_MAP, GRAVITY_SECTORS, ANTI_GRAVITY_SECTORS, PRED_FILE, JST, safe_save_json

# =========================
# Prediction Store (miru_preds.json)
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
                return data
        except Exception:
            pass
    return default_pred_store()

def save_pred_store(store: dict) -> bool:
    store = dict(store)
    store["updated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    return bool(safe_save_json(store, PRED_FILE))

def get_saved_preds(store: dict, game: str, round_no: int):
    g = store.get("games", {}).get(game, {})
    pb = g.get("preds_by_round", {})
    v = pb.get(str(round_no))
    return v if isinstance(v, list) and v else None

def set_saved_preds(store: dict, game: str, round_no: int, preds: list[str]):
    g = store["games"].setdefault(game, {"preds_by_round": {}, "history_limit": 120})
    pb = g["preds_by_round"]
    pb[str(round_no)] = preds

    limit = int(g.get("history_limit", 120))
    keys = [int(k) for k in pb.keys() if str(k).isdigit()]
    keys.sort(reverse=True)
    keep = set(str(k) for k in keys[:limit])
    for k in list(pb.keys()):
        if k not in keep:
            pb.pop(k, None)

# =========================
# Windmill / Trends / Gravity
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

def apply_gravity_final(col: str, idx: int, role: str) -> int:
    if role == "ace":
        sectors = _get_sectors(GRAVITY_SECTORS, col)
        if sectors:
            if idx in sectors:
                return idx
            if random.random() < 0.7:
                return random.choice(sectors)
    elif role == "shift":
        sectors = _get_sectors(ANTI_GRAVITY_SECTORS, col)
        if sectors:
            if idx in sectors:
                return idx
            if random.random() < 0.7:
                return random.choice(sectors)
    return idx

# =========================
# Raw prediction generator
# =========================
def _matrix_crossover(raw_preds: list[str]) -> list[str]:
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
        cand_by_pos.append(list(dict.fromkeys(pos_top[i] + global_top)))

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

def generate_predictions(game: str, last_val: str, trends: dict) -> list[str]:
    digits = 4 if game == "N4" else 3
    cols = ["n1", "n2", "n3", "n4"] if digits == 4 else ["n1", "n2", "n3"]

    last = [int(x) for x in str(last_val)]
    if len(last) != digits:
        last = [random.randint(0, 9) for _ in range(digits)]

    roles = ["ace", "ace", "ace", "shift", "shift", "chaos", "chaos", "ace", "shift", "ace", "chaos", "shift"]
    raw_preds = []

    for attempt, role in enumerate(roles):
        out_digits = []
        for i, col in enumerate(cols):
            curr_digit = last[i]
            curr_idx = INDEX_MAP[col][curr_digit]
            base_spin = int(trends.get(col, 0))

            jitter = 0
            if attempt >= 6:
                jitter = random.choice([-2, -1, 0, 1, 2])

            spin = base_spin
            if role == "chaos":
                spin = random.randint(-5, 5)
            elif role == "shift":
                spin = base_spin + random.choice([-1, 1, 5, -5])
            else:
                if random.random() < 0.25:
                    spin = base_spin + random.choice([-1, 1])

            next_idx = (curr_idx + spin + jitter) % 10
            next_idx = apply_gravity_final(col, next_idx, role)
            out_digits.append(WINDMILL_MAP[col][next_idx])

        raw_preds.append("".join(str(x) for x in out_digits))

    return _matrix_crossover(raw_preds)

# =========================
# Distill (MUST return exactly out_n)
# =========================
def distill_predictions(game: str, raw_preds: list[str], out_n: int = 10) -> list[str]:
    """
    二段蒸留（濃縮）+ 似すぎ抑制
    重要：最終的に必ず out_n 本返す（count表示と画面のズレを根絶）
    """
    if not raw_preds:
        return ["----"] * out_n

    digits = 4 if game == "N4" else 3 if game == "N3" else None
    if digits is None:
        out = raw_preds[:out_n]
        while len(out) < out_n:
            out.append(raw_preds[-1])
        return out

    def multiset_overlap(a: str, b: str) -> int:
        ca = Counter(a)
        cb = Counter(b)
        return sum(min(ca[k], cb.get(k, 0)) for k in ca.keys())

    def is_all_same(s: str) -> bool:
        return len(set(s)) == 1

    def too_similar(candidate: str, chosen: list[str]) -> bool:
        cnt = 0
        for ex in chosen:
            if multiset_overlap(candidate, ex) >= 3:
                cnt += 1
                if cnt >= 2:
                    return True
        return False

    # build freq/pair
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

    # start output
    outs: list[str] = []
    used = set()

    # If pair exists, try pair-driven build first
    if pair:
        def pair_score(p):
            a, b = p
            return (pair[p], freq[a] + freq[b], -int(a) - int(b))

        pairs_sorted = sorted(pair.keys(), key=pair_score, reverse=True)
        pair_used = Counter()

        def attach_score(x: str, a: str, b: str) -> float:
            aa, bb = (a, x) if a < x else (x, a)
            cc, dd = (b, x) if b < x else (x, b)
            return pair.get((aa, bb), 0) + pair.get((cc, dd), 0) + 0.25 * freq.get(x, 0)

        def build_one(core_pair):
            a, b = core_pair
            base = [a, b]
            candidates = [str(i) for i in range(10) if str(i) not in base]
            candidates.sort(key=lambda x: (attach_score(x, a, b), freq.get(x, 0), -int(x)), reverse=True)
            need = digits - 2
            chosen = base + candidates[:need]
            rest = sorted(chosen[2:], key=lambda x: (freq.get(x, 0), -int(x)), reverse=True)
            seq = chosen[:2] + rest
            return "".join(seq[:digits])

        i = 0
        guard = 0
        while len(outs) < out_n and guard < 1200:
            guard += 1
            core = pairs_sorted[i % len(pairs_sorted)]
            i += 1
            if pair_used[core] >= 2:
                continue
            cand = build_one(core)
            if len(cand) != digits:
                continue
            if is_all_same(cand):
                continue
            if too_similar(cand, outs):
                continue
            key = "".join(sorted(set(cand)))
            if key in used:
                continue
            used.add(key)
            pair_used[core] += 1
            outs.append(cand)

    # Fill from raw_preds if still short
    for s in raw_preds:
        if len(outs) >= out_n:
            break
        s = str(s)
        if len(s) != digits:
            continue
        if is_all_same(s):
            continue
        if too_similar(s, outs):
            continue
        key = "".join(sorted(set(s)))
        if key in used:
            continue
        used.add(key)
        outs.append(s)

    # Deterministic drift fill (guarantee out_n)
    drift = [0, 1, -1, 2, -2, 3, -3, 4, -4, 5]
    base = outs[-1] if outs else (raw_preds[0] if len(str(raw_preds[0])) == digits else "0" * digits)
    k = 0
    while len(outs) < out_n and k < 5000:
        k += 1
        d = drift[k % len(drift)]
        cc = list(base)
        # drift last digit
        cc[-1] = str((int(cc[-1]) + d) % 10)
        cand = "".join(cc)
        if is_all_same(cand):
            continue
        if too_similar(cand, outs):
            continue
        key = "".join(sorted(set(cand)))
        if key in used:
            continue
        used.add(key)
        outs.append(cand)

    # Absolute last fallback (never shorter)
    while len(outs) < out_n:
        outs.append("0" * digits)

    return outs[:out_n]

# =========================
# KC mapping
# =========================
def kc_from_n4_preds(n4_preds: list[str]) -> list[str]:
    fruit_preds = []
    for num_str in n4_preds or []:
        s = str(num_str)
        row = ""
        for digit in s:
            row += KC_FRUIT_MAP.get(digit, "🍎")
        fruit_preds.append(row)
    # ensure exactly 10 for UI
    while len(fruit_preds) < 10:
        fruit_preds.append(fruit_preds[-1] if fruit_preds else "🍎🍎🍎🍎")
    return fruit_preds[:10]
