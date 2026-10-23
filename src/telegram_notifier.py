"""
Telegram Bot Notifier & Command Handler for US Stock 6-Button Strategy

Supports:
1. Reading user commands from Telegram (/buy, /sell, /add, /remove, /portfolio) and inline button clicks
2. Sending the 3-Zone daily 6-Button report:
   - 💼 โซนที่ 1: หุ้นในพอร์ต (สั่งซื้อแล้ว — รอจังหวะขายออกเมื่อครบ 6 เม็ดแดง)
   - 🟢 โซนที่ 2: Watchlist ขาขึ้น (KDJ เขียว — รอจังหวะเข้าซื้อเมื่อครบ 6 เม็ดเขียว)
   - 🔴 โซนที่ 3: Watchlist ขาลง (KDJ แดง — พักตัว/ขาลง)
3. Sending individual stock chart images with inline action buttons
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


def sync_telegram_commands(cfg: Dict[str, Any], config_path: str) -> Dict[str, Any]:
    """
    Polls Telegram getUpdates for any queued commands sent by the user:
      /buy TICKER [PRICE]   -> ย้ายหุ้นเข้าโซนที่ 1 (พอร์ตของฉัน รอจังหวะขายออก)
      /sell TICKER          -> เอาหุ้นออกจากโซนที่ 1 กลับไปอยู่ Watchlist
      /add TICKER           -> เพิ่มหุ้นเข้า Watchlist
      /remove TICKER        -> ลบหุ้นออกจาก Watchlist
    Also handles inline button clicks (callback_query: BUY:TICKER:PRICE or SELL:TICKER).
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
                portfolio[tk] = {"buy_price": price, "buy_date": today_str}
                if tk not in tickers:
                    tickers.append(tk)
                send_telegram_message(
                    f"✅ <b>บันทึกเข้าพอร์ตสำเร็จ!</b>\n"
                    f"ย้าย <b>{tk}</b> (ทุน ${price:.2f}) เข้าสู่ <b>💼 โซนที่ 1: หุ้นในพอร์ต (รอสัญญาณขายออกครบ 6 เม็ดแดง)</b> เรียบร้อยแล้วครับ",
                    chat_id=cb_chat_id,
                )
            elif cb_data.startswith("SELL:"):
                parts = cb_data.split(":")
                tk = parts[1].upper()
                portfolio.pop(tk, None)
                send_telegram_message(
                    f"💰 <b>บันทึกการขายออกสำเร็จ!</b>\n"
                    f"นำ <b>{tk}</b> ออกจากพอร์ต และย้ายกลับไปเฝ้าดูใน <b>Watchlist</b> เรียบร้อยแล้วครับ",
                    chat_id=cb_chat_id,
                )
            continue

        # 2. Handle Text Commands (/buy, /sell, /add, /remove)
        msg = upd.get("message", {})
        text = (msg.get("text") or "").strip()
        msg_chat_id = str(msg.get("chat", {}).get("id", cid))
        if not text.startswith("/"):
            continue

        tokens = text.split()
        cmd = tokens[0].lower().split("@")[0]

        if cmd == "/buy" and len(tokens) >= 2:
            tk = tokens[1].upper()
            price = 0.0
            if len(tokens) >= 3:
                try:
                    price = float(tokens[2])
                except ValueError:
                    price = 0.0
            portfolio[tk] = {"buy_price": price, "buy_date": today_str}
            if tk not in tickers:
                tickers.append(tk)
            price_txt = f"ที่ราคา ${price:.2f}" if price > 0 else ""
            send_telegram_message(
                f"✅ <b>บันทึก {tk} เข้าพอร์ตแล้ว {price_txt}</b>\n"
                f"ระบบจะนำ <b>{tk}</b> ไปแสดงใน <b>💼 โซนที่ 1 (เฝ้าระวังกระดุมแดง 1–6 เพื่อเตือนจุดขายออก)</b> ครับ",
                chat_id=msg_chat_id,
            )

        elif cmd == "/sell" and len(tokens) >= 2:
            tk = tokens[1].upper()
            if tk in portfolio:
                portfolio.pop(tk, None)
                send_telegram_message(
                    f"💰 <b>นำ {tk} ออกจากพอร์ตเรียบร้อยแล้ว</b>\n"
                    f"ย้ายกลับไปอยู่ใน Watchlist เพื่อรอจังหวะเข้าซื้อรอบใหม่ครับ",
                    chat_id=msg_chat_id,
                )
            else:
                send_telegram_message(f"ℹ️ ไม่พบ {tk} ในรายการพอร์ตปัจจุบันครับ", chat_id=msg_chat_id)

        elif cmd == "/add" and len(tokens) >= 2:
            added = []
            for raw_tk in tokens[1:]:
                tk = raw_tk.strip(", ").upper()
                if tk and tk not in tickers:
                    tickers.append(tk)
                    added.append(tk)
            if added:
                send_telegram_message(f"➕ เพิ่มหุ้นเข้า Watchlist แล้ว: <b>{', '.join(added)}</b>", chat_id=msg_chat_id)

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
                "🤖 <b>คำสั่งควบคุมพอร์ตและ Watchlist ผ่าน Telegram</b>\n"
                "• <code>/scan</code> — สั่งสแกนกราฟและส่งกระดาน 3 โซนให้ดูทันที\n"
                "• <code>/buy AAPL</code> — บันทึกว่าซื้อหุ้นแล้ว (ย้ายเข้าโซนที่ 1 รอจุดขายออก)\n"
                "• <code>/sell RXRX</code> — บันทึกว่าขายหุ้นแล้ว (ย้ายกลับเข้า Watchlist)\n"
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


