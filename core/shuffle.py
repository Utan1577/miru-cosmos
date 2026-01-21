from __future__ import annotations

from typing import List, Optional
import random
import re
from collections import Counter


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
    # Deterministic seed from content (stable across runs given same input)
    s = game + ":" + "".join(pool)
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _is_banned(game: str, s: str) -> bool:
    # Minimal ban: N4 forbids 4-of-a-kind, N3 forbids 3-of-a-kind (all-same)
    return len(set(s)) == 1


def _rotate(lst: List[str], k: int) -> List[str]:
    if not lst:
        return lst
    k = k % len(lst)
    return lst[k:] + lst[:k]


def shuffle_recompose(game: str, preds: List[str]) -> List[str]:
    """
    Recompose 10 picks by shuffling the pooled digits while preserving digit frequency.

    Input:
      - preds: list[str] (expected 10) of N4(4桁) / N3(3桁)

    Output:
      - list[str] len=10
      - preserves multiset of digits as much as possible
      - bans only all-same (N4: 4連, N3: 3連)
    """
    digits = _digits_len(game)
    raw = _sanitize_preds(preds, digits)

    # Ensure exactly 10 rows worth of digits in the pool
    while len(raw) < 10:
        raw.append(raw[-1] if raw else ("0" * digits))
    raw = raw[:10]

    # Build pool (40 digits for N4, 30 for N3)
    pool: List[str] = [ch for s in raw for ch in s]

    # Deterministic shuffle of pool
    rng = random.Random(_seed_from_pool(game, pool))
    rng.shuffle(pool)

    # Lane distribution: digits lanes, each length 10
    lanes: List[List[str]] = []
    for pos in range(digits):
        lane = pool[pos::digits]
        while len(lane) < 10:
            lane.append(str((pos + len(lane)) % 10))
        lanes.append(lane[:10])

    # Phase rotation to reduce repetitive "faces"
    for pos in range(digits):
        lanes[pos] = _rotate(lanes[pos], (pos * 3) % 10)

    def build_rows() -> List[str]:
        return ["".join(lanes[pos][row] for pos in range(digits)) for row in range(10)]

    # Controlled swaps to remove banned/duplicates
    out = build_rows()
    it = 0
    while it < 2500:
        it += 1
        seen = set()
        bad_i: Optional[int] = None
        for i, s in enumerate(out):
            if _is_banned(game, s) or s in seen:
                bad_i = i
                break
            seen.add(s)
        if bad_i is None:
            break

        i = bad_i
        j = (i + 1 + (it % 9)) % 10
        lane_to_swap = it % digits
        lanes[lane_to_swap][i], lanes[lane_to_swap][j] = lanes[lane_to_swap][j], lanes[lane_to_swap][i]
        out[i] = "".join(lanes[pos][i] for pos in range(digits))
        out[j] = "".join(lanes[pos][j] for pos in range(digits))

    # Final drift fix for any remaining banned
    fixed: List[str] = []
    for s in out:
        if not _is_banned(game, s):
            fixed.append(s)
            continue
        # drift last digit deterministically
        last = int(s[-1])
        for step in range(1, 10):
            cand_last = str((last + step) % 10)
            cand = s[:-1] + cand_last
            if not _is_banned(game, cand):
                fixed.append(cand)
                break
        else:
            fixed.append("0" * digits)

    # Enforce uniqueness preference and length=10
    out2: List[str] = []
    seen2 = set()
    for s in fixed:
        if s not in seen2:
            out2.append(s)
            seen2.add(s)
        if len(out2) >= 10:
            break

    base = out2[-1] if out2 else ("0" * digits)
    k = 0
    while len(out2) < 10 and k < 300:
        k += 1
        cc = list(base)
        cc[-1] = str((int(cc[-1]) + k) % 10)
        cand = "".join(cc)
        if not _is_banned(game, cand) and cand not in seen2:
            out2.append(cand)
            seen2.add(cand)

    while len(out2) < 10:
        out2.append("0" * digits)

    return out2[:10]
