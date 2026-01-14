import streamlit as st
import requests
import re
from bs4 import BeautifulSoup

st.set_page_config(page_title="RAKUTEN N4 TEST", layout="centered")
st.title("RAKUTEN N4 TEST")

URL = "https://takarakuji.rakuten.co.jp/backnumber/numbers4_past/"

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

r = requests.get(URL, headers=headers, timeout=20)
st.write("status:", r.status_code)
st.write("content-type:", r.headers.get("content-type"))
st.write("len:", len(r.text))

# 楽天は通常UTF-8
r.encoding = r.apparent_encoding or "utf-8"
html = r.text

soup = BeautifulSoup(html, "html.parser")

# 1) ページ内テキストから「第xxxx回」「YYYY/MM/DD」「4桁」を1ブロックずつ拾う
text = soup.get_text("\n", strip=True)

# 開催回：第6896回
rounds = re.findall(r"第(\d+)回", text)
# 日付：2026/01/13
dates  = re.findall(r"\b(20\d{2}/\d{2}/\d{2})\b", text)
# 4桁数字（当せん番号の候補）
nums4  = re.findall(r"\b(\d{4})\b", text)

st.subheader("raw counts (debug)")
st.write("rounds:", len(rounds), "dates:", len(dates), "nums4:", len(nums4))

# 2) 画像の構造に合わせた“テーブル行”抽出（これが本命）
items = []
tables = soup.find_all("table")
for tb in tables:
    # テーブル内に「当せん番号」系があるやつだけ対象
    ttxt = tb.get_text(" ", strip=True)
    if ("当せん番号" not in ttxt) and ("当せん番号" not in ttxt) and ("当せん番号" not in ttxt):
        # 表記揺れがあっても拾いたいので条件はゆるめ
        if ("当せん" not in ttxt) and ("当選" not in ttxt):
            continue

    # “開催回 / 抽せん日 / 当せん番号”を同じブロックから抜く
    current_round = None
    current_date = None
    current_num = None

    for tr in tb.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not th or not td:
            continue
        k = th.get_text(" ", strip=True)
        v = td.get_text(" ", strip=True)

        if "開催回" in k or "回別" in k:
            m = re.search(r"第(\d+)回", v)
            if m:
                current_round = int(m.group(1))
        elif "抽せん日" in k or "抽選日" in k:
            m = re.search(r"(20\d{2}/\d{2}/\d{2})", v)
            if m:
                current_date = m.group(1)
        elif "当せん番号" in k or "当選番号" in k:
            m = re.search(r"\b(\d{4})\b", v)
            if m:
                current_num = m.group(1)

    if current_round and current_date and current_num:
        items.append({"round": current_round, "date": current_date, "num": current_num})

# 3) 重複を除いて最新順に並べる
uniq = {}
for it in items:
    uniq[it["round"]] = it
items2 = sorted(uniq.values(), key=lambda x: x["round"], reverse=True)

st.subheader("parsed results (top 15)")
st.write(items2[:15])

st.subheader("latest")
st.write(items2[0] if items2 else "NONE")
