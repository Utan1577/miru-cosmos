import streamlit as st
import requests
import re

st.set_page_config(page_title="MIZUHO PREFIX FINDER", layout="centered")
st.title("MIZUHO PREFIX FINDER")

JS = "https://www.mizuhobank.co.jp/common2024/js/transfer/lottery.js"

txt = requests.get(JS, headers={"User-Agent":"Mozilla/5.0"}, timeout=20).text

# numbers / numbers3 / numbers4 の prefix を抜く
pat = re.compile(r"(numbers4|numbers3|numbers)\s*:\s*\{[^}]*?prefix\s*:\s*['\"]([^'\"]+)['\"]", re.S)
hits = pat.findall(txt)

st.write("hits:", hits)

# もし上で取れなければ prefix候補を全部出す
pat2 = re.compile(r"prefix\s*:\s*['\"]([^'\"]+)['\"]")
st.write("all prefixes:", sorted(set(pat2.findall(txt)))[:80])