def _score_stock_progress(item: Dict[str, Any]) -> tuple:
    """
    Sorts Watchlist stocks (Zone 2 & Zone 3) so identical button patterns stay grouped together:
    1. Just completed 6 dots today (BUY_NOW / SELL_NOW)
    2. Actively forming 4 dots (WAIT_CONFIRM)
    3. Actively forming 3 dots (COUNTING)
    4. Full 6 dots holding (🟢🟢🟢🟢🟢🟢 in Zone 2, 🔴🔴🔴🔴🔴🔴 in Zone 3)
    5. 1 dot challenging 5 opposite dots (🟢🔴🔴🔴🔴🔴 in Zone 2, 🔴🟢🟢🟢🟢🟢 in Zone 3)
    """
    st = item["latest"]
    act = st["action_today"]
    colors = st.get("dot_colors", [])
    target_c = "G" if st["side"] == "BUY" else "R"
    cnt = colors.count(target_c)

    if act in ("BUY_NOW", "SELL_NOW"):
        rank = 1
    elif cnt == 4:
        rank = 2
    elif cnt == 3:
        rank = 3
    elif cnt == 6:
        rank = 4
    else:
        rank = 5
    return (rank, -cnt, -st.get("bar_count", 0), item["ticker"])


def _score_portfolio_exit_urgency(item: Dict[str, Any]) -> tuple:
    """
    For Zone 1 (Portfolio stocks waiting for exit):
    Groups identical button patterns cleanly by exit urgency:
    1. 🔴🔴🔴🔴🔴🔴 (6 Red - ครบ 6 เม็ดแดง ขายออก)
    2. 🔴🔴🔴🔴🟢🟢 (4 Red - EMA ตัดลง รอคอนเฟิร์ม)
    3. 🔴🔴🔴🟢🟢🟢 (3 Red - MACD จุดแดง นับแท่ง 1-9)
    4. 🔴🟢🟢🟢🟢🟢 (1 Red - KDJ เริ่มย่อแดงเม็ดแรก)
    5. 🟢🟢🟢🟢🟢🟢 (6 Green - ขาขึ้นเต็มตัว ถือรันกำไร)
    6. 🟢🟢🟢🟢🔴🔴 / 🟢🟢🟢🔴🔴🔴 / 🟢🔴🔴🔴🔴🔴 (กำลังฟื้นตัวจากแดงเป็นเขียว)
    """
    st = item["latest"]
    colors = st.get("dot_colors", [])
    r_cnt = colors.count("R")
    g_cnt = colors.count("G")

    if st["side"] == "SELL":
        # Red is eating Green from left to right
        if r_cnt == 6:
            rank = 1
        elif r_cnt == 4:
            rank = 2
        elif r_cnt == 3:
            rank = 3
        else:
            rank = 4
        return (rank, -r_cnt, item["ticker"])
    else:
        # Green is active
        if g_cnt == 6:
            rank = 5
        elif g_cnt == 4:
            rank = 6
        elif g_cnt == 3:
            rank = 7
        else:
            rank = 8
        return (rank, -g_cnt, item["ticker"])


