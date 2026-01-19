import os
import shutil
from datetime import datetime

def backup_preds_daily(backup_dir: str = "data/backups") -> None:
    """
    Daily backup for prediction AND status store.
    - miru_preds.json (Predictions)
    - miru_status.json (Results/Credits)
    Copies data -> data/backups/filename_YYYY-MM-DD.json
    """
    # バックアップ対象のリスト（statusを追加）
    targets = ["data/miru_preds.json", "data/miru_status.json"]

    os.makedirs(backup_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    for src in targets:
        if not os.path.exists(src):
            continue
        
        filename = os.path.basename(src).replace(".json", "")
        dst = os.path.join(backup_dir, f"{filename}_{today}.json")

        # その日のバックアップがまだ無い場合のみコピー（1日1回）
        if not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass
