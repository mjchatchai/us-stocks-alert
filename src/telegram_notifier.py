"""
Telegram Bot Notifier & Command Handler for US Stock 6-Button Strategy

Supports:
1. Reading user commands from Telegram (/buy, /sell, /stat, /add, /remove, /scan) and inline button clicks
2. Recording completed 6-Button trades into backend statistics (trade_history) for /stat review
3. Sending the 3-Zone daily 6-Button report:
   - 💼 โซนที่ 1: หุ้นในพอร์ตกระดุม 6 เม็ด (สั่งซื้อแล้ว — โชว์ % กำไร/ขาดทุน และรอจังหวะขายออกเมื่อครบ 6 เม็ดแดง)
   - 🟢 โซนที่ 2: Watchlist ขาขึ้น (KDJ เขียว — รอจังหวะเข้าซื้อเมื่อครบ 6 เม็ดเขียว)
   - 🔴 โซนที่ 3: Watchlist ขาลง (KDJ แดง — พักตัว/ขาลง)
4. Sending individual stock chart images with inline action buttons
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests


def _load_dotenv_if_present() -> None:
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() not in os.environ:
                        os.environ[k.strip()] = v.strip()


_load_dotenv_if_present()


def _fetch_latest_price_us(ticker: str) -> float:
    try:
        import yfinance as yf
        df = yf.Ticker(ticker.strip().upper()).history(period="5d", interval="1d", auto_adjust=False)
        if df is not None and not df.empty:
            return round(float(df["Close"].iloc[-1]), 2)
    except Exception as exc:
        print(f"[PriceFetch] ไม่สามารถดึงราคาล่าสุดของ {ticker}: {exc}")
    return 0.0


def _calc_days_held(buy_date_str: str, sell_date_str: str) -> int:
    try:
        d1 = datetime.strptime(buy_date_str, "%Y-%m-%d").date()
        d2 = datetime.strptime(sell_date_str, "%Y-%m-%d").date()
        return max(0, (d2 - d1).days)
    except Exception:
        return 0


def format_stat_message(cfg: Dict[str, Any]) -> str:
    history: List[Dict[str, Any]] = cfg.get("trade_history", [])
    portfolio: Dict[str, Dict[str, Any]] = cfg.get("portfolio", {})

    lines = [
        "📊 <b>สถิติผลการเทรดด้วยกระดุม 6 เม็ด (US Stocks - Bot 1)</b>",
        "━━━━━━━━━━━━━━━━━━",
    ]

    if not history:
        lines.append("📁 <b>ประวัติที่ปิดรอบแล้ว (Closed Trades):</b> <i>(ยังไม่มีประวัติการขายปิดรอบ)</i>")
    else:
        total = len(history)
        wins = [t for t in history if float(t.get("pnl_r", t.get("pnl_pct", 0.0))) > 0]
        losses = [t for t in history if float(t.get("pnl_r", t.get("pnl_pct", 0.0))) <= 0]
        win_rate = (len(wins) / total) * 100.0 if total > 0 else 0.0

        total_r = sum(float(t.get("pnl_r", t.get("r_multiple", 0.0))) for t in history)
        win_rs = [float(t.get("pnl_r", t.get("r_multiple", 0.0))) for t in wins]
        loss_rs = [float(t.get("pnl_r", t.get("r_multiple", 0.0))) for t in losses]
        avg_win_r = sum(win_rs) / len(win_rs) if win_rs else 0.0
        avg_loss_r = sum(loss_rs) / len(loss_rs) if loss_rs else 0.0

        # Capital-Weighted Return (Sum of Realized PnL / Account Size $10,000)
        tot_realized_dollar = sum(float(t.get("realized_pnl", 0.0)) for t in history)
        capital_weighted_pct = (tot_realized_dollar / 10000.0) * 100.0

        best_trade = max(history, key=lambda t: float(t.get("pnl_r", t.get("pnl_pct", 0.0))))
        worst_trade = min(history, key=lambda t: float(t.get("pnl_r", t.get("pnl_pct", 0.0))))

        lines.extend(
            [
                f"🏆 <b>สรุปผลงานที่ปิดรอบแล้ว ({total} รอบ)</b>",
                f"• <b>Win Rate:</b> <code>{win_rate:.1f}%</code> (ชนะ {len(wins)} / แพ้ {len(losses)})",
                f"• <b>กำไรสะสมสุทธิ (R):</b> <code>{total_r:+.2f}R</code>",
                f"• <b>R เฉลี่ย:</b> ชนะเฉลี่ย <code>+{avg_win_r:.2f}R</code> | แพ้เฉลี่ย <code>{avg_loss_r:.2f}R</code>",
                f"• <b>ผลตอบแทนถ่วงน้ำหนักพอร์ต:</b> <code>{capital_weighted_pct:+.2f}%</code> (${tot_realized_dollar:+,.2f})",
                f"• <b>ไม้ที่ดีที่สุด:</b> <b>{best_trade.get('ticker', '?')}</b> (<code>{float(best_trade.get('pnl_r', best_trade.get('pnl_pct', 0.0))):+.2f}R</code>)",
                f"• <b>ไม้ที่แย่ที่สุด:</b> <b>{worst_trade.get('ticker', '?')}</b> (<code>{float(worst_trade.get('pnl_r', worst_trade.get('pnl_pct', 0.0))):+.2f}R</code>)",
                "",
                "📜 <b>ประวัติการปิดรอบล่าสุด (สูงสุด 10 รายการ):</b>",
            ]
        )
        for t in reversed(history[-10:]):
            tk = t.get("ticker", "?")
            bp = float(t.get("entry_price", t.get("buy_price", 0.0)))
            sp = float(t.get("exit_price", t.get("sell_price", 0.0)))
            r_val = float(t.get("pnl_r", t.get("r_multiple", 0.0)))
            pnl = float(t.get("pnl_pct", 0.0))
            days = int(t.get("days_held", 0))
            s_date = t.get("exit_date", t.get("sell_date", "-"))
            reason = t.get("exit_reason", "")
            icon = "🟢" if r_val > 0 else "🔴"
            reason_str = f" • {reason}" if reason else ""
            lines.append(
                f"{icon} <code>{tk:<5}</code> ${bp:.2f} ➔ ${sp:.2f} (<b>{r_val:+.2f}R</b> / {pnl:+.1f}%) <i>[{days} วัน{reason_str}]</i>"
            )

    lines.append("")
    lines.append(f"💼 <b>หุ้นที่กำลังถือในโซน 1 ปัจจุบัน ({len(portfolio)} ตัว):</b>")
    if portfolio:
        for tk, info in sorted(portfolio.items()):
            bp = float(info.get("entry_price", info.get("buy_price", 0.0)))
            sl = float(info.get("current_sl", info.get("stop_loss", 0.0)))
            t3 = float(info.get("target_3r", 0.0))
            sh = int(info.get("current_shares", info.get("shares", 0)))
            bdate = info.get("entry_date", info.get("buy_date", "-"))
            sh_str = f"{sh} sh @ " if sh > 0 else ""
            sl_str = f" | SL ${sl:.2f}" if sl > 0 else ""
            tp_str = f" | 3R ${t3:.2f}" if t3 > 0 else ""
            lines.append(f"• <code>{tk:<5}</code> ({sh_str}${bp:.2f}{sl_str}{tp_str})")
    else:
        lines.append("<i>(ไม่มีหุ้นที่กำลังถือในโซน 1)</i>")

    return "\n".join(lines)


def send_telegram_message(
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> bool:
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    cid = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not cid:
        print("[Telegram] ข้ามการส่ง Telegram (ยังไม่ได้ตั้งค่า TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Split message into chunks <= 3800 chars to respect Telegram's 4096-char limit
    chunks: List[str] = []
    current_lines: List[str] = []
    current_len = 0
    for line in text.split("\n"):
        if current_len + len(line) + 1 > 3800 and current_lines:
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_len = len(line) + 1
        else:
            current_lines.append(line)
            current_len += len(line) + 1
    if current_lines:
        chunks.append("\n".join(current_lines))

    success = True
    for i, chunk in enumerate(chunks):
        payload: Dict[str, Any] = {
            "chat_id": cid,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup and i == len(chunks) - 1:
            payload["reply_markup"] = reply_markup

        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 400 and "can't parse entities" in resp.text:
                payload.pop("parse_mode", None)
                resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
        except Exception as exc:
            print(f"[Telegram] Error sending message chunk {i+1}: {exc}")
            success = False
    return success


def send_telegram_photo(
    photo_path: str,
    caption: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> bool:
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    cid = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not cid or not os.path.exists(photo_path):
        return False

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(photo_path, "rb") as img_file:
            files = {"photo": img_file}
            data: Dict[str, Any] = {"chat_id": cid, "caption": caption, "parse_mode": "HTML"}
            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)
            resp = requests.post(url, data=data, files=files, timeout=30)
            resp.raise_for_status()
        return True
    except Exception as exc:
        print(f"[Telegram] Error sending photo: {exc}")
        return False


def _record_closed_trade(
    cfg: Dict[str, Any],
    tk: str,
    pos: Dict[str, Any],
    sell_price: float,
    sell_date: str,
    exit_reason: str = "SELL Signal",
    realized_pnl: Optional[float] = None,
    r_multiple: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    buy_price = float(pos.get("entry_price", pos.get("buy_price", 0.0)))
    buy_date = str(pos.get("entry_date", pos.get("buy_date", sell_date)))
    if sell_price <= 0:
        sell_price = _fetch_latest_price_us(tk)
    if buy_price <= 0 or sell_price <= 0:
        return None

    shares = int(pos.get("current_shares", pos.get("shares", 1)))
    sl = float(pos.get("current_sl", pos.get("stop_loss", round(buy_price * 0.95, 2))))
    risk_per_sh = float(pos.get("risk_per_share", round(buy_price - sl, 2)))
    if risk_per_sh <= 0:
        risk_per_sh = round(buy_price * 0.05, 2)

    pnl_pct = round(((sell_price - buy_price) / buy_price) * 100.0, 2)
    tot_pnl = realized_pnl if realized_pnl is not None else round((sell_price - buy_price) * shares, 2)
    r_mult = r_multiple if r_multiple is not None else round((sell_price - buy_price) / risk_per_sh, 2)
    days_held = _calc_days_held(buy_date, sell_date)

    record = {
        "ticker": tk,
        "entry_price": round(buy_price, 2),
        "exit_price": round(sell_price, 2),
        "buy_price": round(buy_price, 2),
        "sell_price": round(sell_price, 2),
        "shares": shares,
        "realized_pnl": tot_pnl,
        "r_multiple": r_mult,
        "pnl_r": r_mult,
        "pnl_pct": pnl_pct,
        "buy_date": buy_date,
        "sell_date": sell_date,
        "entry_date": buy_date,
        "exit_date": sell_date,
        "days_held": days_held,
        "exit_reason": exit_reason,
    }
    history = cfg.setdefault("trade_history", [])
    history.append(record)
    return record


def sync_telegram_commands(cfg: Dict[str, Any], config_path: str) -> Dict[str, Any]:
    """
    Polls Telegram getUpdates for any queued commands sent by the user:
      /buy TICKER [PRICE]   -> ย้ายหุ้นเข้าโซนที่ 1 (บันทึกทุนเพื่อวัดผลกระดุม 6 เม็ด)
      /sell TICKER [PRICE]  -> ขายหุ้นออกจากโซนที่ 1 และบันทึกสถิติลง trade_history
      /stat                 -> ดูสถิติผลการเทรดย้อนหลังและอัตราชนะ (Win Rate)
      /add TICKER           -> เพิ่มหุ้นเข้า Watchlist
      /remove TICKER        -> ลบหุ้นออกจาก Watchlist
    Also handles inline button clicks (callback_query: BUY:TICKER:PRICE or SELL:TICKER[:PRICE]).
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    cid = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token:
        return cfg

    last_update_id = int(cfg.get("last_telegram_update_id", 0))
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 2}

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        updates = resp.json().get("result", [])
    except Exception as exc:
        print(f"[Telegram] ไม่สามารถดึงคำสั่งล่าสุดได้: {exc}")
        return cfg

    if not updates:
        return cfg

    portfolio: Dict[str, Dict[str, Any]] = cfg.setdefault("portfolio", {})
    cfg.setdefault("trade_history", [])
    tickers: List[str] = [t.upper() for t in cfg.get("tickers", [])]
    changed = False
    today_str = datetime.now().strftime("%Y-%m-%d")

    for upd in updates:
        upd_id = int(upd["update_id"])
        if upd_id > last_update_id:
            last_update_id = upd_id
            cfg["last_telegram_update_id"] = last_update_id
            changed = True

        # 1. Handle Inline Button Callback (callback_query)
        cb = upd.get("callback_query")
        if cb:
            cb_data = cb.get("data", "")
            cb_chat_id = str(cb.get("message", {}).get("chat", {}).get("id", cid))
            if cb_data.startswith("BUY:"):
                parts = cb_data.split(":")
                tk = parts[1].upper()
                price = float(parts[2]) if len(parts) > 2 else 0.0
                if price <= 0:
                    price = _fetch_latest_price_us(tk)
                portfolio[tk] = {"buy_price": price, "buy_date": today_str}
                if tk not in tickers:
                    tickers.append(tk)
                send_telegram_message(
                    f"✅ <b>บันทึกเข้าพอร์ตกระดุม 6 เม็ดสำเร็จ!</b>\n"
                    f"ย้าย <b>{tk}</b> (ทุน <code>${price:.2f}</code>) เข้าสู่ <b>💼 โซนที่ 1</b> เพื่อวัดผลและรอสัญญาณขายเมื่อครบ 6 เม็ดแดงครับ",
                    chat_id=cb_chat_id,
                )
            elif cb_data.startswith("SELL:"):
                parts = cb_data.split(":")
                tk = parts[1].upper()
                sell_price = float(parts[2]) if len(parts) > 2 else 0.0
                pos = portfolio.pop(tk, None)
                if pos is not None:
                    rec = _record_closed_trade(cfg, tk, pos, sell_price, today_str)
                    if rec:
                        icon = "🟢 กำไร" if rec["pnl_pct"] > 0 else "🔴 ขาดทุน"
                        send_telegram_message(
                            f"💰 <b>ปิดรอบการเทรด {tk} สำเร็จ! ({icon} {rec['pnl_pct']:+.2f}%)</b>\n"
                            f"• ทุนซื้อ: <code>${rec['buy_price']:.2f}</code> ({rec['buy_date']})\n"
                            f"• ราคาขาย: <code>${rec['sell_price']:.2f}</code> ({rec['sell_date']} | ถือ {rec['days_held']} วัน)\n"
                            f"📊 <i>บันทึกผลเข้าสู่ระบบสถิติหลังบ้านแล้ว พิมพ์ <code>/stat</code> เพื่อดูสรุปผลงานทั้งหมดได้ทันทีครับ</i>",
                            chat_id=cb_chat_id,
                        )
                    else:
                        send_telegram_message(
                            f"💰 <b>นำ {tk} ออกจากโซน 1 เรียบร้อยแล้วครับ</b>",
                            chat_id=cb_chat_id,
                        )
                else:
                    send_telegram_message(f"ℹ️ ไม่พบ {tk} ในโซนที่ 1 ปัจจุบันครับ", chat_id=cb_chat_id)
            continue

        # 2. Handle Text Commands (/buy, /sell, /stat, /add, /remove, /scan — with or without leading '/')
        msg = upd.get("message", {})
        text = (msg.get("text") or "").strip()
        msg_chat_id = str(msg.get("chat", {}).get("id", cid))
        if not text:
            continue

        tokens = text.split()
        raw_cmd = tokens[0].lower().split("@")[0]
        known_cmds = {"/buy", "/sell", "/stat", "/stats", "/add", "/remove", "/scan", "/report", "/help", "/start"}
        candidate_cmd = raw_cmd if raw_cmd.startswith("/") else f"/{raw_cmd}"

        if candidate_cmd not in known_cmds and cfg.get("pending_command"):
            pending = cfg.pop("pending_command")
            tokens = [pending] + tokens
            cmd = pending
        else:
            cmd = candidate_cmd
            if cmd in known_cmds:
                cfg.pop("pending_command", None)

        if cmd in ("/buy", "/sell", "/add", "/remove") and len(tokens) == 1:
            cfg["pending_command"] = cmd
            prompts = {
                "/buy": "✍️ <b>พิมพ์ชื่อหุ้น (และราคาทุนถ้ามี)</b> ที่ต้องการซื้อเข้าโซน 1 ส่งมาได้เลยครับ\nเช่น: <code>AAPL</code> หรือ <code>AAPL 230.50</code>",
                "/sell": "✍️ <b>พิมพ์ชื่อหุ้น (และราคาขายถ้ามี)</b> ที่ต้องการขายปิดรอบจากโซน 1 ส่งมาได้เลยครับ\nเช่น: <code>AAPL</code> หรือ <code>AAPL 245.00</code>",
                "/add": "✍️ <b>พิมพ์ชื่อหุ้นที่ต้องการเพิ่มเข้า Watchlist</b> ส่งมาได้เลยครับ (พิมพ์หลายตัวเว้นวรรคได้)\nเช่น: <code>NVDA AMD TSLA</code>",
                "/remove": "✍️ <b>พิมพ์ชื่อหุ้นที่ต้องการลบออกจาก Watchlist</b> ส่งมาได้เลยครับ\nเช่น: <code>NVDA</code>",
            }
            send_telegram_message(prompts[cmd], chat_id=msg_chat_id)
            continue

        if cmd == "/buy" and len(tokens) >= 2:
            tk = tokens[1].upper()
            price = 0.0
            if len(tokens) >= 3:
                try:
                    price = float(tokens[2])
                except ValueError:
                    price = 0.0
            if price <= 0:
                price = _fetch_latest_price_us(tk)
            portfolio[tk] = {"buy_price": price, "buy_date": today_str}
            if tk not in tickers:
                tickers.append(tk)
            price_txt = f"ที่ราคาทุน <code>${price:.2f}</code>" if price > 0 else ""
            send_telegram_message(
                f"✅ <b>บันทึก {tk} เข้าสู่โซน 1 (พอร์ตกระดุม 6 เม็ด) แล้ว {price_txt}</b>\n"
                f"ระบบจะคำนวณ % กำไร/ขาดทุนให้ทุกวัน และแจ้งเตือนเมื่อเกิดสัญญาณขายครับ",
                chat_id=msg_chat_id,
            )

        elif cmd == "/sell" and len(tokens) >= 2:
            tk = tokens[1].upper()
            sell_price = 0.0
            if len(tokens) >= 3:
                try:
                    sell_price = float(tokens[2])
                except ValueError:
                    sell_price = 0.0
            if tk in portfolio:
                pos = portfolio.pop(tk, None)
                rec = _record_closed_trade(cfg, tk, pos or {}, sell_price, today_str)
                if rec:
                    icon = "🟢 กำไร" if rec["pnl_pct"] > 0 else "🔴 ขาดทุน"
                    send_telegram_message(
                        f"💰 <b>ปิดรอบการเทรด {tk} สำเร็จ! ({icon} {rec['pnl_pct']:+.2f}%)</b>\n"
                        f"• ทุนซื้อ: <code>${rec['buy_price']:.2f}</code> ({rec['buy_date']})\n"
                        f"• ราคาขาย: <code>${rec['sell_price']:.2f}</code> ({rec['sell_date']} | ถือ {rec['days_held']} วัน)\n"
                        f"📊 <i>บันทึกเข้าสถิติหลังบ้านเรียบร้อย พิมพ์ <code>/stat</code> เพื่อดู Win Rate และผลตอบแทนรวมได้เลยครับ</i>",
                        chat_id=msg_chat_id,
                    )
                else:
                    send_telegram_message(
                        f"💰 <b>นำ {tk} ออกจากโซน 1 เรียบร้อยแล้ว</b>\n"
                        f"ย้ายกลับไปอยู่ใน Watchlist เพื่อรอจังหวะเข้าซื้อรอบใหม่ครับ",
                        chat_id=msg_chat_id,
                    )
            else:
                send_telegram_message(f"ℹ️ ไม่พบ {tk} ในโซนที่ 1 ปัจจุบันครับ", chat_id=msg_chat_id)

        elif cmd in ("/stat", "/stats"):
            stat_msg = format_stat_message(cfg)
            send_telegram_message(stat_msg, chat_id=msg_chat_id)

        elif cmd == "/add" and len(tokens) >= 2:
            added = []
            already = []
            for raw_tk in tokens[1:]:
                tk = raw_tk.strip(", ").upper()
                if not tk:
                    continue
                if tk not in tickers:
                    tickers.append(tk)
                    added.append(tk)
                else:
                    already.append(tk)
            msg_parts = []
            if added:
                msg_parts.append(f"➕ เพิ่มหุ้นเข้า Watchlist แล้ว: <b>{', '.join(added)}</b>")
            if already:
                msg_parts.append(f"ℹ️ มีอยู่ใน Watchlist แล้ว: <b>{', '.join(already)}</b>")
            if msg_parts:
                send_telegram_message("\n".join(msg_parts), chat_id=msg_chat_id)

        elif cmd == "/remove" and len(tokens) >= 2:
            tk = tokens[1].upper()
            if tk in tickers:
                tickers.remove(tk)
                portfolio.pop(tk, None)
                send_telegram_message(f"🗑️ ลบ <b>{tk}</b> ออกจาก Watchlist แล้วครับ", chat_id=msg_chat_id)

        elif cmd in ("/scan", "/report"):
            cfg["_trigger_scan_now"] = True
            send_telegram_message(
                "⏳ <b>รับคำสั่ง /scan แล้วครับ!</b> กำลังดึงกราฟล่าสุดและสร้างกระดานเม็ดกระดุม 3 โซนส่งให้สักครู่ครับ...",
                chat_id=msg_chat_id,
            )

        elif cmd in ("/help", "/start"):
            send_telegram_message(
                "🤖 <b>คำสั่งควบคุมพอร์ตกระดุม 6 เม็ด & Watchlist (US)</b>\n"
                "• <code>/scan</code> — สั่งสแกนกราฟและส่งกระดาน 3 โซนให้ดูทันที\n"
                "• <code>/buy AAPL</code> หรือ <code>/buy AAPL 230.5</code> — บันทึกซื้อเข้าโซน 1 (ดึงราคาปิดให้อัตโนมัติถ้าไม่ระบุราคา)\n"
                "• <code>/sell AAPL</code> หรือ <code>/sell AAPL 245.0</code> — ขายปิดรอบจากโซน 1 และบันทึกสถิติหลังบ้าน\n"
                "• <code>/stat</code> — ดูสถิติผลการเทรด (Win Rate, กำไรสะสม, ประวัติการซื้อขาย)\n"
                "• <code>/add NVDA AMD</code> — เพิ่มหุ้นเข้า Watchlist\n"
                "• <code>/remove NVDA</code> — ลบหุ้นออกจาก Watchlist",
                chat_id=msg_chat_id,
            )

    cfg["tickers"] = tickers
    cfg["portfolio"] = portfolio
    if changed:
        save_copy = {k: v for k, v in cfg.items() if not k.startswith("_")}
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(save_copy, f, indent=2, ensure_ascii=False)

    return cfg


