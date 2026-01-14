import streamlit as st
import requests

st.set_page_config(page_title="MIZUHO TEST", layout="centered")
st.title("MIZUHO TEST")

URLS = [
    "https://www.mizuhobank.co.jp/takarakuji/numbers/numbers4/index.html",
    "https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html",
]

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

for url in URLS:
    st.subheader(url)
    try:
        r = requests.get(url, headers=headers, timeout=20)
        st.write("status:", r.status_code)
        st.write("content-type:", r.headers.get("content-type"))
        st.write("len:", len(r.text))
        st.code(r.text[:500], language="html")
    except Exception as e:
        st.error(repr(e))
