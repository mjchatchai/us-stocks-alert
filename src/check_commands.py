"""
Lightweight Telegram Command Checker & Daily Morning Scan Trigger
- Runs every few minutes on GitHub Actions
- Checks if the user sent /buy, /sell, /add, /remove, or /scan in Telegram
- ALSO guarantees the daily morning report (after 08:40 Thai time, Mon-Sat) is sent even if GitHub skips a single-minute cron!
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.telegram_notifier import sync_telegram_commands
from src.scanner import run_scan

THAI_TZ = timezone(timedelta(hours=7))


def main():
    full_config_path = os.path.join(PROJECT_ROOT, "config", "watchlist.json")
    with open(full_config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    cfg = sync_telegram_commands(cfg, full_config_path)

    now_th = datetime.now(THAI_TZ)
    today_th = now_th.strftime("%Y-%m-%d")
    is_trading_morning = (now_th.weekday() < 6) and ((now_th.hour, now_th.minute) >= (8, 40))
    already_scanned_today = (cfg.get("last_daily_scan_date") == today_th)

    if cfg.get("_trigger_scan_now"):
        print("[Command] พบคำสั่ง /scan -> เริ่มสแกนหุ้นทั้งหมดและส่งรายงานทันที...")
        run_scan()
    elif is_trading_morning and not already_scanned_today:
        print(f"[Daily Auto-Scan] ถึงเวลาส่งรายงานประจำวัน ({today_th} {now_th.strftime('%H:%M')} น.) -> เริ่มสแกนทันที...")
        run_scan()
    else:
        print("[Command] เช็คคำสั่ง Telegram เรียบร้อยแล้ว")


if __name__ == "__main__":
    main()