def _count_green_red(colors: List[str]) -> tuple:
    g_cnt = sum(1 for c in colors if c in ("G", "BUY_Rocket", "HOLD_ChartUp"))
    r_cnt = sum(1 for c in colors if c in ("R", "SELL_Siren", "HOLD_ChartDown"))
    return g_cnt, r_cnt


def _score_zone2_uptrend(item: Dict[str, Any]) -> tuple:
    st = item["latest"]
    act = st["action_today"]
    colors = st.get("dot_colors", [])
    _, r_cnt = _count_green_red(colors)

    if act == "BUY_NOW":
        rank = 1
    elif r_cnt == 0:
        rank = 2
    else:
        rank = 2 + r_cnt
    return (rank, item["ticker"])


def _score_zone3_downtrend(item: Dict[str, Any]) -> tuple:
    st = item["latest"]
    act = st["action_today"]
    colors = st.get("dot_colors", [])
    g_cnt, _ = _count_green_red(colors)

    if g_cnt == 4:
        rank = 1
    elif g_cnt == 3:
        rank = 2
    elif g_cnt == 2:
        rank = 3
    elif g_cnt == 1:
        rank = 4
    elif act == "SELL_NOW":
        rank = 5
    else:
        rank = 6
    return (rank, -st.get("bar_count", 0), item["ticker"])


