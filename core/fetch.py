import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime

from core.config import HEADERS, JST

ROUND_RE = re.compile(r"(?:回号\s*)?第(\d+)回")
DATE_RE  = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")
NUM_RE_4 = re.compile(r"当せん番号\s*([0-9]{4})")
NUM_RE_3 = re.compile(r"当せん番号\s*([0-9]{3})")

YEN_RE = re.compile(r"([0-9][0-9,]*)円")


def _strip_pua(s: str) -> str:
    # 私用領域（Termius等で混ざる “” 系）を除去
    return re.sub(r"[\uf000-\uf8ff]", "", s)


def _normalize_date(y, m, d) -> str:
    return f"{int(y):04d}/{int(m):02d}/{int(d):02d}"


def _month_list_back(n_months: int = 36) -> list[tuple[int, int]]:
    """
    JST基準で、当月から過去n_months分の (YYYY,MM) を返す。
    """
    now = datetime.now(JST)
    y = now.year
    m = now.month
    out = []
    for _ in range(n_months):
        out.append((y, m))
        m -= 1
        if m <= 0:
            m = 12
            y -= 1
    return out


def get_month_urls(past_url: str) -> list[str]:
    """
    楽天backnumberは月選択が <select><option value="..."> になっていることがある。
    なので a[href] だけでは足りない場合がある。

    1) a[href] から候補収集
    2) option[value] から候補収集
    3) それでも少ない場合は、過去36ヶ月分のURLを自動生成して追加
    """
    r = requests.get(past_url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    soup = BeautifulSoup(r.text, "html.parser")

    candidates = []

    # 1) <a href>
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if not href:
            continue
        u = urljoin(past_url, href)
        if ("numbers4" in u or "numbers3" in u) and ("backnumber" in u):
            candidates.append(u)

    # 2) <option value>
    for opt in soup.find_all("option"):
        val = opt.get("value", "")
        if not val:
            continue
        u = urljoin(past_url, val)
        if ("numbers4" in u or "numbers3" in u) and ("backnumber" in u):
            candidates.append(u)

    # 3) 最低限、トップも含める
    candidates.append(past_url)

    # 重複排除
    out = []
    seen = set()
    for u in candidates:
        if u not in seen:
            seen.add(u)
            out.append(u)

    # 4) まだ少ないならURL自動生成（推定パス）
    # 例: https://takarakuji.rakuten.co.jp/backnumber/numbers4/2026/01/
    if len(out) < 6:
        is_n4 = "numbers4" in past_url
        base = "https://takarakuji.rakuten.co.jp/backnumber/numbers4/" if is_n4 else "https://takarakuji.rakuten.co.jp/backnumber/numbers3/"
        for (yy, mm) in _month_list_back(36):
            u = f"{base}{yy:04d}/{mm:02d}/"
            if u not in seen:
                seen.add(u)
                out.append(u)

    return out


def _scan_payout_lines(lines: list[str], digits: int) -> dict:
    """
    楽天の払戻は
      ラベル行 → 口数行 → 金額行(円)
    の並びなので、ラベルを見つけたら次の数行で最初の “円” を拾う。
    """
    payout = {}

    def norm_label(s: str) -> str:
        s = _strip_pua(s)
        s = s.replace(" ", "").replace("\u3000", "")
        return s

    labels = [
        ("ストレート", "STR"),
        ("ボックス", "BOX"),
        ("セット（ストレート）", "SET-S"),
        ("セット（ボックス）", "SET-B"),
    ]
    if digits == 3:
        labels.append(("ミニ", "MINI"))

    n = len(lines)
    for i in range(n):
        lab = norm_label(lines[i])
        for jp, key in labels:
            if lab == jp:
                yen = ""
                for j in range(i + 1, min(n, i + 7)):
                    t = norm_label(lines[j])
                    m = YEN_RE.search(t)
                    if m:
                        yen = m.group(1)
                        break
                if yen:
                    payout[key] = {"yen": yen}
                break

    return payout


def parse_month_page(url: str, digits: int) -> list[dict]:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    soup = BeautifulSoup(r.text, "html.parser")

    text = soup.get_text("\n", strip=True)
    text = _strip_pua(text)

    parts = re.split(r"(?:回号\s*)?(第\d+回)", text)
    blocks = []
    cur = ""
    for p in parts:
        if p.startswith("第") and p.endswith("回"):
            if cur:
                blocks.append(cur)
            cur = p
        else:
            cur += "\n" + p
    if cur:
        blocks.append(cur)

    items = []
    for b in blocks:
        m_round = ROUND_RE.search(b)
        if not m_round:
            continue
        round_no = int(m_round.group(1))

        m_date = DATE_RE.search(b)
        date_str = ""
        if m_date:
            date_str = _normalize_date(m_date.group(1), m_date.group(2), m_date.group(3))

        m_num = (NUM_RE_4.search(b) if digits == 4 else NUM_RE_3.search(b))
        if not m_num:
            continue
        num = m_num.group(1)

        lines = b.splitlines()
        payout = _scan_payout_lines(lines, digits)

        items.append({
            "round": round_no,
            "date": date_str,
            "num": num,
            "payout": payout
        })

    items.sort(key=lambda x: x.get("round", 0), reverse=True)
    return items


def fetch_last_n_results(game: str, need: int = 20):
    if game == "N4":
        past_url = "https://takarakuji.rakuten.co.jp/backnumber/numbers4/"
        digits = 4
    else:
        past_url = "https://takarakuji.rakuten.co.jp/backnumber/numbers3/"
        digits = 3

    month_urls = get_month_urls(past_url)
    used = []
    out = []

    for mu in month_urls:
        if len(out) >= need:
            break
        try:
            items = parse_month_page(mu, digits)
            if items:
                used.append(mu)
            for it in items:
                out.append(it)
                if len(out) >= need:
                    break
        except Exception:
            continue

    # round重複排除（最初の1件だけ残す）
    dedup = []
    seen_round = set()
    for it in out:
        rno = it.get("round")
        if rno in seen_round:
            continue
        seen_round.add(rno)
        dedup.append(it)

    return dedup[:need], used
