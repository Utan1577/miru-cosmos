import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "ja,en-US;q=0.9"
}

ROUND_HEAD_RE = re.compile(r"回号\s*第(\d+)回")
DATE_RE = re.compile(r"\d{4}/\d{2}/\d{2}")

def get_month_urls(past_url: str):
    r = requests.get(past_url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    urls = []
    for a in soup.select("a[href]"):
        href = a.get("href")
        if href and re.search(r"/\d{6}/$", href):
            ym = re.search(r"(\d{6})", href).group(1)
            urls.append((ym, urljoin(past_url, href)))

    # 新しい月が先に来るように
    return sorted(urls, reverse=True)

def _extract_payout_from_lines(lines, digits):
    payout = {}

    for i in range(len(lines)):
        t = lines[i]

        if t == "ストレート" and i + 2 < len(lines):
            payout["STR"] = {"kuchi": lines[i+1], "yen": lines[i+2]}

        if t == "ボックス" and i + 2 < len(lines):
            payout["BOX"] = {"kuchi": lines[i+1], "yen": lines[i+2]}

        if t.startswith("セット（ストレート）") and i + 2 < len(lines):
            payout["SET-S"] = {"kuchi": lines[i+1], "yen": lines[i+2]}

        if t.startswith("セット（ボックス）") and i + 2 < len(lines):
            payout["SET-B"] = {"kuchi": lines[i+1], "yen": lines[i+2]}

        # Numbers3 only
        if digits == 3 and t == "ミニ" and i + 2 < len(lines):
            payout["MINI"] = {"kuchi": lines[i+1], "yen": lines[i+2]}

    return payout

def parse_month_page(url: str, digits: int):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # 余計なノイズ除去（数字誤取得の原因になりやすい）
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")
    # 行も使う（払戻拾い用）
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # ★本丸：このページは「回号 第xxxx回」が繰り返しなので、ここでブロックを切る
    matches = list(ROUND_HEAD_RE.finditer(text))

    items = []
    for idx, m in enumerate(matches):
        round_no = int(m.group(1))
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start:end]

        # 抽せん日
        dm = DATE_RE.search(block)
        dtxt = dm.group(0) if dm else None

        # 当せん番号（digits桁）
        nm = re.search(rf"当せん番号\s*([0-9]{{{digits}}})", block)
        ntxt = nm.group(1) if nm else None

        # ブロック部分の lines を作って払戻を拾う（見出し跨ぎに強い）
        block_lines = [l.strip() for l in block.splitlines() if l.strip()]
        payout = _extract_payout_from_lines(block_lines, digits)

        if dtxt and ntxt and re.fullmatch(rf"[0-9]{{{digits}}}", ntxt):
            items.append({
                "round": round_no,
                "date": dtxt,
                "num": ntxt,
                "payout": payout
            })

    # round 重複排除
    uniq = {it["round"]: it for it in items}
    return sorted(uniq.values(), key=lambda x: x["round"], reverse=True)

def fetch_last_n_results(game: str, need: int = 20):
    if game == "N4":
        past = "https://takarakuji.rakuten.co.jp/backnumber/numbers4_past/"
        digits = 4
    elif game == "N3":
        past = "https://takarakuji.rakuten.co.jp/backnumber/numbers3_past/"
        digits = 3
    else:
        raise ValueError("N3/N4 only")

    months = get_month_urls(past)
    collected = {}
    used = []

    for ym, murl in months:
        used.append(ym)
        for it in parse_month_page(murl, digits):
            collected[it["round"]] = it
        if len(collected) >= need:
            break

    items = sorted(collected.values(), key=lambda x: x["round"], reverse=True)[:need]
    return items, used
