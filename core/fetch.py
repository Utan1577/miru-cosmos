import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "ja,en-US;q=0.9"
}

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

    return sorted(urls, reverse=True)

def parse_month_page(url: str, digits: int):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text("\n")
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    items = []
    i = 0
    while i < len(lines):
        payout = {}
        rtxt = dtxt = ntxt = None

        if re.match(r"第\d+回", lines[i]):
            rtxt = lines[i]

            # ---- 修正ポイント ----
            # 次の「第◯回」が出たら、その時点で探索終了（上書き防止）
            for j in range(i + 1, len(lines)):
                if re.match(r"第\d+回", lines[j]):
                    break

                # date/num は最初に見つかったものを採用（上書きしない）
                if dtxt is None and re.fullmatch(r"\d{4}/\d{2}/\d{2}", lines[j]):
                    dtxt = lines[j]

                if ntxt is None and re.fullmatch(rf"\d{{{digits}}}", lines[j]):
                    ntxt = lines[j]

                # ---- payout ----
                if lines[j] == "ストレート" and j + 2 < len(lines):
                    payout["STR"] = {"kuchi": lines[j+1], "yen": lines[j+2]}

                if lines[j] == "ボックス" and j + 2 < len(lines):
                    payout["BOX"] = {"kuchi": lines[j+1], "yen": lines[j+2]}

                if lines[j].startswith("セット（ストレート）") and j + 2 < len(lines):
                    payout["SET-S"] = {"kuchi": lines[j+1], "yen": lines[j+2]}

                if lines[j].startswith("セット（ボックス）") and j + 2 < len(lines):
                    payout["SET-B"] = {"kuchi": lines[j+1], "yen": lines[j+2]}

                # ★ Numbers3 MINI ★
                if digits == 3 and lines[j] == "ミニ" and j + 2 < len(lines):
                    payout["MINI"] = {"kuchi": lines[j+1], "yen": lines[j+2]}

            rm = re.search(r"第(\d+)回", rtxt)
            dm = re.search(r"\d{4}/\d{2}/\d{2}", dtxt or "")
            nm = re.search(rf"\d{{{digits}}}", ntxt or "")

            if rm and dm and nm:
                items.append({
                    "round": int(rm.group(1)),
                    "date": dtxt,
                    "num": ntxt,
                    "payout": payout
                })

        i += 1

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
