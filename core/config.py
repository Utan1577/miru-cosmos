import json
import os
import tempfile
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

# --- 【新機能】鉄壁の保存ロジック (Atomic Write) ---
def safe_save_json(data, filepath):
    """
    データを安全に保存する関数。
    1. データが空(None/Empty)なら保存せず中断（消失防止）
    2. 一時ファイル(.tmp)に書き込む
    3. 成功を確認してから元のファイルと入れ替える
    """
    if not data:
        # 空データによる上書き防止
        return False

    # 保存先ディレクトリの確保
    dir_name = os.path.dirname(filepath)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)

    # 一時ファイルを作成
    fd, temp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno()) # ディスクへの書き込みを保証

        # アトミックな置換（この瞬間に入れ替わる）
        os.replace(temp_path, filepath)
        return True

    except Exception:
        # 失敗時は一時ファイルを削除して元ファイルを守る
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False
