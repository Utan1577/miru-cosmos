import streamlit as st
import requests
import re
from bs4 import BeautifulSoup

st.set_page_config(page_title="RAKUTEN MONTH PARSE TEST", layout="centered")
st.title("RAKUTEN MONTH PARSE TEST (N4)")

MONTH_URL = "https://takarakuji.rakuten.co.jp/backnumber/numbers4/202601/"

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

r = requests.get(MONTH_URL, headers=headers, timeout=20)
st.write("status:", r.status_code, "len:", len(r.text))
r.encoding = r.apparent_encoding or "utf-8"

soup = BeautifulSoup(r.text, "html.parser")
lines = [ln.strip() for ln in soup.get_text("\n", strip=True).splitlines() if ln.strip()]

items = []
i = 0
while i < len(lines):
    # ブロック開始：開催回
    if lines[i] == "開催回" and i+1 < len(lines):
        rtxt = lines[i+1]  # 第6896回
        dtxt = None
        ntxt = None

        # 近傍から「抽せん日」「当せん番号」を拾う
        for j in range(i, min(i+40, len(lines)-1)):
            if lines[j] in ("抽せん日","抽選日") and j+1 < len(lines):
                dtxt = lines[j+1]  # 2026/01/13
            if lines[j] in ("当せん番号","当選番号") and j+1 < len(lines):
                ntxt = lines[j+1]  # 2699
            if dtxt and ntxt:
                break

        rm = re.search(r"第(\d+)回", rtxt)
        nm = re.search(r"^\d{4}$", ntxt or "")
        dm = re.search(r"^\d{4}/\d{2}/\d{2}$", dtxt or "")

        if rm and nm and dm:
            items.append({
                "round": int(rm.group(1)),
                "date": dtxt,
                "num": ntxt
            })

    i += 1

# 重複排除して最新順
uniq = {it["round"]: it for it in items}
items2 = sorted(uniq.values(), key=lambda x: x["round"], reverse=True)

st.subheader("parsed count")
st.write(len(items2))

st.subheader("parsed")
st.write(items2)

st.subheader("latest")
st.write(items2[0] if items2 else "NONE")
