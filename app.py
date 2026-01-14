import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

st.set_page_config(page_title="RAKUTEN N4 MONTH -> DETAIL TEST", layout="centered")
st.title("RAKUTEN N4 MONTH -> DETAIL TEST")

MONTH_URL = "https://takarakuji.rakuten.co.jp/backnumber/numbers4/202601/"

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

def parse_detail_like(url):
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
            for j in range(i, min(i+30, len(lines)-1)):
                if lines[j] in ("抽せん日","抽選日") and j+1 < len(lines):
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

# 1) 月ページ取得
m = requests.get(MONTH_URL, headers=headers, timeout=20)
st.write("month status:", m.status_code, "len:", len(m.text))
m.encoding = m.apparent_encoding or "utf-8"
msoup = BeautifulSoup(m.text, "html.parser")

# 2) 月ページ内のリンクを抽出
links = []
for a in msoup.find_all("a", href=True):
    href = a["href"]
    label = a.get_text(" ", strip=True)
    full = urljoin(MONTH_URL, href)

    # まずは "numbers4_detail" を最優先
    if "numbers4_detail" in full:
        links.append(("numbers4_detail", full, label))
    # 次に "detail" を含むもの
    elif "detail" in full:
        links.append(("detail", full, label))

st.subheader("detail-ish links found (first 30)")
st.write(links[:30])

if not links:
    st.error("この月ページに detail 系リンクが見つからない。月ページ自体を直接パースする必要あり。")
    st.subheader("month hint text (first 2500 chars)")
    st.code(msoup.get_text("\n", strip=True)[:2500])
    st.stop()

# 3) linksの中で numbers4_detail を優先して選ぶ
pref = [x for x in links if x[0] == "numbers4_detail"]
target = pref[0] if pref else links[0]
kind, target_url, label = target

st.success(f"picked link ({kind}): {label}")
st.write("target_url:", target_url)

# 4) その先を detail パーサで読む
items = parse_detail_like(target_url)

st.subheader("parsed count")
st.write(len(items))
st.subheader("top (latest)")
st.write(items[0] if items else "NONE")
st.subheader("top 10")
st.write(items[:10])
