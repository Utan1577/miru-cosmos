import re
import requests
from bs4 import BeautifulSoup

TS4_URL = "https://ts4-net.com/result01.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


def _norm(s: str) -> str:
    return (s or "").replace("\u3000", " ").strip()


def _pick(block_text: str, label: str):
    """
    例（どれでも拾う）:
      ミニ 891口 7,600円
      ミニ, 891口, 7,600円
      ミニ（改行/空白/カンマ混在でもOK）
    label の後ろに「xx口」「yy円」がどこかに出れば拾う。
    """
    pat = rf"{re.escape(label)}[^0-9]*([0-9,]+口)[^0-9]*([0-9,]+円)"
    m = re.search(pat, block_text, flags=re.DOTALL)
    if not m:
        return None
    return {"kuchi": m.group(1), "yen": m.group(2)}


def _parse_ts4_page():
    """
    ts4-net から round ごとに
      - N3: 当せん番号 + STR/BOX/SET-S/SET-B/MINI
      - N4: 当せん番号 + STR/BOX/SET-S/SET-B
    を作る
    """
    r = requests.get(TS4_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    text = _norm(soup.get_text("\n", strip=True))

    # ブロック分割: #### 第6898回ナンバーズ当選番号
    parts = re.split(r"####\s+第(\d+)回ナンバーズ当選番号", text)

    rounds = {}
    it = iter(parts[1:])
    for rno_str, blk in zip(it, it):
        try:
            rno = int(rno_str)
        except Exception:
            continue

        # 日付（あれば）
        dm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", blk)
        date = ""
        if dm:
            y, mo, d = dm.group(1), int(dm.group(2)), int(dm.group(3))
            date = f"{y}/{mo:02d}/{d:02d}"

        # 当せん番号（N3→N4の順で並ぶ想定）
        nums = re.findall(r"当[せ選]ん番号\s*([0-9]{3,4})", blk.replace(" ", ""))
        n3 = nums[0] if len(nums) >= 1 else None
        n4 = nums[1] if len(nums) >= 2 else None

        # N3 payouts
        p3 = {}
        got = _pick(blk, "ストレート")
        if got:
            p3["STR"] = got
        got = _pick(blk, "ボックス")
        if got:
            p3["BOX"] = got
        got = _pick(blk, "セットストレート")
        if got:
            p3["SET-S"] = got
        got = _pick(blk, "セットボックス")
        if got:
            p3["SET-B"] = got
        got = _pick(blk, "ミニ")
        if got:
            p3["MINI"] = got

        # N4 payouts
        # 同ラベルが2列分あるので、全部拾って「後半4つ」をN4として採用
        all_rows = re.findall(
            r"(ストレート|ボックス|セットストレート|セットボックス)[^0-9]*([0-9,]+口)[^0-9]*([0-9,]+円)",
            blk,
            flags=re.DOTALL
        )
        p4 = {}
        if len(all_rows) >= 8:
            tail = all_rows[4:8]
            keymap = {
                "ストレート": "STR",
                "ボックス": "BOX",
                "セットストレート": "SET-S",
                "セットボックス": "SET-B",
            }
            for label, kuchi, yen in tail:
                p4[keymap[label]] = {"kuchi": kuchi, "yen": yen}

        rounds[rno] = {"date": date, "n3": n3, "p3": p3, "n4": n4, "p4": p4}

    return rounds


def fetch_last_n_results(game: str, need: int = 20):
    """
    app.py が期待する形式:
      return items, months_used
      items: [{"round": int, "date": "YYYY/MM/DD", "num": "345", "payout": {...}}, ...] (round desc)
    """
    data = _parse_ts4_page()

    items = []
    months = set()

    for rno, d in data.items():
        dt = d.get("date") or ""
        if dt and "/" in dt:
            try:
                months.add(int(dt.split("/")[1]))
            except Exception:
                pass

        if game == "N3":
            if not d.get("n3"):
                continue
            items.append({
                "round": rno,
                "date": dt,
                "num": d["n3"],
                "payout": d.get("p3") or {},
            })
        elif game == "N4":
            if not d.get("n4"):
                continue
            items.append({
                "round": rno,
                "date": dt,
                "num": d["n4"],
                "payout": d.get("p4") or {},
            })
        else:
            raise ValueError("fetch_last_n_results supports N4/N3 only")

    items = sorted(items, key=lambda x: x["round"], reverse=True)[:need]
    months_used = sorted(list(months)) if months else [0]
    return items, months_used
