import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from core.config import HEADERS

# ------------------------------------------------------------
# Rakuten fetch helpers
# ------------------------------------------------------------
def get_month_urls(past_url: str) -> list[tuple[int, str]]:
    r = requests.get(past_url, headers=HEADERS, timeout=20)
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

def parse_month_page(month_url: str, digits: int) -> list[dict]:
    """
    Parse Rakuten month page text blocks:
      開催回 -> 第xxxx回
      抽せん日 -> YYYY/MM/DD
      当せん番号 -> digits
      (optionally payout lines)
    Returns list of dict sorted by round desc.
    """
    r = requests.get(month_url, headers=HEADERS, timeout=20)
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    lines = [ln.strip() for ln in soup.get_text("\n", strip=True).splitlines() if ln.strip()]

    items = []
    i = 0
    while i < len(lines):
        if lines[i] == "開催回" and i + 1 < len(lines):
            rtxt = lines[i + 1]
            dtxt = None
            ntxt = None
            payout = {}  # optional: STR/BOX/SET-S/SET-B
            # scan nearby
            # 次の「開催回」までをこの回のブロックとして走査する
            end = len(lines)
            for t in range(i + 1, len(lines)):
                if lines[t] == "開催回":
                    end = t
                    break
            for j in range(i, end):
                if lines[j] in ("抽せん日", "抽選日") and j + 1 < len(lines):
                    dtxt = lines[j + 1]
                if lines[j] in ("当せん番号", "当選番号") and j + 1 < len(lines):
                    ntxt = lines[j + 1]

                # payouts (N4 has 4 types; N3 may have fewer)
                if lines[j] == "ストレート" and j + 2 < len(lines):
                    # pattern: ストレート / xx口 / x円
                    payout["STR"] = {"kuchi": lines[j + 1], "yen": lines[j + 2]}
                if lines[j] == "ボックス" and j + 2 < len(lines):
                    payout["BOX"] = {"kuchi": lines[j + 1], "yen": lines[j + 2]}
                if lines[j].startswith("セット（ストレート）") and j + 2 < len(lines):
                    payout["SET-S"] = {"kuchi": lines[j + 1], "yen": lines[j + 2]}
                if lines[j].startswith("セット（ボックス）") and j + 2 < len(lines):
                    payout["SET-B"] = {"kuchi": lines[j + 1], "yen": lines[j + 2]}
                # Numbers3 ミニ（表記ゆらぎ対策）
                if (digits == 3) and ("ミニ" in lines[j]):
                    kuchi = ""
                    yen = ""
                    for k in range(j + 1, min(j + 12, len(lines))):
                        if (not kuchi) and lines[k].endswith("口"):
                            kuchi = lines[k]
                        if (not yen) and lines[k].endswith("円"):
                            yen = lines[k]
                    if kuchi and yen:
                        payout["MINI"] = {"kuchi": kuchi, "yen": yen}
                if dtxt and ntxt:
                    # don't break early because payouts might be slightly later,
                    # but stop if we already passed some payout lines and see next block.
                    pass

                #if j > i + 5 and lines[j] == "開催回":
                 #   break

            rm = re.search(r"第(\d+)回", rtxt or "")
            dm = re.search(r"^\d{4}/\d{2}/\d{2}$", dtxt or "")
            nm = re.search(r"^\d{" + str(digits) + r"}$", ntxt or "")

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

def fetch_last_n_results(game: str, need: int = 20) -> tuple[list[dict], list[int]]:
    """
    Returns (items, months_used). items sorted by round desc.
    """
    if game == "N4":
        past = "https://takarakuji.rakuten.co.jp/backnumber/numbers4_past/"
        digits = 4
    elif game == "N3":
        past = "https://takarakuji.rakuten.co.jp/backnumber/numbers3_past/"
        digits = 3
    else:
        raise ValueError("fetch_last_n_results supports N4/N3 only")

    months = get_month_urls(past)
    collected = {}
    used = []
    for ym, murl in reversed(months):
        used.append(ym)
        for it in parse_month_page(murl, digits):
            collected[it["round"]] = it
        if len(collected) >= need:
            break

    items = sorted(collected.values(), key=lambda x: x["round"], reverse=True)[:need]
    return items, used
