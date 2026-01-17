from datetime import datetime, timedelta, timezone

# 予想固定の保存は model.py 側の PRED_FILE=data/miru_preds.json が担当
# この STATUS_FILE は「UI状態（閲覧回号など）」専用にする
STATUS_FILE = "data/miru_status.json"

JST = timezone(timedelta(hours=9), "JST")

# --- UI/HTTP headers ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

# --- 【厳守】風車盤ロジック定数 ---
WINDMILL_MAP = {
    "n1": [0, 7, 4, 1, 8, 5, 2, 9, 6, 3],
    "n2": [0, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    "n3": [0, 3, 6, 9, 2, 5, 8, 1, 4, 7],
    "n4": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
}
INDEX_MAP = {k: {num: i for i, num in enumerate(arr)} for k, arr in WINDMILL_MAP.items()}
GRAVITY_SECTORS = [4, 5, 6]
ANTI_GRAVITY_SECTORS = [9, 0, 1]
