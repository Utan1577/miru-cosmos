import random
from collections import Counter
import json
import os
from datetime import datetime

from core.config import INDEX_MAP, WINDMILL_MAP, GRAVITY_SECTORS, ANTI_GRAVITY_SECTORS, JST

# ------------------------------------------------------------
# Core logic
# ------------------------------------------------------------
def calc_trends_from_history(nums: list[list[int]], cols: list[str]) -> dict:
    trends = {}
    for i, col in enumerate(cols):
        spins = []
        for j in range(len(nums) - 1):
            curr_idx = INDEX_MAP[col][nums[j][i]]
            prev_idx = INDEX_MAP[col][nums[j + 1][i]]
            spins.append((curr_idx - prev_idx) % 10)
        trends[col] = Counter(spins).most_common(1)[0][0] if spins else 0
    return trends

def apply_gravity_final(idx: int, role: str) -> int:
    if role == "chaos":
        return random.randint(0, 9)

    sectors = GRAVITY_SECTORS if role == "ace" else ANTI_GRAVITY_SECTORS
    candidates = [{"idx": idx, "score": 1.0}]

    for s in (-1, 1, 0):
        n_idx = (idx + s) % 10
        if n_idx in sectors:
            candidates.append({"idx": n_idx, "score": 1.5})

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[0]["idx"] if random.random() < 0.7 else candidates[-1]["idx"]

def generate_predictions(game: str, last_val: str, trends: dict) -> list[str]:
    cols = ["n1", "n2", "n3", "n4"] if game == "N4" else ["n1", "n2", "n3"]
    last_nums = [int(d) for d in last_val]
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
            chosen = row
        seen.add(chosen)
        preds.append(chosen)

    return preds

def generate_unique_mini(n3_preds: list[str], n3_last_val: str, n3_trends: dict) -> list[str]:
    # numbers mini = last2 digits, with uniqueness enforcement
    mini_preds = []
    seen = set()
    cols = ["n2", "n3"]
    last_nums = [int(d) for d in n3_last_val[-2:]]
    roles = ["ace", "shift", "chaos", "ace", "shift", "ace", "shift", "ace", "shift", "chaos"]

    for i, n3v in enumerate(n3_preds):
        cand = n3v[-2:]
        role = roles[i]
        if cand in seen:
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

def kc_random_10() -> list[str]:
    fruits = ["🍎", "🍊", "🍈", "🍇", "🍑"]
    return ["".join(random.choice(fruits) for _ in range(4)) for _ in range(10)]

# ------------------------------------------------------------
# Prediction store (persist across updates)
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
            "KC": {"preds_by_round": {}, "history_limit": 120},
        },
        "updated_at": "",
    }

def load_pred_store(path: str = PRED_FILE):
    _ensure_pred_dir(path)
    if not os.path.exists(path):
        return default_pred_store()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        base = default_pred_store()

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

        if "updated_at" not in data:
            data["updated_at"] = ""
        return data
    except Exception:
        return default_pred_store()

def save_pred_store(store, path: str = PRED_FILE):
    _ensure_pred_dir(path)
    store["updated_at"] = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def ensure_predictions_for_round_store(store, game: str, round_no: int, gen_func, history_limit: int = 120) -> list[str]:
    preds_by_round = store["games"][game]["preds_by_round"]
    key = str(round_no)

    if key in preds_by_round and isinstance(preds_by_round[key], list) and len(preds_by_round[key]) > 0:
        return preds_by_round[key]

    preds = gen_func()
    preds_by_round[key] = preds

    limit = int(store["games"][game].get("history_limit", history_limit))
    if len(preds_by_round) > limit:
        ks = sorted((int(k) for k in preds_by_round.keys() if str(k).isdigit()), reverse=True)
        keep = set(str(k) for k in ks[:limit])
        for k in list(preds_by_round.keys()):
            if (k.isdigit() and k not in keep):
                preds_by_round.pop(k, None)

    return preds
