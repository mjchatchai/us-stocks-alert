"""
Telegram Notifier for Bot 3 (Pullback & R-Multiple Strategy)
Handles:
- One-Page Compact Daily Report (แบบที่ 2 มินิมอล ไม่รกแชท ข้อความเดียวจบ)
- Take Profit (3R / 5R) & Trailing Stop Alerts
"""

import os
from typing import Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


class TelegramNotifier:
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def is_configured(self) -> bool:
        return bool(
            self.token
            and not self.token.startswith("YOUR_")
            and self.chat_id
            and not self.chat_id.startswith("YOUR_")
        )

    def send_message(
        self, text: str, reply_markup: Optional[Dict] = None, parse_mode: str = "HTML"
    ) -> bool:
        """Send formatted HTML message to Telegram chat."""
        if not self.is_configured():
            print(f"[Telegram Mock] Would send:\n{text}")
            return False

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": False,
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup

            res = requests.post(url, json=payload, timeout=10)
            return res.status_code == 200
        except Exception as e:
            print(f"Telegram send_message error: {e}")
            return False

    def send_compact_daily_report(self, summary: Dict, buy_signals: List[Dict]) -> bool:
        """
        Send a single, ultra-clean, structured trading card (แบบที่ 2 จัดระเบียบใหม่).
        No text wrapping glitches, monospace numbers, clean tree formatting.
        """
        date_str = summary.get("date", "")
        scanned = summary.get("total_scanned", 0)
        open_trades = summary.get("open_trades_count", 0)
        pullback_list = summary.get("pullback_tickers", [])

        text = (
            f"🚀 <b>US TREND PULLBACK REPORT</b>\n"
            f"📅 <i>{date_str}</i> • พอร์ต $10,000 (เสี่ยง $50/ไม้)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        buttons = []

        if buy_signals:
            text += f"🟢 <b>สัญญาณเข้าซื้อวันนี้ ({len(buy_signals)} ตัว):</b>\n\n"
            for s in buy_signals:
                p = s["plan"]
                t = p.ticker
                ep = p.entry_price
                sl = p.stop_loss
                sh = p.shares
                t3r = p.target_3r
                r_pct = p.risk_pct
                cap = p.capital_allocated

                text += (
                    f"🔹 <b>{t}</b>\n"
                    f"├ 💵 ทุนเข้า: <code>${ep:.2f}</code>\n"
                    f"├ 🛑 Stop Loss: <code>${sl:.2f}</code> (-{r_pct:.1f}%)\n"
                    f"├ 🎯 เป้าหมาย: <code>${t3r:.2f}</code> (3R)\n"
                    f"└ 📦 ซื้อตามงบ: <b>{sh} หุ้น</b> (~${cap:,.0f})\n\n"
                )
                buttons.append([
                    {"text": f"✅ ซื้อ {t} ({sh} หุ้น)", "callback_data": f"bot3_buy_{t}_{sh}_{ep:.2f}"},
                    {"text": f"📈 กราฟ {t}", "url": f"https://www.tradingview.com/chart/?symbol={t}"}
                ])
        else:
            text += "⚪ <b>สัญญาณเข้าซื้อวันนี้:</b> วันนี้ยังไม่มีหุ้นเบรกจุดซื้อใหม่\n\n"

        if pullback_list:
            top_pb = [f"<code>{tk}</code>" for tk in pullback_list[:6]]
            text += f"👀 <b>หุ้นจ่อแนวรับรอเบรก ({len(pullback_list)} ตัว):</b>\n{' • '.join(top_pb)}\n"

        text += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💼 ถือรันเทรนด์อยู่: <b>{open_trades} ตัว</b> | สแกนทั้งหมด: <b>{scanned} ตัว</b>\n"
            f"🌐 <i>ตรวจดูกราฟเทคนิคอลและสถานะเต็มได้ที่ Web Dashboard</i>"
        )

        reply_markup = {"inline_keyboard": buttons} if buttons else None
        return self.send_message(text, reply_markup=reply_markup)
