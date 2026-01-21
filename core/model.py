import random
import itertools
from collections import Counter
import os
import json

from core.config import INDEX_MAP, WINDMILL_MAP, GRAVITY_SECTORS, ANTI_GRAVITY_SECTORS

KC_FRUIT_MAP = {
    "0": "🍎", "1": "🍊", "2": "🍈", "3": "🍇", "4": "🍑",
    "5": "🍎", "6": "🍊", "7": "🍈", "8": "🍇", "9": "🍑"
}

def calc_trends_from_history(nums: list[list[int]], cols: list[str]) -> dict:
    trends = {}
    if not nums or len(nums) < 2:
        for c in cols:
            trends[c] = 0
        return trends

    for i, c in enumerate(cols):
        idxs = []
        for row in nums:
            d = row[i]
            idxs.append(INDEX_MAP[c][d])

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
        cand = list(dict.fromkeys(pos_top[i] + global_top))
        cand_by_pos.append(cand)

    combos = itertools.product(*cand_by_pos)

    scored = []
    for c in combos:
        s = "".join(c)
        score_pos = 0
        score_box = 0
        for i, ch in enumerate(c):
            score_pos += pos_counts[i].get(ch, 0)
            score_box += global_count.get(ch, 0)
        score = score_pos + score_box * 1.2
        scored.append((score, s))

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

    for attempt in range(len(roles)):
        role = roles[attempt]
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

def distill_predictions(game: str, raw_preds: list[str], out_n: int = 10) -> list[str]:
    """二段蒸留（濃縮）
    追加制約（作戦会議）:
    - 4連（同一数字のみ）は禁止（N4/N3とも）
    - “似すぎ制限”: 既存口とのマルチセット共通数>=3の関係が2本を超える候補は除外
    """
    if not raw_preds:
        return []

    digits = 4 if game == "N4" else 3 if game == "N3" else None
    if digits is None:
        return raw_preds[:out_n]

    freq = Counter()
    pair = Counter()

    def _pairs_from_pred(s: str):
        ds = [ch for ch in s if ch.isdigit()]
        if len(ds) != digits:
            return [], []
        freq.update(ds)
        uniq = sorted(set(ds))
        ps = []
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                ps.append((uniq[i], uniq[j]))
        return ds, ps

    for s in raw_preds:
        _, ps = _pairs_from_pred(s)
        pair.update(ps)

    def _multiset_overlap(a: str, b: str) -> int:
        ca = Counter(a)
        cb = Counter(b)
        return sum(min(ca[k], cb.get(k, 0)) for k in ca.keys())

    def _is_all_same(s: str) -> bool:
        return len(set(s)) == 1

    def _too_similar(candidate: str, chosen: list[str]) -> bool:
        cnt = 0
        for ex in chosen:
            if _multiset_overlap(candidate, ex) >= 3:
                cnt += 1
                if cnt >= 2:
                    return True
        return False

    if not pair:
        top = [d for d, _ in freq.most_common(digits)]
        while len(top) < digits:
            top.append(str((int(top[-1]) + 1) % 10) if top else "0")
        base = "".join(top[:digits])
        outs = []
        drift = [0, 1, -1, 2, -2, 3, -3, 4, -4, 5]
        for k in range(out_n * 6):
            d = drift[k % len(drift)]
            cand = list(base)
            cand[-1] = str((int(cand[-1]) + d) % 10)
            c = "".join(cand)
            if _is_all_same(c):
                continue
            if _too_similar(c, outs):
                continue
            if c not in outs:
                outs.append(c)
            if len(outs) >= out_n:
                break
        return outs[:out_n]

    def pair_score(p):
        a, b = p
        return (pair[p], freq[a] + freq[b], -int(a) - int(b))

    pairs_sorted = sorted(pair.keys(), key=pair_score, reverse=True)

    pair_used = Counter()
    used_sets = set()
    outs: list[str] = []

    def attach_score(x: str, a: str, b: str) -> float:
        aa, bb = (a, x) if a < x else (x, a)
        cc, dd = (b, x) if b < x else (x, b)
        return pair.get((aa, bb), 0) + pair.get((cc, dd), 0) + 0.25 * freq.get(x, 0)

    drift = [0, 1, -1, 2, -2, 3, -3, 4, -4, 5]

    def build_one(core_pair: tuple[str, str]) -> str | None:
        a, b = core_pair
        base = [a, b]
        candidates = [str(i) for i in range(10) if str(i) not in base]
        candidates.sort(key=lambda x: (attach_score(x, a, b), freq.get(x, 0), -int(x)), reverse=True)

        need = digits - 2
        chosen = base + candidates[:need]

        rest = sorted(chosen[2:], key=lambda x: (freq.get(x, 0), -int(x)), reverse=True)
        seq = chosen[:2] + rest
        cand = "".join(seq[:digits])

        if _is_all_same(cand):
            return None
        if _too_similar(cand, outs):
            return None

        key = "".join(sorted(set(cand)))
        if key not in used_sets:
            return cand

        for d in drift:
            cc = list(cand)
            cc[-1] = str((int(cc[-1]) + d + 10) % 10)
            cand2 = "".join(cc)
            if _is_all_same(cand2):
                continue
            if _too_similar(cand2, outs):
                continue
            key2 = "".join(sorted(set(cand2)))
            if key2 not in used_sets:
                return cand2
        return None

    i = 0
    guard = 0
    while len(outs) < out_n and guard < 800:
        guard += 1
        core = pairs_sorted[i % len(pairs_sorted)]
        if pair_used[core] >= 2:
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

    if len(outs) < out_n:
        for s in raw_preds:
            if len(outs) >= out_n:
                break
            if len(s) != digits:
                continue
            if _is_all_same(s):
                continue
            if _too_similar(s, outs):
                continue
            if s not in outs:
                outs.append(s)

    return outs[:out_n]

def kc_from_n4_preds(n4_preds: list[str]) -> list[str]:
    fruit_preds = []
    for num_str in n4_preds:
        row = ""
        for digit in num_str:
            row += KC_FRUIT_MAP.get(digit, "🍎")
        fruit_preds.append(row)
    return fruit_preds

# ------------------------------------------------------------
# pred store
# ------------------------------------------------------------
PRED_FILE = "data/miru_preds.json"

def _ensure_pred_dir(path: str):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)

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

def save_pred_store(store):
    _ensure_pred_dir(PRED_FILE)
    store["updated_at"] = datetime.now().isoformat()
    with open(PRED_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
