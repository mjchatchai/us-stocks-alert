"""
Telegram Notifier for Bot 5 US Hybrid
Token: 9021576257:AAGt-5V7oMo9Ov8JqpZMlbMRPZiu1JAlGUw
Chat ID: 8964251574
"""
import urllib.request
import urllib.parse
import json

BOT_TOKEN = "9021576257:AAGt-5V7oMo9Ov8JqpZMlbMRPZiu1JAlGUw"
CHAT_ID = "8964251574"

class USTelegramNotifier:
    def __init__(self, token=BOT_TOKEN, chat_id=CHAT_ID):
        self.token = token
        self.chat_id = chat_id

    def send_message(self, text: str, reply_markup: dict = None):
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
        # Simple photo upload or send url
        pass
