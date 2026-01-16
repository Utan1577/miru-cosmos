import re
import requests
from bs4 import BeautifulSoup

from core.config import HEADERS


TS4_URL = "https://ts4-net.com/result01.html"


def _norm_space(s: str) -> str:
    return (s or "").replace("\u3000", " ").strip()


def _pick(block_text: str, label: str):
    """
    例: "ミニ 291口 6,300円" のような行を拾う
    label の後ろに「xx口」「yy円」がどこかにあればOK
    """
    pat = rf"{re.escape(label)}\s+([0-9,]+口)\s+([0-9,]+円)"
    m = re.search(pat, block_text)
    if not m:
        return None
    return {"kuchi": m.group(1), "yen": m.group(2)}


def _parse_ts4_page():
    r = requests.get(TS4_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    text = _norm_space(soup.get_text("\n", strip=True))

    # ブロックは "#### 第6873回ナンバーズ当選番号" から始まる  [oai_citation:1‡ts4-net.com](https://ts4-net.com/result01.html)
    # ここは Markdown風にHTML内へ入ってるので、テキストで切るのが最も安定。
    blocks = re.split(r"####\s+第(\d+)回ナンバーズ当選番号", text)
    # blocks は ["前置き", round, block, round, block, ...] の形

    rounds = {}
    it = iter(blocks[1:])  # round から
    for rno_str, blk in zip(it, it):
        try:
            rno = int(rno_str)
        except:
            continue

        # 日付: "2025年12月8日(月)抽選" のような行がある  [oai_citation:2‡ts4-net.com](https://ts4-net.com/result01.html)
        dm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", blk)
        date = None
        if dm:
            y, mo, d = dm.group(1), int(dm.group(2)), int(dm.group(3))
            date = f"{y}/{mo:02d}/{d:02d}"

        # 当せん番号: "当選番号 ４１２" / "当選番号 ３４９３" のように N3/N4が同じ行に並ぶ  [oai_citation:3‡ts4-net.com](https://ts4-net.com/result01.html)
        nums = re.findall(r"当[せ選]ん番号\s*([0-9]{3,4})", blk.replace(" ", ""))
        n3 = nums[0] if len(nums) >= 1 else None
        n4 = nums[1] if len(nums) >= 2 else None

        # 払戻（N3側にミニがある）  [oai_citation:4‡ts4-net.com](https://ts4-net.com/result01.html)
        # ts4の表記は "セットストレート" / "セットボックス"（括弧なし）
        p3 = {}
        got = _pick(blk, "ストレート")
        if got: p3["STR"] = got
        got = _pick(blk, "ボックス")
        if got: p3["BOX"] = got
        got = _pick(blk, "セットストレート")
        if got: p3["SET-S"] = got
        got = _pick(blk, "セットボックス")
        if got: p3["SET-B"] = got
        got = _pick(blk, "ミニ")
        if got: p3["MINI"] = got

        # N4側は同じ行に2列分あるので、2個目のセットを拾う（同ラベルが2回出る）  [oai_citation:5‡ts4-net.com](https://ts4-net.com/result01.html)
        # 雑に「最初の4つをN3、次の4つをN4」として読む
        all_rows = re.findall(r"(ストレート|ボックス|セットストレート|セットボックス)\s+([0-9,]+口)\s+([0-9,]+円)", blk)
        p4 = {}
        if len(all_rows) >= 8:
            # 後半4つがN4
            tail = all_rows[4:8]
            for label, kuchi, yen in tail:
                key = {"ストレート": "STR", "ボックス": "BOX", "セットストレート": "SET-S", "セットボックス": "SET-B"}[label]
                p4[key] = {"kuchi": kuchi, "yen": yen}

        rounds[rno] = {
            "date": date,
            "n3": n3,
            "p3": p3,
            "n4": n4,
            "p4": p4,
        }

    return rounds


def fetch_last_n_results(game: str, need: int = 20):
    """
    app.py が期待している形式:
      return items, months_used
      items: [{"round": int, "date": "YYYY/MM/DD", "num": "345", "payout": {...}}, ...] (round desc)
    """
    data = _parse_ts4_page()

    items = []
    for rno, d in data.items():
        if game == "N3":
            if not d.get("n3"):
                continue
            items.append({
                "round": rno,
                "date": d.get("date") or "",
                "num": d["n3"],
                "payout": d.get("p3") or {},
            })
        elif game == "N4":
            if not d.get("n4"):
                continue
            items.append({
                "round": rno,
                "date": d.get("date") or "",
                "num": d["n4"],
                "payout": d.get("p4") or {},
            })
        else:
            raise ValueError("fetch_last_n_results supports N4/N3 only")

    items = sorted(items, key=lambda x: x["round"], reverse=True)[:need]
    # months_used は app.py で表示に使ってるだけならダミーでOK
    return items, [0]
