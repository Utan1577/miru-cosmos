import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.config import JST, safe_save_json

RESULTS_CACHE_FILE = "data/results_cache.json"
KC_CACHE_FILE = "data/kc_cache.json"


# ----------------------------
# helpers
# ----------------------------
def _now_jst() -> datetime:
    return datetime.now(JST)


def today_ymd() -> str:
    # cache key format uses YYYY/MM/DD (matches your fetch output)
    return _now_jst().strftime("%Y/%m/%d")


def hour_now() -> int:
    return int(_now_jst().strftime("%H"))


def _load_json(path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return dict(default)


def _save_json(path: str, data: Dict[str, Any]) -> bool:
    d = dict(data)
    d["updated_at"] = _now_jst().strftime("%Y-%m-%d %H:%M:%S")
    return bool(safe_save_json(d, path))


def _norm_date(s: str) -> str:
    # accept "2026/1/5" etc and normalize
    if not s:
        return ""
    # already "YYYY/MM/DD"
    parts = s.split("/")
    if len(parts) == 3:
        try:
            y = int(parts[0])
            m = int(parts[1])
            d = int(parts[2])
            return f"{y:04d}/{m:02d}/{d:02d}"
        except Exception:
            return s
    return s


# ----------------------------
# results cache (N4/N3/NM)
# ----------------------------
def load_results_cache() -> Dict[str, Any]:
    cache = _load_json(RESULTS_CACHE_FILE, {"N4": {}, "N3": {}, "NM": {}, "updated_at": ""})
    for k in ("N4", "N3", "NM"):
        if k not in cache or not isinstance(cache.get(k), dict):
            cache[k] = {}
    return cache


def save_results_cache(cache: Dict[str, Any]) -> bool:
    return _save_json(RESULTS_CACHE_FILE, cache)


def cache_items_by_round(cache: Dict[str, Any], game: str, items: List[Dict[str, Any]]) -> None:
    """
    Store results by round, do NOT overwrite existing (past results immutable).
    Exception: if existing payout is empty and incoming has payout, we allow upgrade.
    """
    if game not in ("N4", "N3"):
        return
    g = cache.setdefault(game, {})
    if not isinstance(g, dict):
        g = {}
        cache[game] = g

    for it in items or []:
        try:
            rno = int(it.get("round"))
        except Exception:
            continue

        key = str(rno)
        date = _norm_date(it.get("date", ""))
        num = str(it.get("num", ""))
        payout = it.get("payout", {}) or {}

        if key not in g:
            g[key] = {"round": rno, "date": date, "num": num, "payout": payout}
        else:
            # upgrade payout if previously empty
            old = g.get(key, {}) if isinstance(g.get(key), dict) else {}
            old_pay = old.get("payout", {}) if isinstance(old.get("payout", {}), dict) else {}
            if (not old_pay) and payout:
                old["payout"] = payout
            if (not old.get("date")) and date:
                old["date"] = date
            if (not old.get("num")) and num:
                old["num"] = num
            g[key] = old


def cached_items(cache: Dict[str, Any], game: str, limit: int = 120) -> List[Dict[str, Any]]:
    """
    Return list sorted by round desc.
    """
    g = cache.get(game, {})
    if not isinstance(g, dict) or not g:
        return []

    items = []
    for k, v in g.items():
        if not isinstance(v, dict):
            continue
        try:
            rno = int(v.get("round", k))
        except Exception:
            continue
        items.append({
            "round": rno,
            "date": _norm_date(v.get("date", "")),
            "num": v.get("num", ""),
            "payout": v.get("payout", {}) or {},
        })
    items.sort(key=lambda x: x.get("round", 0), reverse=True)
    return items[:max(1, limit)]


def cache_has_today(cache: Dict[str, Any], game: str, today: str) -> bool:
    today = _norm_date(today)
    for it in cached_items(cache, game, limit=300):
        if _norm_date(it.get("date", "")) == today:
            return True
    return False


def should_fetch_after_20(cache: Dict[str, Any], game: str) -> bool:
    """
    Rule:
      - after 20:00 JST: fetch only if today's result not in cache
      - before 20:00: do NOT fetch (use cache), unless cache is empty (first warm)
    """
    h = hour_now()
    today = today_ymd()
    if h < 20:
        # allow warm-up only if empty
        return len(cached_items(cache, game, limit=1)) == 0
    # after 20: fetch only if missing today
    return not cache_has_today(cache, game, today)


# ----------------------------
# KC cache (by date)
# ----------------------------
def load_kc_cache() -> Dict[str, Any]:
    cache = _load_json(KC_CACHE_FILE, {"by_date": {}, "updated_at": ""})
    if "by_date" not in cache or not isinstance(cache.get("by_date"), dict):
        cache["by_date"] = {}
    return cache


def save_kc_cache(cache: Dict[str, Any]) -> bool:
    return _save_json(KC_CACHE_FILE, cache)


def kc_get(cache: Dict[str, Any], date: str) -> Optional[Dict[str, Any]]:
    date = _norm_date(date)
    by_date = cache.get("by_date", {})
    if not isinstance(by_date, dict):
        return None
    v = by_date.get(date)
    return v if isinstance(v, dict) else None


def kc_put(cache: Dict[str, Any], date: str, result: str, payout: Dict[str, Any]) -> None:
    date = _norm_date(date)
    by_date = cache.setdefault("by_date", {})
    if not isinstance(by_date, dict):
        by_date = {}
        cache["by_date"] = by_date
    if date and date not in by_date:
        by_date[date] = {"result": result, "payout": payout or {}}
    elif date:
        # upgrade payout if empty
        cur = by_date.get(date, {}) if isinstance(by_date.get(date), dict) else {}
        cur_pay = cur.get("payout", {}) if isinstance(cur.get("payout", {}), dict) else {}
        if (not cur_pay) and payout:
            cur["payout"] = payout
        if (not cur.get("result")) and result:
            cur["result"] = result
        by_date[date] = cur