def _is_uptrend_watchlist(st: Dict[str, Any]) -> bool:
    colors = st.get("dot_colors") or []
    if colors:
        return colors[-1] in ("G", "BUY_Rocket", "HOLD_ChartUp")
    return st.get("trend_locked") == "BUY"


def _score_stock_progress(item: Dict[str, Any]) -> tuple:
    st = item["latest"]
    if _is_uptrend_watchlist(st):
        return _score_zone2_uptrend(item)
    return _score_zone3_downtrend(item)


def _score_portfolio_exit_urgency(item: Dict[str, Any]) -> tuple:
    st = item["latest"]
    act = st["action_today"]
    colors = st.get("dot_colors", [])
    g_cnt, r_cnt = _count_green_red(colors)

    if st["side"] == "SELL":
        if act == "SELL_NOW":
            return (1, -r_cnt, item["ticker"])
        if act == "HOLD_SELL":
            return (2, -r_cnt, item["ticker"])
        sell_rank_map = {4: 3, 3: 4, 2: 5, 1: 6}
        return (sell_rank_map.get(r_cnt, 7), -r_cnt, item["ticker"])
    else:
        if act == "BUY_NOW":
            return (8, -g_cnt, item["ticker"])
        if act == "HOLD_BUY":
            return (9, -g_cnt, item["ticker"])
        buy_rank_map = {4: 10, 3: 11, 2: 12, 1: 13}
        return (buy_rank_map.get(g_cnt, 14), -g_cnt, item["ticker"])


