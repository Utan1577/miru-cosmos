import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from collections import Counter

st.set_page_config(page_title="RAKUTEN -> TRENDS TEST", layout="centered")
st.title("RAKUTEN -> TRENDS TEST (N4)")

PAST_URL = "https://takarakuji.rakuten.co.jp/backnumber/numbers4_past/"

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

WINDMILL_MAP = {
    'n1': [0, 7, 4, 1, 8, 5, 2, 9, 6, 3],
    'n2': [0, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    'n3': [0, 3, 6, 9, 2, 5, 8, 1, 4, 7],
    'n4': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
}
INDEX_MAP = {k: {num: i for i, num in enumerate(arr)} for k, arr in WINDMILL_MAP.items()}

def parse_month_page(month_url):
    r = requests.get(month_url, headers=headers, timeout=20)
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    lines = [ln.strip() for ln in soup.get_text("\n", strip=True).splitlines() if ln.strip()]

    items = []
    i = 0
    while i < len(lines):
        if lines[i] == "開催回" and i+1 < len(lines):
            rtxt = lines[i+1]
            dtxt = None
            ntxt = None
            for j in range(i, min(i+40, len(lines)-1)):
                if lines[j] in ("抽せん日","抽選日") and j+1 < len(lines):
                    dtxt = lines[j+1]
                if lines[j] in ("当せん番号","当選番号") and j+1 < len(lines):
                    ntxt = lines[j+1]
                if dtxt and ntxt:
                    break

            rm = re.search(r"第(\d+)回", rtxt)
            nm = re.search(r"^\d{4}$", ntxt or "")
            dm = re.search(r"^\d{4}/\d{2}/\d{2}$", dtxt or "")
            if rm and nm and dm:
                items.append({"round": int(rm.group(1)), "date": dtxt, "num": ntxt})
        i += 1

    uniq = {it["round"]: it for it in items}
    return sorted(uniq.values(), key=lambda x: x["round"], reverse=True)

# 月URL一覧を拾う
r = requests.get(PAST_URL, headers=headers, timeout=20)
r.encoding = r.apparent_encoding or "utf-8"
soup = BeautifulSoup(r.text, "html.parser")

months = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    m = re.search(r"/backnumber/numbers4/(\d{6})/", href)
    if m:
        ym = int(m.group(1))
        months.append((ym, urljoin(PAST_URL, href)))
months = sorted(set(months))

# 最新20回を集める
need = 20
collected = {}
used = []
for ym, murl in reversed(months):
    used.append(ym)
    for it in parse_month_page(murl):
        collected[it["round"]] = it
    if len(collected) >= need:
        break

items = sorted(collected.values(), key=lambda x: x["round"], reverse=True)[:need]
st.write("months used:", used)
st.write("latest item:", items[0] if items else "NONE")

# history(20x4)作成
history = [[int(c) for c in it["num"]] for it in items]
last_val_str = items[0]["num"]

cols = ['n1','n2','n3','n4']
trends = {}
for i, col in enumerate(cols):
    spins = []
    for j in range(len(history)-1):
        curr_idx = INDEX_MAP[col][history[j][i]]
        prev_idx = INDEX_MAP[col][history[j+1][i]]
        spins.append((curr_idx - prev_idx) % 10)
    trends[col] = Counter(spins).most_common(1)[0][0] if spins else 0

st.subheader("OUTPUT")
st.write("last_val_str:", last_val_str)
st.write("history sample:", history[:5])
st.write("trends:", trends)
