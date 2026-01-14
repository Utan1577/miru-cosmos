import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

st.set_page_config(page_title="MIZUHO JS SCAN", layout="centered")
st.title("MIZUHO JS SCAN")

PAGE = "https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html"

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

r = requests.get(PAGE, headers=headers, timeout=20)
st.write("page status:", r.status_code, "len:", len(r.text))
r.encoding = "utf-8"
soup = BeautifulSoup(r.text, "html.parser")

# ページから script src を全部拾う
script_srcs = []
for s in soup.find_all("script"):
    src = s.get("src")
    if src:
        script_srcs.append(urljoin(PAGE, src))

st.subheader("SCRIPT SRC")
for u in script_srcs:
    st.write(u)

# JS内のURL候補を抽出する正規表現
url_pat = re.compile(r"""(?P<u>https?://[^\s"'<>]+|/[^\s"'<>]+)""", re.I)

# “データ取得っぽい”キーワード
def looks_like_data(u: str) -> bool:
    u2 = u.lower()
    keys = ["json", "csv", "api", "ajax", "data", "numbers", "backnumber", "get", "list", "result"]
    return any(k in u2 for k in keys)

found = set()
hits_lines = []

st.subheader("SCAN JS...")

for js in script_srcs:
    try:
        jr = requests.get(js, headers=headers, timeout=20)
        st.write("js:", js, "status:", jr.status_code, "len:", len(jr.text))
        if jr.status_code != 200:
            continue

        # 文字化けしないように utf-8 を優先（ダメなら apparent）
        jr.encoding = "utf-8"
        text = jr.text

        # URL候補を拾う
        for m in url_pat.finditer(text):
            u = m.group("u")
            full = urljoin(js, u)
            if looks_like_data(full):
                found.add(full)

        # numbers4 / 抽せん / 当せん っぽい行を抜く（手がかり）
        for line in text.splitlines():
            if any(k in line.lower() for k in ["numbers4", "takarakuji", "kuji", "ajax", "json", "csv", "backnumber"]):
                if len(line) < 220:
                    hits_lines.append(line.strip())

    except Exception as e:
        st.error(f"{js} -> {repr(e)}")

st.subheader("ENDPOINT CANDIDATES")
for u in sorted(found):
    st.write(u)

st.subheader("HIT LINES (hints)")
# 長すぎると見づらいので先頭200行だけ
for line in hits_lines[:200]:
    st.code(line)
