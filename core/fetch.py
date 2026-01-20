import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9"
}

# --- Rakuten (N3/N4) 用の設定 ---
ROUND_HEAD_RE = re.compile(r"回号\s*第(\d+)回")
DATE_RE = re.compile(r"\d{4}/\d{2}/\d{2}")

# --- KC (MoneyPlan) 用の設定 ---
KC_BASE_URL = "https://qoochan.money-plan.net/round/{}/"
KC_HISTORY_URL = "https://qoochan.money-plan.net/history/"
FRUIT_MAP = {
    "リンゴ": "🍎", "ミカン": "🍊", "メロン": "🍈", "ブドウ": "🍇", "モモ": "🍑",
    "りんご": "🍎", "みかん": "🍊", "めろん": "🍈", "ぶどう": "🍇", "もも": "🍑"
}

# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------
def get_month_urls(past_url: str):
    try:
        r = requests.get(past_url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        urls = []
        for a in soup.select("a[href]"):
            href = a.get("href")
            if href and re.search(r"/\d{6}/$", href):
                ym = re.search(r"(\d{6})", href).group(1)
                urls.append((ym, urljoin(past_url, href)))

        return sorted(urls, reverse=True)
    except:
        return []

def _extract_payout_from_lines(lines, digits):
    payout = {}
    for i in range(len(lines)):
        t = lines[i]
        if t == "ストレート" and i + 2 < len(lines):
            payout["STR"] = {"kuchi": lines[i+1], "yen": lines[i+2]}
        if t == "ボックス" and i + 2 < len(lines):
            payout["BOX"] = {"kuchi": lines[i+1], "yen": lines[i+2]}
        if t.startswith("セット（ストレート）") and i + 2 < len(lines):
            payout["SET-S"] = {"kuchi": lines[i+1], "yen": lines[i+2]}
        if t.startswith("セット（ボックス）") and i + 2 < len(lines):
            payout["SET-B"] = {"kuchi": lines[i+1], "yen": lines[i+2]}
        if digits == 3 and t == "ミニ" and i + 2 < len(lines):
            payout["MINI"] = {"kuchi": lines[i+1], "yen": lines[i+2]}
    return payout

def parse_month_page(url: str, digits: int):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = soup.get_text("\n")
        matches = list(ROUND_HEAD_RE.finditer(text))
        items = []
        
        for idx, m in enumerate(matches):
            round_no = int(m.group(1))
            start = m.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            block = text[start:end]

            dm = DATE_RE.search(block)
            dtxt = dm.group(0) if dm else None
            nm = re.search(rf"当せん番号\s*([0-9]{{{digits}}})", block)
            ntxt = nm.group(1) if nm else None
            block_lines = [l.strip() for l in block.splitlines() if l.strip()]
            payout = _extract_payout_from_lines(block_lines, digits)

            if dtxt and ntxt and re.fullmatch(rf"[0-9]{{{digits}}}", ntxt):
                items.append({
                    "round": round_no,
                    "date": dtxt,
                    "num": ntxt,
                    "payout": payout
                })
        return items
    except:
        return []

# ---------------------------------------------------------
# KC Logic (MoneyPlan)
# ---------------------------------------------------------
def _get_latest_kc_round():
    """履歴ページから最新の回号を取得"""
    try:
        r = requests.get(KC_HISTORY_URL, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        max_round = 0
        for a in soup.find_all("a"):
            text = a.get_text(strip=True)
            m = re.search(r"第(\d+)回", text)
            if m:
                r_num = int(m.group(1))
                if r_num > max_round:
                    max_round = r_num
        return max_round
    except:
        return 0

def fetch_kc_results(need: int = 20):
    """
    クーちゃんの過去データをMoneyPlanから取得
    詳細ページをループして確実に取る
    """
    latest = _get_latest_kc_round()
    if latest == 0:
        return [], []

    items = []
    used = ["qoochan.money-plan.net"]
    
    # 最新回から指定回数分だけ過去へ遡る
    count = 0
    # 負荷軽減のため最大30回程度までチェック
    for i in range(latest, latest - need - 5, -1):
        if i < 1: break
        if count >= need: break
        
        url = KC_BASE_URL.format(i)
        try:
            r = requests.get(url, headers=HEADERS, timeout=5)
            if r.status_code != 200: continue
            
            r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, "html.parser")
            
            # 正しいデータが入っているテーブル(class="numbers")を探す
            # ページ下部の理論値テーブルを避けるため find で最初の一つだけ取る
            target_table = soup.find("table", class_="numbers")
            if not target_table: continue
            
            text = target_table.get_text(" ", strip=True)
            
            # 日付
            date_str = ""
            m_date = re.search(r"(\d{4}年\d{1,2}月\d{1,2}日)", text)
            if m_date: date_str = m_date.group(1)

            # 絵柄抽出 (テキストベース)
            fruits = []
            matches = re.findall(r"(リンゴ|ミカン|メロン|ブドウ|モモ)", text)
            for m in matches:
                if m in FRUIT_MAP:
                    fruits.append(FRUIT_MAP[m])
            # 最初の4つが当選絵柄
            result_fruits = fruits[:4]
            if len(result_fruits) != 4: continue
            
            # 金額抽出 (1等～3等)
            payout = {}
            for g in ["1等", "2等", "3等"]:
                m_yen = re.search(rf"{g}\D*?([\d,]+)\s*円", text)
                if m_yen:
                    payout[g] = {"yen": m_yen.group(1) + "円"}

            items.append({
                "round": i,
                "date": date_str,
                "num": "".join(result_fruits),
                "payout": payout
            })
            count += 1
            
        except:
            continue

    return items, used

# ---------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------
def fetch_last_n_results(game: str, need: int = 20):
    # KCの場合は専用ロジックへ分岐
    if game == "KC":
        return fetch_kc_results(need)
    
    # N4/N3は楽天ロジック
    elif game == "N4":
        past = "https://takarakuji.rakuten.co.jp/backnumber/numbers4_past/"
        digits = 4
    elif game == "N3":
        past = "https://takarakuji.rakuten.co.jp/backnumber/numbers3_past/"
        digits = 3
    else:
        # 未知のゲームなら空を返す
        return [], []

    months = get_month_urls(past)
    collected = {}
    used = []

    for ym, murl in months:
        used.append(ym)
        month_items = parse_month_page(murl, digits)
        for it in month_items:
            collected[it["round"]] = it
        if len(collected) >= need:
            break

    items = sorted(collected.values(), key=lambda x: x["round"], reverse=True)[:need]
    return items, used
