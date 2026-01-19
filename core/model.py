import random
import itertools
from collections import Counter
import json
import os
from datetime import datetime
from core.config import INDEX_MAP, WINDMILL_MAP, GRAVITY_SECTORS, ANTI_GRAVITY_SECTORS, JST, safe_save_json
from core.backup import backup_preds_daily

# ------------------------------------------------------------
# Matrix Crossover Logic (The Aligner - Box & Str Hybrid)
# ------------------------------------------------------------
def _matrix_crossover(raw_preds: list[str]) -> list[str]:
    """
    マトリックス・クロスオーバー (BOX-STR Hybrid):
    1. 生成された予測群（素材）全体から「場に出ている強い数字」をグローバルに特定（BOX対策）。
    2. その強い数字を、各桁の傾向に合わせて最適な位置に配置（STR対策）。
    3. 「数字としての強さ」と「並びの美しさ」を両立させた10行を生成する。
    """
    if not raw_preds:
        return []

    width = len(raw_preds[0])

    # 1. 解析 (Analysis)
    # A. ポジショナル・カウント (桁ごとの強さ -> STR用)
    pos_counts = [Counter() for _ in range(width)]
    # B. グローバル・カウント (全体での強さ -> BOX用)
    global_count = Counter()

    for p in raw_preds:
        for i, d in enumerate(p):
            pos_counts[i][d] += 1
            global_count[d] += 1

    # 2. 候補生成 (Candidate Generation)
    # 各桁で「その場所で強い数字」上位5つ + 「全体で最強の数字」上位3つ を候補にする
    # これにより、配置重視の数字と、パワー重視の数字が混ざる
    global_strongest = [d for d, _ in global_count.most_common(3)]
    
    top_digits_per_col = []
    for c in pos_counts:
        # その桁のTop5
        col_cands = set(d for d, _ in c.most_common(5))
        # 全体のTop3も強制的に候補に入れる (BOX漏れを防ぐ)
        for g in global_strongest:
            col_cands.add(g)
        top_digits_per_col.append(list(col_cands))

    # 3. 組み合わせとスコアリング (Scoring)
    candidates = []
    
    # 候補の組み合わせを全探索
    for combo in itertools.product(*top_digits_per_col):
        s = "".join(combo)
        
        # Score 1: ポジショナル・スコア (配置の正しさ)
        score_pos = sum(pos_counts[i][ch] for i, ch in enumerate(s))
        
        # Score 2: ボックス・スコア (数字そのもののパワー)
        # その数字が全体でどれだけ出ているか？
        score_box = sum(global_count[ch] for ch in s)
        
        # ハイブリッド評価: BOX力(パワー) と STR力(配置) を合算
        # 少しBOX力を重く見て、カスり当たりを増やす
        total_score = score_pos + (score_box * 1.2)
        
        candidates.append((total_score, s))

    # スコア順にソート (最強のキメラ順)
    candidates.sort(key=lambda x: x[0], reverse=True)

    # 4. 出力 (Top 10 Unique)
    final_preds = []
    seen = set()

    for score, s in candidates:
        if s not in seen:
            seen.add(s)
            final_preds.append(s)
        if len(final_preds) >= 10:
            break

    # 補填 (万が一足りない場合)
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
    Matrix Crossover (Box-Str Hybrid) で最強の10行へ昇華させる。
    """
    cols = ["n1", "n2", "n3", "n4"] if game == "N4" else ["n1", "n2", "n3"]
    last_nums = [int(d) for d in last_val]
    # 素材生成: バリエーションを確保するため多めに回す
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

    # STEP 2: Matrix Crossover (BOX & STR 融合)
    final_preds = _matrix_crossover(raw_preds)

    return final_preds

def generate_unique_mini(n3_preds: list[str], n3_last_val: str, n3_trends: dict) -> list[str]:
    # numbers mini = last2 digits, with uniqueness enforcement
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
