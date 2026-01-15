import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# もし core/config.py に HEADERS がある運用なら↓に変えてOK
# from core.config import HEADERS

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "ja,en-US;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

def get_month_urls(past_url: str):
    r = requests.get(past_url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    urls = []
    for a in soup.select("a[href]"):
        href = a.get("href")
        if not href:
            continue
        m = re.search(r"/backnumber/(numbers4|numbers3)/(\d{6})/", href)
        if m:
            ym = m.group(2)
            urls.append((ym, urljoin(past_url, href)))

    # 新しい月→古い月の順
    return sorted(set(urls), reverse=True)

def _pick_round(txt: str):
    m = re.search(r"第(\d+)回", txt or "")
    return int(m.group(1)) if m else None

def _pick_date(txt: str):
    m = re.search(r"\d{4}/\d{2}/\d{2}", txt or "")
    return m.group(0) if m else None

def _pick_num(txt: str, digits: int):
    # "345" / "8060" のような当せん番号
    m = re.search(rf"\b\d{{{digits}}}\b", (txt or "").replace(" ", ""))
    return m.group(0) if m else None

def _pick_payout(block_text: str, label: str):
    """
    ブロック全文から
      ラベル ... 891口 ... 7,600円
    を拾う。改行や空白が挟まってもOK。
    """
    # label の後に「xx口」と「yy円」がどこかに出る形を許す
    pat = rf"{re.escape(label)}.*?([0-9,]+口).*?([0-9,]+円)"
    m = re.search(pat, block_text, flags=re.DOTALL)
    if not m:
        return None
    return {"kuchi": m.group(1), "yen": m.group(2)}

def parse_month_page(url: str, digits: int):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    lines = [l.strip() for l in soup.get_text("\n", strip=True).splitlines() if l.strip()]

    items = []
    i = 0
    while i < len(lines):
        # 楽天は「開催回」「回号」ラベル → 次行に「第xxxx回」が多い
        if lines[i] in ("開催回", "回号") and i + 1 < len(lines):
            round_line = lines[i + 1]
            round_no = _pick_round(round_line)
            if not round_no:
                i += 1
                continue

            # 次の「開催回/回号」までをこの回のブロックとする
            end = len(lines)
            for t in range(i + 2, len(lines)):
                if lines[t] in ("開催回", "回号"):
                    end = t
                    break

            block = lines[i:end]
            block_text = "\n".join(block)

            # 日付・当せん番号（ラベルの次行を拾う）
            date = None
            num = None
            for j in range(0, len(block) - 1):
                if block[j] in ("抽せん日", "抽選日"):
                    date = _pick_date(block[j + 1])
                if block[j] in ("当せん番号", "当選番号"):
                    num = _pick_num(block[j + 1], digits)

            # 払戻（ブロック全文から拾う：これが一番強い）
            payout = {}
            got = _pick_payout(block_text, "ストレート")
            if got: payout["STR"] = got
            got = _pick_payout(block_text, "ボックス")
            if got: payout["BOX"] = got
            got = _pick_payout(block_text, "セット（ストレート）")
            if got: payout["SET-S"] = got
            got = _pick_payout(block_text, "セット（ボックス）")
            if got: payout["SET-B"] = got
            if digits == 3:
                got = _pick_payout(block_text, "ミニ")
                if got: payout["MINI"] = got

            # 最低限 round/date/num が取れたら採用
            if date and num and len(num) == digits:
                items.append({
                    "round": round_no,
                    "date": date,
                    "num": num,
                    "payout": payout
                })

            i = end
            continue

        i += 1

    # round重複排除
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
        used.append(int(ym))
        for it in parse_month_page(murl, digits):
            collected[it["round"]] = it
        if len(collected) >= need:
            break

    items = sorted(collected.values(), key=lambda x: x["round"], reverse=True)[:need]
    return items, used
