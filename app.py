import streamlit as st
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="MIZUHO PARSE TEST", layout="centered")
st.title("MIZUHO PARSE TEST (N4)")

url = "https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html"

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

r = requests.get(url, headers=headers, timeout=20)
st.write("status:", r.status_code, "len:", len(r.text))

# ★このページはUTF-8（文字化け対策の決定打）
r.encoding = "utf-8"

soup = BeautifulSoup(r.text, "html.parser")

latest_num = None
latest_round = None
latest_date = None

# 「抽せん数字」の行から数字を取る
for cell in soup.find_all(["th", "td"]):
    t = cell.get_text(" ", strip=True)
    if "抽せん数字" in t or "抽選数字" in t:
        tr = cell.find_parent("tr")
        if not tr:
            continue
        tds = tr.find_all("td")
        if not tds:
            continue
        v = tds[-1].get_text(strip=True).replace(" ", "")
        if v.isdigit() and len(v) == 4:
            latest_num = v

            table = tr.find_parent("table")
            if table:
                # 回別
                for c2 in table.find_all(["th", "td"]):
                    if "回別" in c2.get_text(" ", strip=True):
                        tr2 = c2.find_parent("tr")
                        if tr2:
                            td2 = tr2.find_all("td")
                            if td2:
                                latest_round = td2[-1].get_text(" ", strip=True)
                    if "抽せん日" in c2.get_text(" ", strip=True) or "抽選日" in c2.get_text(" ", strip=True):
                        tr3 = c2.find_parent("tr")
                        if tr3:
                            td3 = tr3.find_all("td")
                            if td3:
                                latest_date = td3[-1].get_text(" ", strip=True)
            break

st.subheader("RESULT")
st.write("round:", latest_round)
st.write("date :", latest_date)
st.write("num  :", latest_num)

# デバッグ：見つからなかった場合にページ内ヒント
if not latest_num:
    st.error("抽せん数字(4桁)が取れなかった。ページ構造が想定と違う可能性。")
    st.code(soup.get_text("\n", strip=True)[:1200])
