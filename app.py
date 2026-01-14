import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

st.set_page_config(page_title="RAKUTEN N4 DETAIL TEST", layout="centered")
st.title("RAKUTEN N4 DETAIL TEST")

LIST_URL = "https://takarakuji.rakuten.co.jp/backnumber/numbers4_past/"

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

# 1) 一覧ページ取得
r = requests.get(LIST_URL, headers=headers, timeout=20)
st.write("list status:", r.status_code, "len:", len(r.text))
r.encoding = r.apparent_encoding or "utf-8"
soup = BeautifulSoup(r.text, "html.parser")

# 2) detailリンク（fromto=xxxx_yyyy）を探す
detail_links = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    if "numbers4" in href and "fromto=" in href:
        detail_links.append(urljoin(LIST_URL, href))

# もし直接リンクが無い場合、別の形式も拾う（保険）
if not detail_links:
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "numbers4" in href and "detail" in href:
            detail_links.append(urljoin(LIST_URL, href))

detail_links = list(dict.fromkeys(detail_links))  # unique

st.subheader("detail link candidates")
st.write(detail_links[:10])

if not detail_links:
    st.error("detailリンクが見つからない（ページ構造が違う）。")
    st.stop()

# 3) とりあえず一番上を使う（最新の可能性が高い）
detail_url = detail_links[0]
st.success(f"detail_url: {detail_url}")

# 4) detailページ取得
d = requests.get(detail_url, headers=headers, timeout=20)
st.write("detail status:", d.status_code, "len:", len(d.text))
d.encoding = d.apparent_encoding or "utf-8"
dsoup = BeautifulSoup(d.text, "html.parser")

text = dsoup.get_text("\n", strip=True)

# 5) (開催回, 抽せん日, 当せん番号) をまとめて抜く
# 例: 開催回 第6896回 / 抽せん日 2026/01/13 / 当せん番号 2699
rounds = re.findall(r"第(\d+)+回", text)
dates  = re.findall(r"\b(20\d{2}/\d{2}/\d{2})\b", text)
nums4  = re.findall(r"\b(\d{4})\b", text)

st.subheader("raw counts (detail)")
st.write("rounds:", len(rounds), "dates:", len(dates), "nums4:", len(nums4))

# 6) テーブルブロックから “当せん番号” を抜く（本命）
items = []
tables = dsoup.find_all("table")
for tb in tables:
    ttxt = tb.get_text(" ", strip=True)
    if ("当せん番号" not in ttxt) and ("当選番号" not in ttxt):
        continue

    cur_round = None
    cur_date  = None
    cur_num   = None

    for tr in tb.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not th or not td:
            continue
        k = th.get_text(" ", strip=True)
        v = td.get_text(" ", strip=True)

        if "開催回" in k or "回別" in k:
            m = re.search(r"第(\d+)回", v)
            if m: cur_round = int(m.group(1))
        elif "抽せん日" in k or "抽選日" in k:
            m = re.search(r"(20\d{2}/\d{2}/\d{2})", v)
            if m: cur_date = m.group(1)
        elif "当せん番号" in k or "当選番号" in k:
            m = re.search(r"\b(\d{4})\b", v)
            if m: cur_num = m.group(1)

    if cur_round and cur_date and cur_num:
        items.append({"round": cur_round, "date": cur_date, "num": cur_num})

# 重複排除して最新順
uniq = {it["round"]: it for it in items}
items2 = sorted(uniq.values(), key=lambda x: x["round"], reverse=True)

st.subheader("parsed (top 20)")
st.write(items2[:20])

st.subheader("latest")
st.write(items2[0] if items2 else "NONE")

# 7) もし取れなかったら、ページの一部をデバッグ表示
if not items2:
    st.error("テーブル抽出で取れなかった。detailページの構造が違う可能性。")
    st.subheader("hint text (first 2000 chars)")
    st.code(text[:2000])
