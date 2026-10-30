"""
Command & Callback Query Handler for Bot 3 (@US2_Pullback_bot)
Handles:
- Button click: bot3_chart_<TICKER> -> Sends high-res chart document + TradingView link
- Button click: bot3_buy_<TICKER>_<SHARES>_<PRICE> -> Saves trade to active_positions in config.json
- Commands: /start, /help, /scan, /stat, /positions
"""

import json
import os
import sys
from typing import Dict, List, Optional
import requests
from dotenv import load_dotenv

# Ensure utf-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
CHARTS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "charts")


class Bot3CommandHandler:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def answer_callback_query(self, query_id: str, text: str = "รับคำสั่งเรียบร้อยครับ!"):
        try:
            url = f"{self.base_url}/answerCallbackQuery"
            requests.post(url, json={"callback_query_id": query_id, "text": text}, timeout=10)
        except Exception as e:
            print(f"Error answering callback query: {e}")

    def send_message(self, chat_id: str, text: str, reply_markup=None):
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            if reply_markup:
                payload["reply_markup"] = reply_markup
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Error sending message: {e}")

    def send_document(self, chat_id: str, file_path: str, caption: str = ""):
        """Send high-res uncompressed image as document."""
        try:
            url = f"{self.base_url}/sendDocument"
            with open(file_path, "rb") as f:
                requests.post(
                    url,
                    data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                    files={"document": f},
                    timeout=25,
                )
        except Exception as e:
            print(f"Error sending document: {e}")

    def process_updates(self):
        """Fetch and process all pending updates from Telegram."""
        if not self.token:
            print("Missing bot token")
            return

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        last_update_id = int(cfg.get("last_telegram_update_id", 0))
        url = f"{self.base_url}/getUpdates"
        params = {"offset": last_update_id + 1, "timeout": 5}

        try:
            res = requests.get(url, params=params, timeout=15)
            updates = res.json().get("result", [])
        except Exception as e:
            print(f"Error getting updates: {e}")
            return

        if not updates:
            print("No new updates.")
            return

        print(f"Processing {len(updates)} updates...")
        for upd in updates:
            upd_id = upd["update_id"]
            if upd_id > last_update_id:
                last_update_id = upd_id

            # 1. Handle Inline Button Click (callback_query)
            if "callback_query" in upd:
                cb = upd["callback_query"]
                cb_id = cb["id"]
                data = cb.get("data", "")
                chat_id = str(cb.get("message", {}).get("chat", {}).get("id", self.chat_id))

                if data.startswith("bot3_chart_"):
                    ticker = data.replace("bot3_chart_", "").upper()
                    self.answer_callback_query(cb_id, f"📊 กำลังเปิดกราฟชัด ${ticker}...")
                    
                    chart_path = os.path.join(CHARTS_DIR, f"{ticker}.png")
                    tv_link = f"https://www.tradingview.com/chart/?symbol={ticker}"
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": f"📈 เปิดดูกราฟสดบน TradingView (${ticker})", "url": tv_link}]
                        ]
                    }

                    if os.path.exists(chart_path):
                        self.send_document(
                            chat_id=chat_id,
                            file_path=chart_path,
                            caption=f"📊 <b>ภาพกราฟความละเอียดสูง (HD): ${ticker}</b>\nแนวรับ EMA 9/21/50, AVWAP และระดับ Stop Loss / 3R / 5R",
                        )
                    else:
                        self.send_message(
                            chat_id=chat_id,
                            text=f"📊 ดูกราฟแบบ Interactive บน TradingView ได้ที่ลิงก์ด้านล่าง:",
                            reply_markup=keyboard,
                        )

                elif data.startswith("bot3_buy_"):
                    # Format: bot3_buy_TICKER_SHARES_PRICE
                    parts = data.split("_")
                    if len(parts) >= 5:
                        ticker = parts[2].upper()
                        shares = int(parts[3])
                        price = float(parts[4])

                        self.answer_callback_query(cb_id, f"✅ บันทึกซื้อ {shares} หุ้น ${ticker} เรียบร้อย!")

                        # Add to active_positions in config
                        active_pos = cfg.setdefault("active_positions", {})
                        from datetime import datetime
                        today_str = datetime.now().strftime("%Y-%m-%d")

                        # Calculate default targets if not present
                        # 1R approx 2% if not known
                        sl = round(price * 0.98, 2)
                        r1 = round(price - sl, 2)
                        target_3r = round(price + (3 * r1), 2)
                        target_5r = round(price + (5 * r1), 2)

                        active_pos[ticker] = {
                            "ticker": ticker,
                            "entry_price": price,
                            "entry_date": today_str,
                            "initial_shares": shares,
                            "current_shares": shares,
                            "initial_sl": sl,
                            "current_sl": sl,
                            "risk_per_share": r1,
                            "target_3r": target_3r,
                            "target_5r": target_5r,
                            "tp1_hit": False,
                            "tp2_hit": False,
                            "total_realized_pnl": 0.0,
                            "status": "OPEN",
                        }

                        self.send_message(
                            chat_id=chat_id,
                            text=(
                                f"✅ <b>บันทึกเข้าพอร์ตสำเร็จ!</b>\n"
                                f"• หุ้น: <b>${ticker}</b>\n"
                                f"• จำนวน: <b>{shares} หุ้น</b> (ทุน ${price:.2f})\n"
                                f"• เงินลงทุน: <b>${shares * price:,.2f}</b>\n"
                                f"• Stop Loss: ${sl:.2f}\n"
                                f"• เป้าหมาย 3R: ${target_3r:.2f} (ขาย 50% + ขยับ SL บังทุน)\n"
                                f"• เป้าหมาย 5R: ${target_5r:.2f}\n\n"
                                f"🤖 <i>Bot 3 จะคอยเฝ้าติดตามราคาและแจ้งเตือนเมื่อถึงเป้าหมายหรือหลุด EMA 9 ให้อัตโนมัติครับ!</i>"
                            ),
                        )

            # 2. Handle Text Commands
            elif "message" in upd and "text" in upd["message"]:
                msg = upd["message"]
                text = msg.get("text", "").strip()
                chat_id = str(msg.get("chat", {}).get("id", self.chat_id))

                if text in ("/start", "/help"):
                    help_msg = (
                        "🚀 <b>ยินดีต้อนรับสู่ US Trend Leader Pullback Bot (@US2_Pullback_bot)</b>\n"
                        "━━━━━━━━━━━━━━━━━━━\n"
                        "คำสั่งที่สามารถใช้ได้:\n"
                        "• <code>/scan</code> - สั่งสแกนหุ้นตามกลยุทธ์ 4 ข้อทันที\n"
                        "• <code>/positions</code> - ดูหุ้นที่กำลังถืออยู่ในพอร์ต\n"
                        "• <code>/stat</code> - ดูผลตอบแทนและสถิติ Win Rate\n"
                        "• <code>/buy TICKER SHARES PRICE</code> - บันทึกเข้าพอร์ตแบบแมนนวล\n"
                        "• <code>/sell TICKER PRICE</code> - บันทึกปิดทำกำไร/ขายหุ้น\n"
                        "━━━━━━━━━━━━━━━━━━━\n"
                        "📊 <i>ระบบจะสแกนหาจังหวะ Pullback และส่งสัญญาณพร้อมภาพกราฟและคำนวณขนาดไม้ให้ทุกเช้าครับ</i>"
                    )
                    self.send_message(chat_id, help_msg)

                elif text == "/scan":
                    self.send_message(chat_id, "⏳ <b>กำลังเริ่มสแกนหุ้นตามกลยุทธ์ 4 ขั้นตอน...</b>\nกรุณารอสักครู่ (ประมาณ 20-30 วินาที)")
                    from bot3_pullback.src.main import run_bot3_pipeline
                    run_bot3_pipeline()

                elif text in ("/positions", "/port"):
                    active_pos = cfg.get("active_positions", {})
                    if not active_pos:
                        self.send_message(chat_id, "💼 ขณะนี้ยังไม่มีหุ้นที่ถืออยู่ในพอร์ต Bot 3 ครับ")
                    else:
                        pos_text = "💼 <b>รายการหุ้นที่ถืออยู่ในพอร์ต Bot 3:</b>\n━━━━━━━━━━━━━━━━━━━\n"
                        for tk, p in active_pos.items():
                            pos_text += (
                                f"• <b>${tk}</b>: {p['current_shares']} หุ้น (ทุน ${p['entry_price']:.2f})\n"
                                f"  🛑 SL: ${p['current_sl']:.2f} | 🎯 3R: ${p['target_3r']:.2f} | 🎯 5R: ${p['target_5r']:.2f}\n"
                            )
                        self.send_message(chat_id, pos_text)

        # Update last_telegram_update_id
        cfg["last_telegram_update_id"] = last_update_id
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    handler = Bot3CommandHandler()
    handler.process_updates()