def format_ema21_extension_info(st: Dict[str, Any]) -> str:
    """
    Calculates % distance between Close and EMA 21 to warn against chasing overextended breakouts (>5%).
    """
    close_p = float(st.get("close", 0.0))
    ema21 = float(st.get("ema_slow", 0.0))
    if close_p <= 0 or ema21 <= 0:
        return ""
    dist_pct = ((close_p - ema21) / ema21) * 100.0
    if dist_pct <= 5.0:
        return f"✅ ระยะห่างฐาน EMA21: <b>{dist_pct:+.1f}%</b> <i>(ใกล้ฐานแนวรับ จุดคัทตื้น ปลอดภัย)</i>"
    elif dist_pct <= 8.0:
        return f"⚠️ ระยะห่างฐาน EMA21: <b>{dist_pct:+.1f}%</b> <i>(เริ่มห่างฐานเกิน 5% แนะนำแบ่งไม้เข้า 50%)</i>"
    else:
        return f"🔥 ระยะห่างฐาน EMA21: <b>{dist_pct:+.1f}%</b> <i>(ราคาพุ่งตึงมาก! ระวังการไล่ราคา/รอย่อใกล้ EMA9)</i>"


def format_portfolio_exit_status(st: Dict[str, Any]) -> str:
    close_p = float(st.get("close", 0.0))
    ema9 = float(st.get("ema_fast", 0.0))
    ema21 = float(st.get("ema_slow", 0.0))
    below_ema9_txt = " (⚠️ ราคาเริ่มหลุดเส้นฟ้า EMA9 แบ่งล็อกกำไรได้)" if (close_p > 0 and ema9 > 0 and close_p < ema9) else ""

    if st["side"] == "BUY":
        if close_p > 0 and ema21 > 0:
            dist_pct = ((close_p - ema21) / ema21) * 100.0
            if dist_pct > 8.0:
                return f"🔥 กราฟขาขึ้นเต็มตัว แต่ราคาฉีกห่าง EMA21 ถึง {dist_pct:+.1f}% — ถือรันเทรนด์และระวังแรงเทขายทำกำไร"
        return "✅ กราฟยังเป็นขาขึ้น (KDJ เขียว) — ถือรันกำไรต่อ ยังไม่มีเม็ดแดงเตือนขาย"
    act = st["action_today"]
    bc = st["bar_count"]
    mb = st["max_bars"]
    if act == "SELL_NOW":
        return f"🚨 ครบ 6 เม็ดแดงวันนี้! (แท่งที่ {bc}/{mb}) — สัญญาณขายทิ้งออกจากพอร์ต! (EXIT NOW)"
    if act == "HOLD_SELL":
        return "🚨 กระดุมแดงครบ 6 เม็ดแล้ว — แนะนำขายออก / ระวังขาลงเต็มตัว!"
    if act == "WAIT_CONFIRM_SELL":
        return f"⚠️ เตรียมขายพรุ่งนี้! EMA9 ตัดลง EMA21 แล้ว (เม็ดแดงที่ 3 แท่ง {bc}/{mb}) รอแท่งถัดไปคอนเฟิร์ม"
    if act in ("COUNTING_SELL", "MACD_DOT_SELL"):
        return f"⏳ เฝ้าระวังย่อตัว! เกิดจุดแดง MACD นับแท่งที่ {bc}/{mb}{below_ema9_txt}"
    return f"👀 KDJ เริ่มย่อเป็นสีแดง (เม็ดแดงที่ 1){below_ema9_txt} — ยังถือต่อ รอเช็คจุดแดง MACD"


