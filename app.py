import requests

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
    try:
        r = requests.get(url, headers=headers, timeout=20)
        print("\n===", url)
        print("status:", r.status_code)
        print("content-type:", r.headers.get("content-type"))
        print("len:", len(r.text))
        print("head:", r.text[:200].replace("\n"," ") )
    except Exception as e:
        print("\n===", url)
        print("ERROR:", repr(e))
