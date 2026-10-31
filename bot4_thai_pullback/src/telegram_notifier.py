"""
Telegram Notifier for Bot 4 (Thai Stocks Pullback & R-Multiple Strategy)
- Clean, structured One-Page Compact Report (แบบจัดระเบียบใหม่ สวยงาม ไม่ตกบรรทัด)
- Currency in Baht (฿)
- Board Lot Formatting (Multiples of 100 shares)
- Direct TradingView Links (SET:{TICKER})
"""

import html
import os
from typing import Dict, List, Optional
import requests

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass


def sanitize_html(text: str) -> str:
    """Safely escapes dynamic strings for Telegram HTML parse mode."""
    return html.escape(str(text))


class ThaiTelegramNotifier:
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

    def send_chunked_message(
        self,
        text: str,
        max_chunk: int = 4000,
        reply_markup: Optional[Dict] = None,
        parse_mode: str = "HTML",
    ) -> bool:
        """Splits message into blocks <= max_chunk characters to avoid Telegram 4096 limit."""
        if len(text) <= max_chunk:
            return self._send_raw(text, reply_markup=reply_markup, parse_mode=parse_mode)

        chunks = []
        lines = text.split("\n")
        curr = []
        curr_len = 0
        for line in lines:
            if curr_len + len(line) + 1 > max_chunk:
                chunks.append("\n".join(curr))
                curr = [line]
                curr_len = len(line)
            else:
                curr.append(line)
                curr_len += len(line) + 1
        if curr:
            chunks.append("\n".join(curr))

        success = True
        for i, chunk in enumerate(chunks):
            # Attach reply_markup only to the final chunk
            markup = reply_markup if i == len(chunks) - 1 else None
            res = self._send_raw(chunk, reply_markup=markup, parse_mode=parse_mode)
            if not res:
                success = False
        return success

    def _send_raw(
        self, text: str, reply_markup: Optional[Dict] = None, parse_mode: str = "HTML"
    ) -> bool:
        """Raw single message sender to Telegram chat."""
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

    def send_message(
        self, text: str, reply_markup: Optional[Dict] = None, parse_mode: str = "HTML"
    ) -> bool:
        """Send formatted HTML message to Telegram chat (with automatic chunking)."""
        if len(text) > 4000:
            return self.send_chunked_message(
                text, max_chunk=4000, reply_markup=reply_markup, parse_mode=parse_mode
            )
        return self._send_raw(text, reply_markup=reply_markup, parse_mode=parse_mode)

    def send_compact_daily_report(self, summary: dict, buy_signals: list):
        """Send concise, clean report with HTML escaping and chunking."""
        date_str = sanitize_html(summary.get("date", ""))
        pullback_list = summary.get("pullback_tickers", [])

        lines = [
            f"🎯 <b>TH PULLBACK REPORT</b> • <code>{date_str}</code>",
            "━━━━━━━━━━━━━━━━"
        ]

        buttons = []

        if buy_signals:
            for s in buy_signals:
                p = s["plan"]
                t = sanitize_html(p.ticker)
                raw_t = p.ticker
                ep = p.entry_price
                sl = p.stop_loss
                sh = p.shares
                t3r = p.target_3r
                t5r = getattr(p, "target_5r", 0.0)
                r_pct = p.risk_pct
                cap = p.capital_allocated

                lines.append(f"🟢 <b>{t}</b>")
                lines.append(f"├ เข้า: <code>{ep:.2f} ฿</code> | SL: <code>{sl:.2f} ฿</code> (-{r_pct:.1f}%)")
                lines.append(f"├ ซื้อ: <b>{sh:,} หุ้น</b> ({cap:,.0f} ฿)")
                if t5r > 0:
                    lines.append(f"└ เป้า: 3R <code>{t3r:.2f} ฿</code> | 5R <code>{t5r:.2f} ฿</code>")
                else:
                    lines.append(f"└ เป้า 3R: <code>{t3r:.2f} ฿</code>")
                lines.append("")

                tv_link = f"https://www.tradingview.com/chart/?symbol=SET%3A{raw_t}"
                buttons.append([
                    {"text": f"✅ ซื้อ {raw_t} ({sh:,} หุ้น)", "callback_data": f"bot4_buy_{raw_t}_{sh}_{ep:.2f}"},
                    {"text": f"📈 กราฟ {raw_t}", "url": tv_link}
                ])
        else:
            lines.append("⚪ <b>ไม่มีสัญญาณซื้อใหม่</b>")

        if pullback_list:
            top_pb = [f"<code>{sanitize_html(tk)}</code>" for tk in pullback_list[:6]]
            lines.append(f"👀 <b>จ่อแนวรับ:</b> {' • '.join(top_pb)}")

        reply_markup = {"inline_keyboard": buttons} if buttons else None
        return self.send_message("\n".join(lines).strip(), reply_markup=reply_markup)

