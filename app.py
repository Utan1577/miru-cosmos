import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

st.set_page_config(page_title="RAKUTEN N4 LAST20 TEST", layout="centered")
st.title("RAKUTEN N4 LAST20 TEST")

PAST_URL = "https://takarakuji.rakuten.co.jp/backnumber/numbers4_past/"

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

def parse_month_page(month_url):
    r = requests.get(month_url, headers=headers, timeout=20)
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    lines = [ln.strip() for ln in soup.get_text("\n", strip=True).splitlines() if ln.strip()]

    items = []
    i = 0
    while i < len(lines):
        if lines[i] == "開催回" and i+1 < len(lines):
            rtxt = lines[i+1]
            dtxt = None
            ntxt = None
            for j in range(i, min(i+40, len(lines)-1)):
                if lines[j] in ("抽せん日","抽選日") and j+1 < len(lines):
                    dtxt = lines[j+1]
                if lines[j] in ("当せん番号","当選番号") and j+1 < len(lines):
                    ntxt = lines[j+1]
                if dtxt and ntxt:
                    break

            rm = re.search(r"第(\d+)回", rtxt)
            nm = re.search(r"^\d{4}$", ntxt or "")
            dm = re.search(r"^\d{4}/\d{2}/\d{2}$", dtxt or "")
            if rm and nm and dm:
                items.append({"round": int(rm.group(1)), "date": dtxt, "num": ntxt})
        i += 1

    uniq = {it["round"]: it for it in items}
    return sorted(uniq.values(), key=lambda x: x["round"], reverse=True)

# 1) pastページから「月URL（/backnumber/numbers4/YYYYMM/）」を全部拾う
r = requests.get(PAST_URL, headers=headers, timeout=20)
r.encoding = r.apparent_encoding or "utf-8"
soup = BeautifulSoup(r.text, "html.parser")

months = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    m = re.search(r"/backnumber/numbers4/(\d{6})/", href)
    if m:
        ym = int(m.group(1))
        months.append((ym, urljoin(PAST_URL, href)))

months = sorted(set(months))  # unique + sort
st.write("months found:", len(months))
st.write("latest month:", months[-1][0] if months else "NONE")

if not months:
    st.error("月URLが見つからない")
    st.stop()

# 2) 最新月→前月→…と辿って直近20回ぶん集める
need = 20
collected = {}  # round -> item
month_used = []

for ym, murl in reversed(months):
    month_used.append((ym, murl))
    items = parse_month_page(murl)
    for it in items:
        collected[it["round"]] = it
    if len(collected) >= need:
        break

items2 = sorted(collected.values(), key=lambda x: x["round"], reverse=True)[:need]

st.subheader("months used")
st.write(month_used)

st.subheader("last 20 (or less if not enough months)")
st.write(items2)

st.subheader("latest")
st.write(items2[0] if items2 else "NONE")
