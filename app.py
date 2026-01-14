import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

st.set_page_config(page_title="MIZUHO SOURCE SCAN", layout="centered")
st.title("MIZUHO SOURCE SCAN")

PAGE = "https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html"

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

r = requests.get(PAGE, headers=headers, timeout=20)
st.write("status:", r.status_code, "len:", len(r.text))
r.encoding = "utf-8"
html = r.text

soup = BeautifulSoup(html, "html.parser")

# 1) script src 一覧（まずこれが超重要）
script_srcs = []
for s in soup.find_all("script"):
    src = s.get("src")
    if src:
        script_srcs.append(urljoin(PAGE, src))

st.subheader("SCRIPT SRC")
if script_srcs:
    for u in script_srcs:
        st.write(u)
else:
    st.write("(no external script src found)")

# 2) HTML中のURLっぽいものを正規表現で抽出（json/csv/api等）
pattern = re.compile(r"""(?P<u>https?://[^\s"'<>]+|/[^\s"'<>]+)""")
found = set()
for m in pattern.finditer(html):
    u = m.group("u")
    if any(k in u.lower() for k in ["json", "csv", "api", "data", "ajax", "numbers", "backnumber"]):
        found.add(urljoin(PAGE, u))

st.subheader("URL CANDIDATES (json/csv/api/data/...)")
if found:
    for u in sorted(found):
        st.write(u)
else:
    st.write("(no candidates found)")

# 3) 念のため HTML から “抽せん数字一覧表” 周辺をそのまま表示（手がかり）
st.subheader("HINT TEXT (first 2000 chars of visible text)")
st.code(soup.get_text("\n", strip=True)[:2000])
