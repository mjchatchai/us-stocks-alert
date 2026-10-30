"""
Telegram Notifier for Bot 5 Thai Hybrid
"""
import os
import urllib.request
import urllib.parse
import json

class ThaiTelegramNotifier:
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    def send_message(self, text: str, reply_markup: dict = None):
        if not self.token or not self.chat_id:
            print("[Telegram Mock] Would send:\n", text)
            return None

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print("Telegram send_message error:", e)
            return None

    def send_photo(self, photo_path: str, caption: str = ""):
        pass
