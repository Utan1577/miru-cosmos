import streamlit as st
import requests

st.set_page_config(page_title="MIZUHO CSV TEST (N4)", layout="centered")
st.title("MIZUHO CSV TEST (N4)")

# まずは「月次一覧のCSV」を試す（存在する可能性が高い）
# numbers4 は type="numbers4" で行けるはず、ダメなら "numbers" を試す
CANDIDATES = [
    "https://www.mizuhobank.co.jp/retail/takarakuji/numbers4/csv/numbers4.csv",
    "https://www.mizuhobank.co.jp/retail/takarakuji/numbers/csv/numbers.csv",
    "https://www.mizuhobank.co.jp/retail/takarakuji/numbers/csv/numbers4.csv",
]

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

for url in CANDIDATES:
    try:
        r = requests.get(url, headers=headers, timeout=20)
        st.subheader(url)
        st.write("status:", r.status_code, "content-type:", r.headers.get("content-type"), "len:", len(r.text))
        st.code(r.text[:600])
    except Exception as e:
        st.subheader(url)
        st.error(repr(e))
