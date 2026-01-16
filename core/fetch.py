import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "ja,en-US;q=0.9"
}

DATE_RE = re.compile(r"\d{4}/\d{2}/\d{2}")
ROUND_TAG_RE = re.compile(r"(第\d+回)")
YEN_RE = re.compile(r"[\d,]+円")
KUCHI_RE = re.compile(r"[\d,]+口")

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

def _extract_payout_from_lines(lines: list[str], digits: int) -> dict:
    payout = {}

    # 行走査で「ラベル→口→円」を拾う（楽天の表崩れに強い）
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

        # Numbers3 MINI
        if digits == 3 and t == "ミニ" and i + 2 < len(lines):
            payout["MINI"] = {"kuchi": lines[i+1], "yen": lines[i+2]}

    return payout

def parse_month_page(url: str, digits: int):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # スクリプト/スタイルが混じると数字拾いが壊れるので除去
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")
    # ここが本丸：第xxxx回 を “区切り” として分割して、回ごとの塊を確実に閉じる
    parts = ROUND_TAG_RE.split(text)

    items = []
    # parts: ["", "第6897回", ".....", "第6896回", ".....", ...]
    for idx in range(1, len(parts), 2):
        rtxt = parts[idx].strip()
        block = parts[idx + 1] if idx + 1 < len(parts) else ""

        rm = re.search(r"第(\d+)回", rtxt)
        if not rm:
            continue
        round_no = int(rm.group(1))

        # ブロック内の lines（表示の微妙な差に強い）
        lines = [l.strip() for l in block.splitlines() if l.strip()]

        # 日付：ブロック内で最初に出る YYYY/MM/DD を採用（同一行でもOK）
        dtxt = None
        m = DATE_RE.search(block)
        if m:
            dtxt = m.group(0)

        # 当せん番号：まず「当せん番号」の直後を狙い撃ち（同一行/改行どっちでもOK）
        ntxt = None
        m = re.search(rf"当せん番号\s*([0-9]{{{digits}}})", block)
        if m:
            ntxt = m.group(1)
        else:
            # ラベルが行として出るタイプのフォールバック
            for i in range(len(lines)):
                if "当せん番号" in lines[i]:
                    # 同じ行に数字がある場合
                    mm = re.search(rf"([0-9]{{{digits}}})", lines[i])
                    if mm:
                        ntxt = mm.group(1)
                        break
                    # 次行以降で最初に出る digits 桁を採用
                    for j in range(i + 1, min(i + 6, len(lines))):
                        mm = re.fullmatch(rf"[0-9]{{{digits}}}", lines[j])
                        if mm:
                            ntxt = lines[j]
                            break
                    if ntxt:
                        break

        # 払戻：従来通り lines から拾う
        payout = _extract_payout_from_lines(lines, digits)

        if dtxt and ntxt and re.fullmatch(rf"[0-9]{{{digits}}}", ntxt):
            items.append({
                "round": round_no,
                "date": dtxt,
                "num": ntxt,
                "payout": payout
            })

    # round 重複排除（最新優先）
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
