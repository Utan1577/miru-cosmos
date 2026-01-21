from __future__ import annotations

from typing import List, Tuple, Optional
from collections import Counter
import random


def _digits_len(game: str) -> int:
    return 4 if game == "N4" else 3


def _sanitize_preds(preds: List[str], digits: int) -> List[str]:
    out: List[str] = []
    for p in preds or []:
        s = "".join(ch for ch in str(p) if ch.isdigit())
        if len(s) == digits:
            out.append(s)
    return out


def _seed_from_pool(game: str, pool: List[str]) -> int:
    # Deterministic FNV-1a-ish
    s = game + ":" + "".join(pool)
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _is_all_same(s: str) -> bool:
    return len(set(s)) == 1 if s else False


def _row_max_repeat(s: str) -> int:
    if not s:
        return 0
    c = Counter(s)
    return max(c.values())


def _multiset_overlap(a: str, b: str) -> int:
    ca = Counter(a)
    cb = Counter(b)
    return sum(min(ca[k], cb.get(k, 0)) for k in ca.keys())


def shuffle_recompose(game: str, preds: List[str]) -> List[str]:
    """
    BOX特化：素材（N4=40桁 / N3=30桁）を捨てずに再配置して10本作る。

    目標：
      - 全同一（N4: 4連 / N3: 3連）を確実に排除
      - 可能な限り「1本内 同じ数字3個以上」を回避（最大2個を優先）
      - なるべく同じ顔（重なりすぎ）を避ける（BOX優先なので位置最適化はしない）
      - 必ず10本返す
      - 決定論（素材が同じなら結果が同じ）
    """
    digits = _digits_len(game)
    raw = _sanitize_preds(preds, digits)

    # ensure 10 rows worth of material
    while len(raw) < 10:
        raw.append(raw[-1] if raw else ("0" * digits))
    raw = raw[:10]

    pool: List[str] = [ch for s in raw for ch in s]
    if not pool:
        return ["0" * digits] * 10

    # If pool itself is all one digit, it is mathematically impossible to avoid all-same.
    # In practice this won't happen, but keep safe behavior.
    if len(set(pool)) == 1:
        return [pool[0] * digits] * 10

    rng = random.Random(_seed_from_pool(game, pool))
    counts = Counter(pool)

    # Prepare deterministic digit preference list (by remaining freq desc, digit asc)
    def ranked_digits() -> List[str]:
        items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return [d for d, c in items if c > 0]

    # Pick one digit with soft constraint: avoid making >=3 repeats inside a row when possible.
    def pick_for_row(row_counts: Counter, cap2_prefer: bool = True) -> str:
        candidates = ranked_digits()
        if not candidates:
            return "0"
        # prefer digits under cap (<=1 if picking would make it 3)
        for d in candidates:
            if counts[d] <= 0:
                continue
            if cap2_prefer and row_counts[d] >= 2:
                continue
            counts[d] -= 1
            return d
        # relax
        d = candidates[0]
        counts[d] -= 1
        return d

    # Build 10 rows greedily from global pool, keeping material.
    rows: List[List[str]] = []
    for _ in range(10):
        row: List[str] = []
        rc = Counter()
        for _pos in range(digits):
            row.append(pick_for_row(rc, cap2_prefer=True))
            rc[row[-1]] += 1
        rows.append(row)

    # Phase operations to diversify "faces" without changing material
    # (position permutation inside each row)
    perms4 = [
        (0,1,2,3),
        (1,2,3,0),
        (2,3,0,1),
        (3,0,1,2),
        (0,2,1,3),
        (3,2,1,0),
    ]
    perms3 = [
        (0,1,2),
        (1,2,0),
        (2,0,1),
        (0,2,1),
    ]
    perms = perms4 if digits == 4 else perms3
    for i in range(10):
        p = perms[i % len(perms)]
        rows[i] = [rows[i][k] for k in p]

    def rows_to_strings() -> List[str]:
        return ["".join(r) for r in rows]

    out = rows_to_strings()

    # Repair loop:
    # 1) remove all-same
    # 2) reduce row_max_repeat > 2 when possible
    # 3) reduce exact duplicates
    # 4) reduce too-high overlap clusters (soft)
    def try_swap(i: int, j: int, pi: int, pj: int) -> bool:
        # Swap rows[i][pi] with rows[j][pj]
        si_before = "".join(rows[i])
        sj_before = "".join(rows[j])

        rows[i][pi], rows[j][pj] = rows[j][pj], rows[i][pi]
        si = "".join(rows[i])
        sj = "".join(rows[j])

        # hard constraints
        if _is_all_same(si) or _is_all_same(sj):
            # revert
            rows[i][pi], rows[j][pj] = rows[j][pj], rows[i][pi]
            return False

        # improve criteria: reduce max repeats, reduce duplicates
        before_bad = 0
        after_bad = 0
        if _row_max_repeat(si_before) > 2: before_bad += 1
        if _row_max_repeat(sj_before) > 2: before_bad += 1
        if _row_max_repeat(si) > 2: after_bad += 1
        if _row_max_repeat(sj) > 2: after_bad += 1

        # If swap doesn't worsen repeat situation, keep it
        if after_bad <= before_bad:
            return True

        # otherwise revert
        rows[i][pi], rows[j][pj] = rows[j][pj], rows[i][pi]
        return False

    # Deterministic repair passes
    for _pass in range(40):
        changed = False
        out = rows_to_strings()

        # A) kill exact duplicates by swaps
        seen = {}
        for idx, s in enumerate(out):
            if s in seen:
                # try to break duplicates by swapping one digit with a far row
                src = idx
                tgt = (idx + 3) % 10
                done = False
                for pi in range(digits):
                    for pj in range(digits):
                        if try_swap(src, tgt, pi, pj):
                            done = True
                            changed = True
                            break
                    if done:
                        break
            else:
                seen[s] = idx

        # B) reduce row_max_repeat > 2 by swapping with another row
        out = rows_to_strings()
        for i, s in enumerate(out):
            if _row_max_repeat(s) <= 2:
                continue
            # choose a donor row that has diversity
            j = (i + 5) % 10
            for pi in range(digits):
                for pj in range(digits):
                    if try_swap(i, j, pi, pj):
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break

        # C) ensure no all-same remains (should already be prevented)
        out = rows_to_strings()
        for i, s in enumerate(out):
            if not _is_all_same(s):
                continue
            # force fix by swapping last digit with next row
            j = (i + 1) % 10
            if try_swap(i, j, digits - 1, digits - 1):
                changed = True
                break

        # D) soften "same-face" (very high multiset overlap) if it repeats too much
        out = rows_to_strings()
        for i in range(10):
            for j in range(i + 1, 10):
                if _multiset_overlap(out[i], out[j]) >= digits and out[i] != out[j]:
                    # identical multiset (e.g., 5550 vs 0555) is OK for BOX,
                    # but if too many, we try one small swap
                    k = (j + 2) % 10
                    if try_swap(j, k, 0, 0):
                        changed = True
                        break
            if changed:
                break

        if not changed:
            break

    # Finalize
    out = rows_to_strings()

    # Guarantee: 10 strings, correct length, no all-same (best effort)
    fixed: List[str] = []
    for s in out:
        s = "".join(ch for ch in s if ch.isdigit())[:digits]
        if len(s) != digits:
            s = ("0" * digits)
        if _is_all_same(s):
            # last-resort drift (changes material minimally, only if needed)
            base = int(s[-1])
            for step in range(1, 10):
                cand = s[:-1] + str((base + step) % 10)
                if not _is_all_same(cand):
                    s = cand
                    break
        fixed.append(s)

    # Unique preference
    uniq: List[str] = []
    seenu = set()
    for s in fixed:
        if s not in seenu:
            uniq.append(s)
            seenu.add(s)
        if len(uniq) >= 10:
            break

    while len(uniq) < 10:
        uniq.append(("0" * digits))

    return uniq[:10]
