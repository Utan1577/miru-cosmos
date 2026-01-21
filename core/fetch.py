import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from core.config import HEADERS

ROUND_RE = re.compile(r"(?:回号\s*)?第(\d+)回")
DATE_RE  = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")
NUM_RE_4 = re.compile(r"当せん番号\s*([0-9]{4})")
NUM_RE_3 = re.compile(r"当せん番号\s*([0-9]{3})")

def get_month_urls(past_url: str) -> list[str]:
    r = requests.get(past_url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    soup = BeautifulSoup(r.text, "html.parser")

    urls = []
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if not href:
            continue
        u = urljoin(past_url, href)
        # 楽天のバックナンバー配下っぽいものを優先的に集める
        if "backnumber" in u or "numbers" in u:
            urls.append(u)

    # 重複除去（順序維持）
    out = []
    seen = set()
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)

    # もし拾えなかったら past_url 自体も入れておく（最低限動く）
    if not out:
        out = [past_url]

    return out

def parse_month_page(url: str, digits: int) -> list[dict]:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    soup = BeautifulSoup(r.text, "html.parser")

    text = soup.get_text("\n", strip=True)

    # 「回号 第xxxx回」でも「第xxxx回」でも split
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
            y, mo, d = int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3))
            date_str = f"{y:04d}/{mo:02d}/{d:02d}"

        m_num = NUM_RE_4.search(b) if digits == 4 else NUM_RE_3.search(b)
        if not m_num:
            continue
        num = m_num.group(1)

        payout = {}
        # ざっくり抽出（壊れない優先）
        for k in ["ストレート", "ボックス", "セット-ストレート", "セット-ボックス", "ミニ"]:
            m = re.search(rf"{k}\s*([0-9,]+)円", b)
            if m:
                payout[k] = {"yen": m.group(1)}

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

    return out[:need], used
