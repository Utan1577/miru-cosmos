from __future__ import annotations

from typing import List
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
    # deterministic seed from content
    s = game + ":" + "".join(pool)
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _is_all_same(s: str) -> bool:
    return len(set(s)) == 1 if s else False


def shuffle_recompose(game: str, preds: List[str]) -> List[str]:
    """
    BOX特化の再配置（素材保存＋見た目分散）

    Input:
      - preds: list[str] (10本想定)

    Output:
      - 10本
      - 素材（数字頻度）をできるだけ保存
      - N4=4連 / N3=3連 の全同一だけ禁止
    """
    digits = _digits_len(game)
    raw = _sanitize_preds(preds, digits)

    # ensure 10 rows exist (material is duplicated minimally if needed)
    while len(raw) < 10:
        raw.append(raw[-1] if raw else ("0" * digits))
    raw = raw[:10]

    # pool: N4=40, N3=30
    pool: List[str] = [ch for s in raw for ch in s]
    if not pool:
        return ["0" * digits] * 10

    rng = random.Random(_seed_from_pool(game, pool))

    counts = Counter(pool)

    # helper: choose digit for a position, trying to avoid too many repeats inside the same number
    def pick_digit(row_counts: Counter, prefer_cap: int) -> str:
        # rank digits by remaining count desc, tie by digit asc, then shuffle tie groups deterministically
        items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        # try strict cap first
        for d, c in items:
            if c <= 0:
                continue
            if row_counts[d] < prefer_cap:
                counts[d] -= 1
                return d
        # relax: allow any remaining digit
        for d, c in items:
            if c <= 0:
                continue
            counts[d] -= 1
            return d
        # should not happen
        return "0"

    # build rows greedily from the global pool counts
    rows: List[List[str]] = []
    for _ in range(10):
        row: List[str] = []
        row_counts = Counter()
        # prefer at most 2 duplicates inside one number (keeps it from looking like 555x spam)
        prefer_cap = 2
        for _pos in range(digits):
            d = pick_digit(row_counts, prefer_cap)
            row.append(d)
            row_counts[d] += 1
        rows.append(row)

    # phase operations: rotate positions per-row to vary “faces” without changing material
    for i in range(10):
        if digits == 4:
            # rotate by i mod 4
            k = i % 4
            if k:
                rows[i] = rows[i][k:] + rows[i][:k]
        else:
            # digits == 3
            k = i % 3
            if k:
                rows[i] = rows[i][k:] + rows[i][:k]

    out = ["".join(r) for r in rows]

    # repair: remove all-same by swapping last digit with another row
    it = 0
    while it < 2000:
        it += 1
        bad = [idx for idx, s in enumerate(out) if _is_all_same(s)]
        if not bad:
            break
        i = bad[0]
        j = (i + 1 + (it % 9)) % 10
        # swap last digit
        ri = list(out[i])
        rj = list(out[j])
        ri[-1], rj[-1] = rj[-1], ri[-1]
        out[i] = "".join(ri)
        out[j] = "".join(rj)
        if not _is_all_same(out[i]) and not _is_all_same(out[j]):
            continue

    # ensure exactly 10
    out = out[:10]
    while len(out) < 10:
        out.append(out[-1] if out else ("0" * digits))

    return out
