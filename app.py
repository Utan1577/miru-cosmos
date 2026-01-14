import streamlit as st
import requests
import re
from bs4 import BeautifulSoup

st.set_page_config(page_title="RAKUTEN N4 DETAIL PARSE v2", layout="centered")
st.title("RAKUTEN N4 DETAIL PARSE v2")

URL = "https://takarakuji.rakuten.co.jp/backnumber/numbers4_detail/0001-0020/"

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

r = requests.get(URL, headers=headers, timeout=20)
st.write("status:", r.status_code, "len:", len(r.text))
r.encoding = r.apparent_encoding or "utf-8"

soup = BeautifulSoup(r.text, "html.parser")
lines = [ln.strip() for ln in soup.get_text("\n", strip=True).splitlines() if ln.strip()]

def next_val(key, start=0):
    for i in range(start, len(lines)-1):
        if lines[i] == key:
            return lines[i+1], i+1
    return None, start

items = []
i = 0
while i < len(lines):
    # 「開催回」ブロックを起点に3点セット取る
    if lines[i] == "開催回":
        rtxt, j = next_val("開催回", i)
        dtxt, k = next_val("抽せん日", i)
        # ラベルが「ナンバーズ4」の場合に数字が次行
        ntxt, m = next_val("ナンバーズ4", i)

        if rtxt and dtxt and ntxt:
            rm = re.search(r"第(\d+)回", rtxt)
            dm = re.search(r"(20\d{2}|\d{4})/\d{2}/\d{2}", dtxt)  # 1994/10/07もOK
            nm = re.search(r"^\d{4}$", ntxt)  # 0097 もOK（4桁）
            if rm and dm and nm:
                items.append({
                    "round": int(rm.group(1)),
                    "date": dtxt,
                    "num": ntxt
                })
        i += 1
    else:
        i += 1

# 重複排除して整列
uniq = {it["round"]: it for it in items}
items2 = sorted(uniq.values(), key=lambda x: x["round"], reverse=True)

st.subheader("parsed count")
st.write(len(items2))

st.subheader("parsed (top 10)")
st.write(items2[:10])

st.subheader("latest in this page-range")
st.write(items2[0] if items2 else "NONE")
