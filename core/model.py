import random
import itertools
from collections import Counter
import json
import os
from datetime import datetime
from core.config import INDEX_MAP, WINDMILL_MAP, GRAVITY_SECTORS, ANTI_GRAVITY_SECTORS, JST, safe_save_json
from core.backup import backup_preds_daily

# ------------------------------------------------------------
# Matrix Crossover Logic (The Aligner)
# ------------------------------------------------------------
def _matrix_crossover(raw_preds: list[str]) -> list[str]:
    """
    マトリックス・クロスオーバー:
    1. 生成された予測群（素材）全体をスキャンし、各桁の「強い数字」を特定。
    2. 縦の壁を取り払い、強い数字同士を強制的に横一列に結合（整列）させる。
    3. 「惜しい」を排除し、凝縮された最強の10行を返す。
    """
    if not raw_preds:
        return []

    # 1. スキャン (各桁の出現頻度を解析)
    width = len(raw_preds[0])
    counts = [Counter() for _ in range(width)]
    for p in raw_preds:
        for i, d in enumerate(p):
            counts[i][d] += 1

    # 2. 強制整列 (High Power Alignment)
    # 各桁で出現頻度の高い数字トップ4を抽出し、それらの組み合わせ(キメラ)を全生成
    top_digits = []
    for c in counts:
        # 頻度順にソートして上位4つを取得 (バリエーション確保のため)
        top = [d for d, freq in c.most_common(4)]
        if not top: # 万が一空なら0-9全候補
             top = [str(n) for n in range(10)]
        top_digits.append(top)

    # 全組み合わせを生成し、スコア付け (スコア = 構成数字の出現頻度合計)
    candidates = []
    for combo in itertools.product(*top_digits):
        s = "".join(combo)
        score = sum(counts[i][ch] for i, ch in enumerate(s))
        candidates.append((score, s))

    # スコアが高い順にソート (最強の整列順)
    candidates.sort(key=lambda x: x[0], reverse=True)

    # 3. 出力 (Top 10 Unique)
    final_preds = []
    seen = set()

    for score, s in candidates:
        if s not in seen:
            seen.add(s)
            final_preds.append(s)
        if len(final_preds) >= 10:
            break

    # 万が一10個に満たない場合の補填 (元の予測から補充)
    if len(final_preds) < 10:
        for p in raw_preds:
            if p not in seen:
                seen.add(p)
                final_preds.append(p)
            if len(final_preds) >= 10:
                break

    return final_preds

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
    """
    Windmill & Gravity で素材を生成し、
    Matrix Crossover で「当たり」を整列させて出力する。
    """
    cols = ["n1", "n2", "n3", "n4"] if game == "N4" else ["n1", "n2", "n3"]
    last_nums = [int(d) for d in last_val]
    # 素材を多めに生成 (15行) して、クロスオーバーの精度を高める
    roles = ["ace", "shift", "chaos", "ace", "shift", "ace", "shift", "ace", "shift", "chaos", "ace", "ace", "shift", "shift", "chaos"]

    raw_preds = []
    seen = set()

    # STEP 1: Windmill & Gravity (素材生成)
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
        raw_preds.append(chosen)

    # STEP 2: Matrix Crossover (整列・融合)
    final_preds = _matrix_crossover(raw_preds)

    return final_preds

def generate_unique_mini(n3_preds: list[str], n3_last_val: str, n3_trends: dict) -> list[str]:
    # numbers mini = last2 digits, with uniqueness enforcement
    # Miniは「ユニーク性」が重要なので、既存のドリフトロジックを維持
    mini_preds = []
    seen = set()
    cols = ["n2", "n3"]
    last_nums = [int(d) for d in n3_last_val[-2:]]
    roles = ["ace", "shift", "chaos", "ace", "shift", "ace", "shift", "ace", "shift", "chaos"]

    def _pair_score(pair: str, role: str) -> float:
        sectors = GRAVITY_SECTORS if role == "ace" else ANTI_GRAVITY_SECTORS
        score = 0.0
        for j, col in enumerate(cols):
            try:
                d = int(pair[j])
            except Exception:
                return -9999.0
            idx = INDEX_MAP[col][d]
            score += 1.0
            if idx in sectors:
                score += 0.6
            if ((idx - 1) % 10) in sectors or ((idx + 1) % 10) in sectors:
                score += 0.2
            score += (n3_trends[col] * 0.01)
        return score

    def _neighbor_fix(cand: str, role: str) -> str:
        try:
            base = int(cand)
        except Exception:
            return cand

        prev_s = f"{(base - 1) % 100:02d}"
        next_s = f"{(base + 1) % 100:02d}"

        prev_ok = prev_s not in seen
        next_ok = next_s not in seen

        if prev_ok and next_ok:
            return prev_s if _pair_score(prev_s, role) >= _pair_score(next_s, role) else next_s
        if prev_ok:
            return prev_s
        if next_ok:
            return next_s
        return cand

    for i, n3v in enumerate(n3_preds):
        cand = n3v[-2:]
        role = roles[i]

        if cand in seen:
            cand2 = _neighbor_fix(cand, role)
            if cand2 not in seen:
                cand = cand2
            else:
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
    
    # Atomic write
    if safe_save_json(store, path):
        backup_preds_daily()

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
