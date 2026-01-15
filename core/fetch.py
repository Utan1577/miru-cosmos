import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from core.config import HEADERS

TS4_URL = "https://ts4-net.com/result01.html"


# -------------------------
# Rakuten (base for N3/N4)
# -------------------------
def get_month_urls(past_url: str) -> list[tuple[int, str]]:
    r = requests.get(past_url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    months = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.search(r"/backnumber/(numbers4|numbers3)/(\d{6})/", href)
        if m:
            ym = int(m.group(2))
            months.append((ym, urljoin(past_url, href)))

    months = sorted(set(months))
    return months


def _pick_payout(block_text: str, label: str):
    pat = rf"{re.escape(label)}.*?([0-9,]+口).*?([0-9,]+円)"
    m = re.search(pat, block_text, flags=re.DOTALL)
    if not m:
        return None
    return {"kuchi": m.group(1), "yen": m.group(2)}


def parse_month_page_rakuten(month_url: str, digits: int) -> list[dict]:
    r = requests.get(month_url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    lines = [ln.strip() for ln in soup.get_text("\n", strip=True).splitlines() if ln.strip()]
    items = []

    i = 0
    while i < len(lines):
        if lines[i] in ("開催回", "回号") and i + 1 < len(lines):
            rm = re.search(r"第(\d+)回", lines[i + 1])
            if not rm:
                i += 1
                continue
            round_no = int(rm.group(1))

            end = len(lines)
            for t in range(i + 2, len(lines)):
                if lines[t] in ("開催回", "回号"):
                    end = t
                    break

            block = lines[i:end]
            block_text = "\n".join(block)

            date = ""
            num = ""
            for j in range(0, len(block) - 1):
                if block[j] in ("抽せん日", "抽選日"):
                    m = re.search(r"\d{4}/\d{2}/\d{2}", block[j + 1])
                    if m:
                        date = m.group(0)
                if block[j] in ("当せん番号", "当選番号"):
                    m = re.search(rf"\b\d{{{digits}}}\b", block[j + 1].replace(" ", ""))
                    if m:
                        num = m.group(0)

            payout = {}
            got = _pick_payout(block_text, "ストレート")
            if got: payout["STR"] = got
            got = _pick_payout(block_text, "ボックス")
            if got: payout["BOX"] = got
            got = _pick_payout(block_text, "セット（ストレート）")
            if got: payout["SET-S"] = got
            got = _pick_payout(block_text, "セット（ボックス）")
            if got: payout["SET-B"] = got

            if date and num and len(num) == digits:
                items.append({"round": round_no, "date": date, "num": num, "payout": payout})

            i = end
            continue

        i += 1

    uniq = {it["round"]: it for it in items}
    return sorted(uniq.values(), key=lambda x: x["round"], reverse=True)


# -------------------------
# ts4-net (MINI only)
# -------------------------
def _parse_ts4_mini_map() -> dict[int, dict]:
    r = requests.get(TS4_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    txt = soup.get_text("\n", strip=True).replace("\u3000", " ")

    # ページ内の「第xxxx回」の位置を全部拾って、次の回までを1ブロックとして切る
    headers = [(int(m.group(1)), m.start()) for m in re.finditer(r"第(\d+)回", txt)]
    mini_map: dict[int, dict] = {}

    for idx, (rno, start) in enumerate(headers):
        end = headers[idx + 1][1] if idx + 1 < len(headers) else len(txt)
        blk = txt[start:end]

        # ブロック内の「ミニ 891口 7,600円」（改行/カンマ/空白混在OK）
        m = re.search(r"ミニ[^0-9]*([0-9,]+口)[^0-9]*([0-9,]+円)", blk, flags=re.DOTALL)
        if m:
            mini_map[rno] = {"kuchi": m.group(1), "yen": m.group(2)}

    return mini_map


# -------------------------
# public API
# -------------------------
def fetch_last_n_results(game: str, need: int = 20) -> tuple[list[dict], list[int]]:
    if game == "N4":
        past = "https://takarakuji.rakuten.co.jp/backnumber/numbers4_past/"
        digits = 4
   