def _compact_buttons(st: Dict[str, Any]) -> str:
    if "buttons_compact" in st and st["buttons_compact"]:
        return st["buttons_compact"]
    if "dot_colors" in st and st["dot_colors"]:
        m = {
            "G": "🟢",
            "R": "🔴",
            "W": "⚪",
            "BUY_Rocket": "🚀",
            "SELL_Siren": "🚨",
            "HOLD_ChartUp": "📈",
            "HOLD_ChartDown": "📉",
        }
        return "".join(m.get(c, "⚪") for c in st["dot_colors"])
    dot = "🟢" if st["side"] == "BUY" else "🔴"
    s1 = dot if st["b1_kdj"] else "⚪"
    s2 = dot if st["b2_macd_dot"] else "⚪"
    s3 = dot if st["b3_counting"] else "⚪"
    s4 = dot if st["b4_ema_cross"] else "⚪"
    s5 = dot if st["b5_ema_confirm"] else "⚪"
    s6 = dot if st["b6_signal"] else "⚪"
    return f"{s1}{s2}{s3}{s4}{s5}{s6}"


def format_daily_board_message(
    scan_results: List[Dict[str, Any]],
    portfolio: Dict[str, Dict[str, Any]],
    scan_date: str,
) -> str:
    portfolio_upper = {k.upper(): v for k, v in portfolio.items()}
    portfolio_tickers = set(portfolio_upper.keys())

    zone1_portfolio = sorted(
        [x for x in scan_results if x["ticker"] in portfolio_tickers],
        key=_score_portfolio_exit_urgency,
    )
    zone2_watchlist_buy = sorted(
        [x for x in scan_results if x["ticker"] not in portfolio_tickers and _is_uptrend_watchlist(x["latest"])],
        key=_score_zone2_uptrend,
    )
    zone3_watchlist_sell = sorted(
        [x for x in scan_results if x["ticker"] not in portfolio_tickers and not _is_uptrend_watchlist(x["latest"])],
        key=_score_zone3_downtrend,
    )

    lines = [
        f"📊 <b>กระดานเม็ดกระดุม US (1D) — {scan_date}</b>",
        "<code>1:KDJ | 2:MACD(0-9) | 3:EMAตัด | 4:EMA&gt;21 | 5:ปิด&gt;EMA | 6:สถานะ</code>",
        "",
    ]

    # Build ⚡ ACTION ALERT box at the very top
    buy_now_list = [x for x in scan_results if x["latest"]["action_today"] == "BUY_NOW"]
    sell_now_list = [x for x in scan_results if x["latest"]["action_today"] == "SELL_NOW"]
    setup_buy_list = sorted(
        [
            x
            for x in scan_results
            if x["latest"]["action_today"] in ("WAIT_CONFIRM_BUY", "MACD_DOT_BUY", "COUNTING_BUY")
        ],
        key=lambda x: (-_count_green_red(x["latest"].get("dot_colors", []))[0], x["ticker"]),
    )
    setup_sell_list = sorted(
        [
            x
            for x in scan_results
            if x["latest"]["action_today"] in ("WAIT_CONFIRM_SELL", "MACD_DOT_SELL", "COUNTING_SELL")
        ],
        key=lambda x: (
            0 if x["ticker"] in portfolio_tickers else 1,
            -_count_green_red(x["latest"].get("dot_colors", []))[1],
            x["ticker"],
        ),
    )

    lines.extend(
        [
            "⚡ <b>ACTION ALERT — สัญญาณต้องจับตาวันนี้</b>",
            "━━━━━━━━━━━━━━━━━━",
        ]
    )

    if buy_now_list:
        lines.append(f"🚀 <b>เข้าซื้อวันนี้ ({len(buy_now_list)}):</b>")
        for item in buy_now_list:
            tk = item["ticker"]
            st = item["latest"]
            lines.append(f"<code>{tk:<5}</code> {_compact_buttons(st)} <code>${st['close']:.2f}</code>")
    else:
        lines.append("🚀 <b>เข้าซื้อวันนี้:</b> <i>(ไม่มี)</i>")

    if sell_now_list:
        lines.append(f"🚨 <b>ขายออกวันนี้ ({len(sell_now_list)}):</b>")
        for item in sell_now_list:
            tk = item["ticker"]
            st = item["latest"]
            lines.append(f"<code>{tk:<5}</code> {_compact_buttons(st)} <code>${st['close']:.2f}</code>")
    else:
        lines.append("🚨 <b>ขายออกวันนี้:</b> <i>(ไม่มี)</i>")

    if setup_buy_list:
        lines.append(f"🟢 <b>จ่อซื้อ ({len(setup_buy_list)}):</b>")
        for item in setup_buy_list:
            tk = item["ticker"]
            st = item["latest"]
            lines.append(f"<code>{tk:<5}</code> {_compact_buttons(st)} <code>${st['close']:.2f}</code>")

    if setup_sell_list:
        lines.append(f"⚠️ <b>เฝ้าระวังย่อ/จ่อขาย ({len(setup_sell_list)}):</b>")
        for item in setup_sell_list:
            tk = item["ticker"]
            st = item["latest"]
            lines.append(f"<code>{tk:<5}</code> {_compact_buttons(st)} <code>${st['close']:.2f}</code>")

    lines.extend(
        [
            "",
            f"💼 <b>โซน 1: พอร์ตกระดุม 6 เม็ด ({len(zone1_portfolio)})</b>",
            "━━━━━━━━━━━━━━━━━━",
        ]
    )

    if zone1_portfolio:
        for item in zone1_portfolio:
            tk = item["ticker"]
            st = item["latest"]
            btns = _compact_buttons(st)
            bp = float(portfolio_upper.get(tk, {}).get("buy_price", 0.0))
            if bp > 0:
                pnl_pct = ((st["close"] - bp) / bp) * 100.0
                lines.append(f"<code>{tk:<5}</code> {btns} <code>${st['close']:.2f} ({pnl_pct:+.1f}%)</code>")
            else:
                lines.append(f"<code>{tk:<5}</code> {btns} <code>${st['close']:.2f}</code>")
    else:
        lines.append("<i>(ยังไม่มีหุ้นที่ซื้อด้วยกระดุม 6 เม็ด — พิมพ์ /buy ชื่อหุ้น เพื่อเริ่มวัดผล)</i>")

    lines.extend(
        [
            "",
            f"🟢 <b>โซน 2: Watchlist ขาขึ้น ({len(zone2_watchlist_buy)})</b>",
            "━━━━━━━━━━━━━━━━━━",
        ]
    )

    if zone2_watchlist_buy:
        for item in zone2_watchlist_buy:
            tk = item["ticker"]
            st = item["latest"]
            btns = _compact_buttons(st)
            lines.append(f"<code>{tk:<5}</code> {btns} <code>${st['close']:.2f}</code>")
    else:
        lines.append("<i>(ไม่มี)</i>")

    lines.extend(
        [
            "",
            f"🔴 <b>โซน 3: Watchlist ขาลง ({len(zone3_watchlist_sell)})</b>",
            "━━━━━━━━━━━━━━━━━━",
        ]
    )

    if zone3_watchlist_sell:
        for item in zone3_watchlist_sell:
            tk = item["ticker"]
            st = item["latest"]
            btns = _compact_buttons(st)
            lines.append(f"<code>{tk:<5}</code> {btns} <code>${st['close']:.2f}</code>")
    else:
        lines.append("<i>(ไม่มี)</i>")

    return "\n".join(lines)
