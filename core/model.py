import random
from collections import Counter

from core.config import INDEX_MAP, WINDMILL_MAP, GRAVITY_SECTORS, ANTI_GRAVITY_SECTORS

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
