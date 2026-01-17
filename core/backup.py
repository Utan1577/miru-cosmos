import os
import shutil
from datetime import datetime

def backup_preds_daily(src: str = "data/miru_preds.json", backup_dir: str = "data/backups") -> None:
    """
    Daily backup for prediction store.
    - 1 backup per day
    - No overwrite for the same day
    - Copies data/miru_preds.json -> data/backups/miru_preds_YYYY-MM-DD.json
    """
    if not os.path.exists(src):
        return

    os.makedirs(backup_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    dst = os.path.join(backup_dir, f"miru_preds_{today}.json")

    if not os.path.exists(dst):
        shutil.copy2(src, dst)
