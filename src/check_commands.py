"""
Lightweight Telegram Command Checker
- Runs quickly to check if the user sent /buy, /sell, /add, /remove, or /scan in Telegram
- Updates config/watchlist.json immediately and replies in Telegram
- If the user sent /scan (or /report), triggers a full 3-zone scan immediately
"""

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.telegram_notifier import sync_telegram_commands
from src.scanner import run_scan


def main():
    full_config_path = os.path.join(PROJECT_ROOT, "config", "watchlist.json")
    with open(full_config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    cfg = sync_telegram_commands(cfg, full_config_path)

    if cfg.get("_trigger_scan_now"):
        print("[Command] พบคำสั่ง /scan -> เริ่มสแกนหุ้นทั้งหมดและส่งรายงานทันที...")
        run_scan()
    else:
        print("[Command] เช็คคำสั่ง Telegram เรียบร้อยแล้ว")


if __name__ == "__main__":
    main()
