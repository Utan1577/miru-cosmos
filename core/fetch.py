import re
import requests
from bs4 import BeautifulSoup

from core.config import HEADERS

TS4_URL = "https://ts4-net.com/result01.html"


def _norm(s: str) -> str:
    return (s or "").replace("\u3000", " ").strip()


def _pick(block_text: str, label: str):
    """
    例（どれでも拾う）:
      ミニ 808口 5,300円
      ミニ, 808口, 5,300円
      ミニ 808口 5,300円（空白や改行だらけでもOK）
    """
    # 「label の後ろに、どこかで 〇口 と 〇円 が出ればOK」
    pat = rf"{re.escape(label)}[^0-9]*([0-9,]+口)[^0-9]*([0-9,]+円)"
    m = re.search(pat, block_text, flags=re.DOTALL)
    if not m:
        return None
    return {"kuchi": m.group(1), "yen": m.group(2)}


def _parse_ts4_page():
    r = requests.get(TS4_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    text = _norm(soup.get_text("\n", strip=True))

    # "#### 第6890回ナンバーズ当選番号" でブロック分割
    blocks = re.split(r"####\s+第(\d+)回ナンバーズ当選番号", text)

    rounds = {}
    it = iter(blocks[1:])
    for rno_str, blk in zip(it, it):
        try:
            rno = int(rno_str)
        except:
            continue

        # 日付
        dm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", blk)
        date = ""
        if dm:
            y, mo, d = dm.group(1), int(dm.group(2)), int(dm.group(3))
            date = f"{y}/{mo:02d}/{d:02d}"

        # 当せん番号（N3→N4の順で出る前提）
        nums = re.findall(r"当[せ選]ん番号\s*([0-9]{3,4})", blk.replace(" ", ""))
        n3 = nums[0] if len(nums) >= 1 else None
        n4 = nums[1] if len(nums) >= 2 else None

        # 払戻（N3）
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

        # 払戻（N4）: 同じラベルが2列分あるので、2回目側を拾う
        # まず全行を拾って、前半4つ=3桁側、後半4つ=4桁側 として読む
        all_rows = re.findall(
            r"(ストレート|ボックス|セットストレート|セットボックス)[^0-9]*([0-9,]+口)[^0-9]*([0-9,]+円)",
            blk,
            flags=re.DOTALL
        )
        p4 = {}
        if len(all_rows) >= 8:
            tail = all_rows[4:8]
            keymap = {"ストレート": "STR", "ボックス": "BOX", "セットストレート": "SET-S", "セットボックス": "SET-B"}
            for label, kuchi, yen in tail:
                p4[keymap[label]] = {"kuchi": kuchi, "yen": yen}

        rounds[rno] = {"date": date, "n3": n3, "p3": p3, "n4": n4, "p4": p4}

    return rounds


def fetch_last_n_results(game: str, need: int = 20):
    data = _parse_ts4_page()

    items = []
    for rno, d in data.items():
        if game == "N3":
            if not d.get("n3"):
                continue
            items.append({"round": rno, "date": d.get("date") or "", "num": d["n3"], "payout": d.get("p3") or {}})
        elif game == "N4":
            if not d.get("n4"):
                continue
            items.append({"round": rno, "date": d.get("date") or "", "num": d["n4"], "payout": d.get("p4") or {}})
        else:
            raise ValueError("fetch_last_n_results supports N4/N3 only")

    items = sorted(items, key=lambda x: x["round"], reverse=True)[:need]
    return items, [0]
