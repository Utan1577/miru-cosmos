# core/optimizer.py
# MIRU-PAD: CROSS-OVER (SAFE) optimizer
#
# Protocol:
# - UI: NO CHANGE
# - Output: ALWAYS 10 picks (same as input count)
# - Deterministic: NO random
# - Immutable Past: apply ONLY to future/NOW (caller responsibility)
#
# This optimizer improves "near-miss" situations by reassembling candidate digits
# using deterministic ranking derived from the model's raw 10 picks.

from __future__ import annotations

from collections import Counter
from typing import List, Tuple


def _digits_len(game: str) -> int:
    return 4 if game == "N4" else 3


def _sanitize_preds(preds: List[str], digits: int) -> List[str]:
    out: List[str] = []
    for p in preds or []:
        s = "".join(ch for ch in str(p) if ch.isdigit())
        if len(s) == digits:
            out.append(s)
    return out


def _rank_list(counter: Counter) -> List[str]:
    """Return digits ranked by (freq desc, digit asc)."""
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return [d for d, _ in items]


def _build_pos_counters(preds: List[str], digits: int) -> List[Counter]:
    pos = [Counter() for _ in range(digits)]
    for p in preds:
        for i, ch in enumerate(p[:digits]):
            pos[i][ch] += 1
    return pos


def _candidate_lists(pos_counts: List[Counter], top_k: int) -> List[List[str]]:
    lists: List[List[str]] = []
    for c in pos_counts:
        ranked = _rank_list(c)
        if not ranked:
            ranked = [str(i) for i in range(10)]
        lists.append(ranked[:max(1, top_k)])
    return lists


def _score_combo(combo: str, pos_counts: List[Counter]) -> Tuple[int, str]:
    # Score = sum of per-position frequency; tie-breaker = combo string
    score = 0
    for i, ch in enumerate(combo):
        score += int(pos_counts[i].get(ch, 0))
    return (score, combo)


def optimize_predictions(game: str, preds: List[str], top_k_per_pos: int = 5) -> List[str]:
    """Deterministically rewrite the raw predictions.

    Input:  list of predicted numbers (len=10 expected)
    Output: list of numbers (len=10) optimized by cross-over safe mode.

    Safe-mode rules:
    - Keeps digit positions (no "position destroy").
    - No random.
    - Always returns 10 picks (or original count if <10).
    """
    digits = _digits_len(game)
    raw = _sanitize_preds(preds, digits)
    if not raw:
        return preds

    want_n = len(raw)

    pos_counts = _build_pos_counters(raw, digits)
    cand_lists = _candidate_lists(pos_counts, top_k_per_pos)

    # Generate candidate combos via deterministic nested loops.
    # We do NOT explode all possibilities blindly; we generate all combos
    # for the small top_k space and then take the best 10.
    candidates: List[str] = []

    def rec(i: int, prefix: str):
        if i == digits:
            candidates.append(prefix)
            return
        for d in cand_lists[i]:
            rec(i + 1, prefix + d)

    rec(0, "")

    # Rank candidates by score desc, then lexicographic asc
    scored = sorted((_score_combo(c, pos_counts) for c in candidates), key=lambda t: (-t[0], t[1]))

    optimized: List[str] = []
    seen = set()

    for _, c in scored:
        if c in seen:
            continue
        optimized.append(c)
        seen.add(c)
        if len(optimized) >= want_n:
            break

    # Fallback: if not enough unique combos, append original raw preds in order
    if len(optimized) < want_n:
        for p in raw:
            if p not in seen:
                optimized.append(p)
                seen.add(p)
            if len(optimized) >= want_n:
                break

    return optimized