def format_portfolio_exit_status(st: Dict[str, Any]) -> str:
    """
    Describes the exit/sell watch status for a stock that the user already holds in Zone 1.
    """
    if st["side"] == "BUY":
        return "✅ กราฟยังเป็นขาขึ้น (KDJ เขียว) — ถือรันกำไรต่อ ยังไม่มีเม็ดแดงเตือนขาย"
    # When side == "SELL", show how many red buttons have formed toward the 6-button exit!
    act = st["action_today"]
    bc = st["bar_count"]
    mb = st["max_bars"]
    if act == "SELL_NOW":
        return f"🚨 ครบ 6 เม็ดแดงวันนี้! (แท่งที่ {bc}/{mb}) — สัญญาณขายทิ้งออกจากพอร์ต! (EXIT NOW)"
    if act == "HOLD_SELL":
        return "🚨 กระดุมแดงครบ 6 เม็ดแล้ว — แนะนำขายออก / ระวังขาลงเต็มตัว!"
    if act == "WAIT_CONFIRM_SELL":
        return f"⚠️ เตรียมขายพรุ่งนี้! EMA9 ตัดลง EMA21 แล้ว (เม็ดแดงที่ 4 แท่ง {bc}/{mb}) รอแท่งถัดไปคอนเฟิร์ม"
    if act == "COUNTING_SELL":
        return f"⏳ เฝ้าระวังย่อตัว! เกิดจุดแดง MACD นับแท่งที่ {bc}/{mb} (รอดูว่า EMA9 จะตัดลง EMA21 หรือไม่)"
    return "👀 KDJ เริ่มย่อเป็นสีแดง (เม็ดแดงที่ 1) — ยังถือต่อ รอเช็คจุดแดง MACD"


def _compact_buttons(st: Dict[str, Any]) -> str:
    """
    Pure 6-button strip using progressive takeover colors (G=🟢, R=🔴, W=⚪).
    Example: 🔴🟢🟢🟢🟢🟢 or 🔴🔴🔴🟢🟢🟢 or 🟢🔴🔴🔴🔴🔴
    """
    if "buttons_compact" in st and st["buttons_compact"]:
        return st["buttons_compact"]
    if "dot_colors" in st and st["dot_colors"]:
        m = {"G": "🟢", "R": "🔴", "W": "⚪"}
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
    """
    Formats the 6-button daily report into 3 distinct zones using Format 2:
    1 stock = 1 compact line: Ticker + 6 pure dots + Closing Price.
    """
    portfolio_tickers = {k.upper() for k in portfolio.keys()}

    zone1_portfolio = sorted(
        [x for x in scan_results if x["ticker"] in portfolio_tickers],
        key=_score_portfolio_exit_urgency,
    )
    zone2_watchlist_buy = sorted(
        [x for x in scan_results if x["ticker"] not in portfolio_tickers and x["latest"]["side"] == "BUY"],
        key=_score_stock_progress,
    )
    zone3_watchlist_sell = sorted(
        [x for x in scan_results if x["ticker"] not in portfolio_tickers and x["latest"]["side"] == "SELL"],
        key=_score_stock_progress,
    )

    lines = [
        f"📊 <b>กระดานเม็ดกระดุม US (1D) — {scan_date}</b>",
        "<code>1:KDJ | 2:MACD | 3:นับ9 | 4:EMAตัด | 5:ยืนยัน | 6:ครบ</code>",
        "",
        f"💼 <b>โซน 1: หุ้นในพอร์ต ({len(zone1_portfolio)})</b>",
        "━━━━━━━━━━━━━━━━━━",
    ]

    if zone1_portfolio:
        for item in zone1_portfolio:
            tk = item["ticker"]
            st = item["latest"]
            btns = _compact_buttons(st)
            lines.append(f"<code>{tk:<5}</code> {btns} <code>${st['close']:.2f}</code>")
    else:
        lines.append("<i>(ไม่มีหุ้นในพอร์ต)</i>")

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
