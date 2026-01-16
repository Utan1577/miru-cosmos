from typing import List

def nm_drift_unique(preds_2d: List[str]) -> List[str]:
    """
    Numbers mini (NM) duplicate resolver.
    Rule (deterministic, no random):
      base = N3 last2
      if duplicate -> +1, -1, +2, -2, ... (00-99 wrap)
    """
    seen = set()
    out: List[str] = []

    for s in preds_2d:
        # normalize to int 0..99
        try:
            base = int(str(s).strip()) % 100
        except Exception:
            base = 0

        cand = f"{base:02d}"
        if cand not in seen:
            seen.add(cand)
            out.append(cand)
            continue

        chosen = None
        # drift search: +1, -1, +2, -2, ...
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
            chosen = cand  # theoretically unreachable for <=10 outputs

        seen.add(chosen)
        out.append(chosen)

    return out
