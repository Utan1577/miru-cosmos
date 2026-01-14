import streamlit as st
import requests
import re
import time

st.set_page_config(page_title="MIZUHO PREFIX BRUTE", layout="centered")
st.title("MIZUHO PREFIX BRUTE (N4)")

NUMBERS_LIST = "https://www.mizuhobank.co.jp/retail/takarakuji/numbers/csv/numbers.csv"
BASE = "https://www.mizuhobank.co.jp/retail/takarakuji/numbers/csv/"

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

# 1) 最新回号をnumbers.csvから取る
r = requests.get(NUMBERS_LIST, headers=headers, timeout=20)
st.write("numbers.csv status:", r.status_code, "content-type:", r.headers.get("content-type"), "len:", len(r.text))

# Shift_JISなので明示
r.encoding = "shift_jis"
text = r.text

m = re.search(r"第(\d+)回", text)
if not m:
    st.error("numbers.csv から回号が取れない")
    st.stop()

round_no = int(m.group(1))
tail4 = f"{round_no % 10000:04d}"
st.success(f"latest round = {round_no} (tail4={tail4})")

# 2) prefix総当たり（A-Z）
cands = [chr(ord("A")+i) for i in range(26)]

found = None
tried = 0

prog = st.progress(0)
out = st.empty()

for i, p in enumerate(cands, start=1):
    tried += 1
    url = f"{BASE}A10{p}{tail4}.CSV"

    try:
        rr = requests.get(url, headers=headers, timeout=15)
        out.write(f"try {p}: {rr.status_code}  {url}")

        # 200なら当たり候補
        if rr.status_code == 200 and ("csv" in (rr.headers.get("content-type","").lower())):
            rr.encoding = rr.apparent_encoding or "shift_jis"
            head = rr.text[:600]
            found = (p, url, rr.headers.get("content-type"), head)
            break

    except Exception as e:
        out.write(f"try {p}: ERROR {repr(e)}")

    prog.progress(i/len(cands))
    time.sleep(0.2)  # 叩き過ぎ防止

if not found:
    st.error("A-Zでは見つからなかった。次は a-z / 0-9 を試す。")
else:
    p, url, ctype, head = found
    st.success(f"FOUND PREFIX = {p}")
    st.write("url:", url)
    st.write("content-type:", ctype)
    st.code(head)
