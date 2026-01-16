import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from core.config import HEADERS

# Rakuten official backnumber pages
RAKUTEN_BASE = "https://takarakuji.rakuten.co.jp"
PAST_URLS = {
    "N4": "https://takarakuji.rakuten.co.jp/backnumber/numbers4_past/",
    "N3": "https://takarakuji.rakuten.co.jp/backnumber/numbers3_past/",
}

# --------------------------
# helpers
# --------------------------
def _get(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text

def _norm(s: str) -> str:
    return (s or "").replace("\u3000", " ").strip()

def _int_or_none(s: str):
    try:
        return int(s)
    except Exception:
        return None

def _find_month_links(index_html: str, base_url: str) -> list[str]:
    """
    Rakuten's backnumber index page contains month links.
    We collect links that look like .../numbers4_past/202601/ (or similar).
    """
    soup = BeautifulSoup(index_html, "html.parser")
    links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        absu = urljoin(base_url, href)
        if "/backnumber/numbers4_past/" in absu or "/backnumber/numbers3_past/" in absu:
            # month page often includes YYYYMM
            m = re.search(r"/(numbers[34]_past)/(\d{6})/", absu)
            if m:
                links.add(absu)

    # sort by YYYYMM desc
    def key(u):
        m = re.search(r"/(\d{6})/", u)
        return m.group(1) if m else "000000"

    return sorted(list(links), key=key, reverse=True)

def _extract_draw_blocks(month_html: str):
    """
    Month page has multiple draws; structure can vary.
    We'll do robust extraction:
      - find all occurrences of "第####回" and around it search for date and winning number (3 or 4 digits).
    """
    soup = BeautifulSoup(month_html, "html.parser")

    # prefer text stream
    text = soup.get_text("\n", strip=True)
    text = _norm(text)

    # split by draw marker
    # keep the marker number by capturing group
    parts = re.split(r"(第\s*\d+\s*回)", text)
    if len(parts) < 3:
        return []

    blocks = []
    for i in range(1, len(parts), 2):
        marker = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        blocks.append(marker + "\n" + body)

    return blocks

def _parse_one_draw(block: str, game: str):
    """
    Returns dict {round, date, num, payout}
    payout is best-effort; if not found -> {}
    """
    # round
    rm = re.search(r"第\s*(\d+)\s*回", block)
    rno = _int_or_none(rm.group(1)) if rm else None
    if not rno:
        return None

    # date: 2026年1月15日 or 1月15日 (sometimes without year)
    dm = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", block)
    if dm:
        y, mo, d = dm.group(1), int(dm.group(2)), int(dm.group(3))
        date = f"{y}/{mo:02d}/{d:02d}"
    else:
        dm2 = re.search(r"(\d{1,2})月\s*(\d{1,2})日", block)
        date = ""
        if dm2:
            mo, d = int(dm2.group(1)), int(dm2.group(2))
            # year unknown -> keep empty (UI still works)
            date = f"{mo:02d}/{d:02d}"

    # winning number
    # Look for "当せん番号" near digits; if not, take first 3/4 digit token after marker
    want_len = 4 if game == "N4" else 3

    nm = re.search(r"当[せ選]ん番号[^0-9]*([0-9]{" + str(want_len) + r"})", block)
    if nm:
        num = nm.group(1)
    else:
        # fallback: pick first exact-length digit sequence that appears in the block
        cands = re.findall(r"\b([0-9]{" + str(want_len) + r"})\b", block)
        num = cands[0] if cands else None

    if not num:
        return None

    # payout (best-effort). If not found, {} is fine.
    payout = {}

    def pick(label, key):
        # ex: ストレート 12口 1,000,000円  OR  ストレート 1,000,000円
        m = re.search(rf"{label}[^0-9]*([0-9,]+口)?[^0-9]*([0-9,]+円)", block)
        if m:
            kuchi = m.group(1) or ""
            yen = m.group(2)
            payout[key] = {"kuchi": kuchi, "yen": yen}

    pick("ストレート", "STR")
    pick("ボックス", "BOX")
    pick("セットストレート", "SET-S")
    pick("セットボックス", "SET-B")
    if game == "N3":
        pick("ミニ", "MINI")

    return {
        "round": rno,
        "date": date,
        "num": num,
        "payout": payout,
    }

def _fetch_from_rakuten(game: str, need: int = 20):
    base_url = PAST_URLS[game]
    index_html = _get(base_url)
    month_links = _find_month_links(index_html, base_url)

    items = []
    seen_round = set()

    # If month links not found, still try base page itself as a "month-ish" page
    if not month_links:
        month_links = [base_url]

    for murl in month_links:
        try:
            mh = _get(murl)
        except Exception:
            continue

        blocks = _extract_draw_blocks(mh)
        for blk in blocks:
            it = _parse_one_draw(blk, game)
            if not it:
                continue
            rno = it["round"]
            if rno in seen_round:
                continue
            seen_round.add(rno)
            items.append(it)
            if len(items) >= need:
                break

        if len(items) >= need:
            break

    # sort by round desc
    items = sorted(items, key=lambda x: x["round"], reverse=True)[:need]
    return items

# --------------------------
# public API (app.py uses this)
# --------------------------
def fetch_last_n_results(game: str, need: int = 20):
    """
    returns: (items, months_used)
      items: [{"round": int, "date": str, "num": str, "payout": dict}, ...] (round desc)
      months_used: list[int] (not critical; keep [0] if unknown)
    """
    if game not in ("N4", "N3"):
        raise ValueError("fetch_last_n_results supports N4/N3 only")

    items = _fetch_from_rakuten(game, need=need)

    # months_used is optional UI hint; best-effort from dates
    months = set()
    for it in items:
        dt = it.get("date") or ""
        if "/" in dt:
            try:
                parts = dt.split("/")
                if len(parts) >= 2:
                    months.add(int(parts[1]))
            except Exception:
                pass

    months_used = sorted(list(months)) if months else [0]
    return items, months_used
