import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

st.set_page_config(page_title="RAKUTEN N4 REAL LATEST TEST", layout="centered")
st.title("RAKUTEN N4 REAL LATEST TEST")

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
        if lines[i] == "開催回" and i+1 < len(lines):
            rtxt = lines[i+1]
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
                items.append({"round": int(rm.group(1)), "date": dtxt, "num": ntxt})
        i += 1

    uniq = {it["round"]: it for it in items}
    return sorted(uniq.values(), key=lambda x: x["round"], reverse=True)

# 1) 一覧取得
r = requests.get(LIST_URL, headers=headers, timeout=20)
st.write("list status:", r.status_code, "len:", len(r.text))
r.encoding = r.apparent_encoding or "utf-8"
soup = BeautifulSoup(r.text, "html.parser")

# 2) まず「第xxxx回〜第yyyy回」を含むリンクを探す（これが最新）
cand = []
for a in soup.find_all("a", href=True):
    label = a.get_text(" ", strip=True)
    m = re.search(r"第(\d+)回～第(\d+)回", label)
    if m:
        start = int(m.group(1))
        end = int(m.group(2))
        cand.append((end, start, urljoin(LIST_URL, a["href"]), label))

cand = sorted(cand)
st.subheader("range-link candidates (top 10 by end)")
st.write(cand[-10:])

if not cand:
    st.error("『第xxxx回～第yyyy回』リンクが見つからない")
    st.stop()

end, start, latest_url, label = cand[-1]
st.success(f"picked: {label}")
st.write("latest_url:", latest_url)

# 3) そのリンク先をパース
items = parse_detail_page(latest_url)
st.subheader("parsed count")
st.write(len(items))
st.subheader("top (latest)")
st.write(items[0] if items else "NONE")
st.subheader("top 10")
st.write(items[:10])
