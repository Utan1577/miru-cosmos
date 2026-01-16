# core/mini.py
# NM drift unique (deterministic, no random)
# Rule: base = N3 last2; if duplicate -> +1, -1, +2, -2, ... (00-99 wrap)

from typing import List

def nm_drift_unique(preds_2d: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []

    for s in preds_2d:
        # normalize to 2 digits
        try:
            base = int(str(s).strip()) % 100
        except Exception:
            base = 0
        cand = f"{base:02d}"

        if cand not in seen:
            seen.add(cand)
            out.append(cand)
            continue

        # drift: +1, -1, +2, -2, ...
        chosen = None
        for k in range(1, 100):
            for delta in (k, -k):
                v = (base + delta) % 100
                c = f"{v:02d}"
                if c not in seen:
                    chosen = c
                    break
            if chosen is not None:
                break

        if chosen is None:
            # theoretically unreachable (100 slots, <=10 picks)
            chosen = cand

        seen.add(chosen)
        out.append(chosen)

    return out
