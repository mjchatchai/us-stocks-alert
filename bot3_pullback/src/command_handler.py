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
import tempfile
import time
from typing import Dict, List, Optional
import requests
from dotenv import load_dotenv

# Ensure utf-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
CHARTS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "charts")


def save_config(cfg: Dict):
    """Atomic state persistence using tempfile and os.replace with Windows concurrency retry."""
    dir_name = os.path.dirname(os.path.abspath(CONFIG_PATH))
    os.makedirs(dir_name, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(dir=dir_name, text=True)
    replaced = False
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        max_attempts = 6
        backoff = 0.05
        for attempt in range(max_attempts):
            try:
                os.replace(temp_path, CONFIG_PATH)
                replaced = True
                break
            except PermissionError:
                if attempt == max_attempts - 1:
                    raise
                time.sleep(backoff)
                backoff *= 2
    finally:
        if not replaced and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


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
                tokens = text.split()
                cmd = tokens[0].lower() if tokens else ""

                if cmd in ("/start", "/help"):
                    help_msg = (
                        "🚀 <b>ยินดีต้อนรับสู่ US Trend Leader Pullback Bot (@US2_Pullback_bot)</b>\n"
                        "━━━━━━━━━━━━━━━━\n"
                        "คำสั่งที่สามารถใช้ได้:\n"
                        "• <code>/scan</code> - สั่งสแกนหุ้นตามกลยุทธ์ 4 ข้อทันที\n"
                        "• <code>/positions</code> - ดูหุ้นที่กำลังถืออยู่ในพอร์ต\n"
                        "• <code>/stat</code> - ดูผลตอบแทนและสถิติ Win Rate\n"
                        "• <code>/buy TICKER SHARES PRICE</code> - บันทึกเข้าพอร์ตแบบแมนนวล\n"
                        "• <code>/sell TICKER PRICE</code> - บันทึกปิดทำกำไร/ขายหุ้น\n"
                        "━━━━━━━━━━━━━━━━\n"
                        "📊 <i>ระบบจะสแกนหาจังหวะ Pullback และส่งสัญญาณพร้อมภาพกราฟและคำนวณขนาดไม้ให้ทุกเช้าครับ</i>"
                    )
                    self.send_message(chat_id, help_msg)

                elif cmd == "/scan":
                    self.send_message(chat_id, "⏳ <b>กำลังเริ่มสแกนหุ้นตามกลยุทธ์ 4 ขั้นตอน...</b>\nกรุณารอสักครู่ (ประมาณ 20-30 วินาที)")
                    from bot3_pullback.src.main import run_bot3_pipeline
                    run_bot3_pipeline()

                elif cmd in ("/positions", "/port"):
                    active_pos = cfg.get("active_positions", {})
                    if not active_pos:
                        self.send_message(chat_id, "💼 ขณะนี้ยังไม่มีหุ้นที่ถืออยู่ในพอร์ต Bot 3 ครับ")
                    else:
                        pos_text = "💼 <b>รายการหุ้นที่ถืออยู่ในพอร์ต Bot 3:</b>\n━━━━━━━━━━━━━━━━\n"
                        for tk, p in active_pos.items():
                            pos_text += (
                                f"• <b>${tk}</b>: {p['current_shares']} หุ้น (ทุน ${p['entry_price']:.2f})\n"
                                f"  🛑 SL: ${p['current_sl']:.2f} | 🎯 3R: ${p['target_3r']:.2f} | 🎯 5R: ${p['target_5r']:.2f}\n"
                            )
                        self.send_message(chat_id, pos_text)

                elif cmd in ("/stat", "/stats"):
                    history = cfg.get("trade_history", [])
                    active = cfg.get("active_positions", {})
                    total = len(history)
                    wins = [h for h in history if float(h.get("realized_pnl", 0)) > 0]
                    losses = [h for h in history if float(h.get("realized_pnl", 0)) <= 0]
                    win_rate = (len(wins) / total * 100.0) if total > 0 else 0.0
                    tot_r = sum(float(h.get("pnl_r", h.get("r_multiple", 0))) for h in history)
                    tot_pnl = sum(float(h.get("realized_pnl", 0)) for h in history)

                    win_rs = [float(h.get("pnl_r", h.get("r_multiple", 0))) for h in wins]
                    loss_rs = [float(h.get("pnl_r", h.get("r_multiple", 0))) for h in losses]
                    avg_win = (sum(win_rs) / len(win_rs)) if win_rs else 0.0
                    avg_loss = (sum(loss_rs) / len(loss_rs)) if loss_rs else 0.0

                    stat_msg = (
                        "📊 <b>BOT 3 FORWARD TEST PERFORMANCE</b>\n"
                        "━━━━━━━━━━━━━━━━\n"
                        f"• ออเดอร์ที่เปิดอยู่: <code>{len(active)} ตัว</code>\n"
                        f"• ไม้ปิดรอบทั้งหมด: <code>{total} ไม้</code>\n"
                        f"• Win Rate: <code>{win_rate:.1f}%</code> (ชนะ {len(wins)} / แพ้ {len(losses)})\n"
                        f"• กำไรสะสมสุทธิ: <code>{tot_r:+.2f}R</code> (<code>${tot_pnl:+,.2f}</code>)\n"
                        f"• ชนะเฉลี่ย: <code>+{avg_win:.2f}R</code> | แพ้เฉลี่ย: <code>{avg_loss:.2f}R</code>\n"
                        "━━━━━━━━━━━━━━━━"
                    )
                    self.send_message(chat_id, stat_msg)

                elif cmd == "/buy" or cmd.startswith("/buy@"):
                    if len(tokens) < 4:
                        self.send_message(
                            chat_id,
                            "⚠️ <b>รูปแบบคำสั่งไม่ถูกต้อง</b>\n"
                            "กรุณาใช้: <code>/buy TICKER SHARES PRICE</code>\n"
                            "ตัวอย่าง: <code>/buy AAPL 10 150.50</code>"
                        )
                    else:
                        ticker = tokens[1].upper().replace("$", "")
                        try:
                            shares = int(tokens[2])
                            price = float(tokens[3])
                            if shares <= 0 or price <= 0:
                                raise ValueError("Positive numbers required")

                            active_pos = cfg.setdefault("active_positions", {})
                            from datetime import datetime
                            today_str = datetime.now().strftime("%Y-%m-%d")

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
                                chat_id,
                                (
                                    f"✅ <b>บันทึกเข้าพอร์ตสำเร็จ! (/buy)</b>\n"
                                    f"• หุ้น: <b>${ticker}</b>\n"
                                    f"• จำนวน: <b>{shares} หุ้น</b> (ทุน ${price:.2f})\n"
                                    f"• เงินลงทุน: <b>${shares * price:,.2f}</b>\n"
                                    f"• Stop Loss: ${sl:.2f}\n"
                                    f"• เป้าหมาย 3R: ${target_3r:.2f} (ขาย 50% + ขยับ SL บังทุน)\n"
                                    f"• เป้าหมาย 5R: ${target_5r:.2f}\n\n"
                                    f"🤖 <i>Bot 3 จะคอยเฝ้าติดตามราคาและแจ้งเตือนตามกลยุทธ์ให้อัตโนมัติครับ!</i>"
                                )
                            )
                        except ValueError:
                            self.send_message(
                                chat_id,
                                "⚠️ <b>ข้อมูลตัวเลขไม่ถูกต้อง</b>\n"
                                "กรุณาระบุจำนวนหุ้น (จำนวนเต็มบวก) และราคา (มากกว่า 0)\n"
                                "เช่น: <code>/buy AAPL 10 150.50</code>"
                            )

                elif cmd == "/sell" or cmd.startswith("/sell@"):
                    if len(tokens) < 3:
                        self.send_message(
                            chat_id,
                            "⚠️ <b>รูปแบบคำสั่งไม่ถูกต้อง</b>\n"
                            "กรุณาใช้: <code>/sell TICKER PRICE</code>\n"
                            "ตัวอย่าง: <code>/sell AAPL 165.20</code>"
                        )
                    else:
                        ticker = tokens[1].upper().replace("$", "")
                        try:
                            sell_price = float(tokens[2])
                            if sell_price <= 0:
                                raise ValueError("Positive price required")

                            active_pos = cfg.get("active_positions", {})
                            if ticker not in active_pos:
                                self.send_message(
                                    chat_id,
                                    f"⚠️ ไม่พบหุ้น <b>${ticker}</b> ในพอร์ต Bot 3 (กรุณาตรวจสอบด้วย <code>/positions</code>)"
                                )
                            else:
                                from datetime import datetime
                                today_str = datetime.now().strftime("%Y-%m-%d")
                                pos = active_pos.pop(ticker)

                                entry_price = float(pos.get("entry_price", sell_price))
                                curr_shares = int(pos.get("current_shares", 0))
                                initial_shares = int(pos.get("initial_shares", curr_shares))
                                risk_per_share = float(pos.get("risk_per_share", 1.0))
                                prior_realized_pnl = float(pos.get("total_realized_pnl", 0.0))

                                close_pnl = round((sell_price - entry_price) * curr_shares, 2)
                                total_realized_pnl = round(prior_realized_pnl + close_pnl, 2)

                                initial_dollar_risk = initial_shares * risk_per_share if risk_per_share > 0 else 1.0
                                blended_r = round(total_realized_pnl / initial_dollar_risk, 2) if initial_dollar_risk > 0 else 0.0
                                pnl_pct = round(((sell_price - entry_price) / entry_price) * 100.0, 2) if entry_price > 0 else 0.0

                                trade_history = cfg.setdefault("trade_history", [])
                                record = {
                                    "ticker": ticker,
                                    "entry_price": entry_price,
                                    "entry_date": pos.get("entry_date", today_str),
                                    "exit_price": round(sell_price, 2),
                                    "exit_date": today_str,
                                    "shares": initial_shares,
                                    "shares_sold": curr_shares,
                                    "status": "CLOSED_MANUAL",
                                    "exit_reason": "Manual Telegram /sell",
                                    "realized_pnl": total_realized_pnl,
                                    "pnl_r": blended_r,
                                    "r_multiple": blended_r,
                                    "pnl_pct": pnl_pct,
                                }
                                trade_history.append(record)

                                outcome_emoji = "🟢" if total_realized_pnl >= 0 else "🔴"
                                self.send_message(
                                    chat_id,
                                    (
                                        f"✅ <b>บันทึกปิดออเดอร์สำเร็จ! (/sell)</b>\n"
                                        f"• หุ้น: <b>${ticker}</b>\n"
                                        f"• ขายที่ราคา: <b>${sell_price:.2f}</b> (ทุน ${entry_price:.2f})\n"
                                        f"• จำนวนที่ขาย: <b>{curr_shares} หุ้น</b>\n"
                                        f"• ผลตอบแทนรอบนี้: <b>{total_realized_pnl:+,.2f}$</b> ({outcome_emoji} <b>{blended_r:+.2f}R</b>)\n"
                                        f"• บันทึกลงใน Trade History เรียบร้อยครับ"
                                    )
                                )
                        except ValueError:
                            self.send_message(
                                chat_id,
                                "⚠️ <b>ราคาขายไม่ถูกต้อง</b>\n"
                                "กรุณาระบุราคาเป็นตัวเลขมากกว่า 0 เช่น: <code>/sell AAPL 165.20</code>"
                            )

        # Update last_telegram_update_id
        cfg["last_telegram_update_id"] = last_update_id
        save_config(cfg)


if __name__ == "__main__":
    handler = Bot3CommandHandler()
    handler.process_updates()
