import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

st.set_page_config(page_title="RAKUTEN N4 LATEST RANGE TEST", layout="centered")
st.title("RAKUTEN N4 LATEST RANGE TEST")

LIST_URL = "https://takarakuji.rakuten.co.jp/backnumber/numbers4_past/"

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

def parse_detail_page(url):
    r = requests.get(url, headers=headers, timeout=20)
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    lines = [ln.strip() for ln in soup.get_text("\n", strip=True).splitlines() if ln.strip()]

    items = []
    i = 0
    while i < len(lines):
        if lines[i] == "開催回":
            # 次行：第xxxx回
            if i+1 < len(lines):
                rtxt = lines[i+1]
            else:
                i += 1
                continue

            # 抽せん日/ナンバーズ4 の位置を探す（近傍にある想定）
            dtxt = None
            ntxt = None
            for j in range(i, min(i+25, len(lines)-1)):
                if lines[j] == "抽せん日" and j+1 < len(lines):
                    dtxt = lines[j+1]
                if lines[j] == "ナンバーズ4" and j+1 < len(lines):
                    ntxt = lines[j+1]
                if dtxt and ntxt:
                    break

            rm = re.search(r"第(\d+)回", rtxt)
            nm = re.search(r"^\d{4}$", ntxt or "")
            if rm and dtxt and nm:
                items.append({
                    "round": int(rm.group(1)),
                    "date": dtxt,
                    "num": ntxt
                })
        i += 1

    uniq = {it["round"]: it for it in items}
    items2 = sorted(uniq.values(), key=lambda x: x["round"], reverse=True)
    return items2

# 1) 一覧ページ取得
r = requests.get(LIST_URL, headers=headers, timeout=20)
st.write("list status:", r.status_code, "len:", len(r.text))
r.encoding = r.apparent_encoding or "utf-8"
soup = BeautifulSoup(r.text, "html.parser")

# 2) numbers4_detail/xxxx-xxxx/ を拾う
ranges = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    m = re.search(r"/backnumber/numbers4_detail/(\d+)-(\d+)/", href)
    if m:
        start = int(m.group(1))
        end = int(m.group(2))
        full = urljoin(LIST_URL, href)
        ranges.append((end, start, full))

ranges = sorted(set(ranges))  # unique + sort

st.subheader("found ranges count")
st.write(len(ranges))

if not ranges:
    st.error("numbers4_detail のレンジURLが見つからない")
    st.stop()

# 3) “endが最大”のレンジを最新とする
end, start, latest_url = ranges[-1]
st.success(f"latest range: {start}-{end}")
st.write("latest_url:", latest_url)

# 4) 最新レンジページをパース（20件想定）
items = parse_detail_page(latest_url)

st.subheader("parsed count in latest range page")
st.write(len(items))

st.subheader("latest 10")
st.write(items[:10])

st.subheader("top (latest)")
st.write(items[0] if items else "NONE")
