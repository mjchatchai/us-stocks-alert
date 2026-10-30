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

    def send_compact_daily_report(self, summary: dict, buy_signals: list):
        """Send concise, clean report."""
        date_str = summary.get("date", "")
        pullback_list = summary.get("pullback_tickers", [])

        lines = [
            f"🎯 <b>US PULLBACK REPORT</b> • <code>{date_str}</code>",
            "━━━━━━━━━━━━━━━━━━━━"
        ]

        buttons = []

        if buy_signals:
            for s in buy_signals:
                p = s["plan"]
                t = p.ticker
                ep = p.entry_price
                sl = p.stop_loss
                sh = p.shares
                t3r = p.target_3r
                r_pct = p.risk_pct
                cap = p.capital_allocated

                lines.append(f"🟢 <b>${t}</b>")
                lines.append(f"├ เข้า: <code>${ep:.2f}</code> | SL: <code>${sl:.2f}</code> (-{r_pct:.1f}%)")
                lines.append(f"├ ซื้อ: <b>{sh} sh</b> (${cap:,.0f})")
                lines.append(f"└ เป้า 3R: <code>${t3r:.2f}</code>")
                lines.append("")

                tv_link = f"https://www.tradingview.com/chart/?symbol={t}"
                buttons.append([
                    {"text": f"✅ ซื้อ ${t} ({sh} sh)", "callback_data": f"bot3_buy_{t}_{sh}_{ep:.2f}"},
                    {"text": f"📈 กราฟ ${t}", "url": tv_link}
                ])
        else:
            lines.append("⚪ <b>ไม่มีสัญญาณซื้อใหม่</b>")

        if pullback_list:
            top_pb = [f"<code>{tk}</code>" for tk in pullback_list[:6]]
            lines.append(f"👀 <b>จ่อแนวรับ:</b> {' • '.join(top_pb)}")

        reply_markup = {"inline_keyboard": buttons} if buttons else None
        return self.send_message("\n".join(lines).strip(), reply_markup=reply_markup)
