import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from core.config import HEADERS


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


def _parse_inline_payout(line: str) -> tuple[str, str] | None:
    """
    "ミニ 891口 7,600円" のような1行から ("891口","7,600円") を抜く
    """
    m = re.search(r"([0-9,]+口)\s*([0-9,]+円)", line)
    if not m:
        return None
    return m.group(1), m.group(2)


def parse_month_page(month_url: str, digits: int) -> list[dict]:
    r = requests.get(month_url, headers=HEADERS, timeout=20)
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    # 1行単位で取り出す（Rakutenはここに「直書き1行」が混ざる）
    lines = [ln.strip() for ln in soup.get_text("\n", strip=True).splitlines() if ln.strip()]

    items = []
    i = 0
    while i < len(lines):
        # "回号" または "開催回" 起点に対応（ページによって揺れる）
        if lines[i] in ("回号", "開催回") and i + 1 < len(lines):
            rtxt = lines[i + 1]
            dtxt = None
            ntxt = None
            payout = {}

            # このブロック終端（次の 回号/開催回 まで）
            end = len(lines)
            for t in range(i + 1, len(lines)):
                if lines[t] in ("回号", "開催回"):
                    end = t
                    break

            for j in range(i, end):
                # date / number
                if lines[j] in ("抽せん日", "抽選日") and j + 1 < end:
                    dtxt = lines[j + 1]
                if lines[j] in ("当せん番号", "当選番号") and j + 1 < end:
                    ntxt = lines[j + 1]

                # payout（1行直書き or 3トークン分割の両対応）
                def take(key: str, label: str):
                    # 直書き1行: "ラベル 〇口 〇円"
                    if lines[j].startswith(label):
                        got = _parse_inline_payout(lines[j])
                        if got:
                            payout[key] = {"kuchi": got[0], "yen": got[1]}
                            return

                    # 分割: "ラベル" / "〇口" / "〇円"
                    if lines[j] == label and j + 2 < end:
                        # 次行・次々行が「口」「円」形式でない場合もあるので軽くチェック
                        if re.search(r"[0-9,]+口$", lines[j + 1]) and re.search(r"[0-9,]+円$", lines[j + 2]):
                            payout[key] = {"kuchi": lines[j + 1], "yen": lines[j + 2]}

                take("STR", "ストレート")
                take("BOX", "ボックス")
                take("SET-S", "セット（ストレート）")
                take("SET-B", "セット（ボックス）")

                if digits == 3:
                    take("MINI", "ミニ")

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

            i = end
            continue

        i += 1

    uniq = {it["round"]: it for it in items}
    return sorted(uniq.values(), key=lambda x: x["round"], reverse=True)


def fetch_last_n_results(game: str, need: int = 20) -> tuple[list[dict], list[int]]:
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
