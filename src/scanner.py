from datetime import datetime, timezone, timedelta
import json
import os
import sys
import tempfile
from dataclasses import asdict
from typing import List, Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import yfinance as yf

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.indicators import compute_all_indicators
from src.strategy_engine import evaluate_strategy_timeline
from src.chart_generator import generate_stock_chart
from src.dashboard_builder import build_dashboard_html
from src.risk_manager import US6ButtonRiskManager
from src.exit_tracker import US6ButtonExitTracker
from src.calendar_utils import is_us_market_holiday, passes_us_liquidity_filter
from src.telegram_notifier import (
    _record_closed_trade,
    _compact_buttons,
    _score_portfolio_exit_urgency,
    _score_stock_progress,
    format_daily_board_message,
    format_ema21_extension_info,
    format_portfolio_exit_status,
    send_telegram_message,
    send_telegram_photo,
    sync_telegram_commands,
)


def _atomic_save_config(config_path: str, data: dict):
    tmp_dir = os.path.dirname(config_path)
    with tempfile.NamedTemporaryFile("w", dir=tmp_dir, delete=False, encoding="utf-8") as tf:
        json.dump(data, tf, indent=2, ensure_ascii=False)
        tmp_path = tf.name
    os.replace(tmp_path, config_path)


def send_weekly_summary_6button(cfg, is_thai=False, bot_label="US 6-Button (Bot 1)"):
    history = cfg.get("trade_history", [])
    portfolio = cfg.get("portfolio", {})
    total = len(history)
    wins = sum(1 for h in history if float(h.get("pnl_r", h.get("pnl_pct", 0))) > 0)
    win_rate = (wins / total * 100.0) if total > 0 else 0.0
    total_r = sum(float(h.get("pnl_r", h.get("r_multiple", 0))) for h in history)
    
    win_rs = [float(h.get("pnl_r", h.get("r_multiple", 0))) for h in history if float(h.get("pnl_r", h.get("r_multiple", 0))) > 0]
    loss_rs = [float(h.get("pnl_r", h.get("r_multiple", 0))) for h in history if float(h.get("pnl_r", h.get("r_multiple", 0))) < 0]
    avg_win_r = (sum(win_rs) / len(win_rs)) if win_rs else 0.0
    avg_loss_r = (sum(loss_rs) / len(loss_rs)) if loss_rs else 0.0
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"📊 <b>WEEKLY FORWARD TEST REPORT</b> • <code>{today_str}</code>",
        f"<b>{bot_label}</b>",
        "━━━━━━━━━━━━━━━━",
        f"• หุ้นในพอร์ตปัจจุบัน: <code>{len(portfolio)} ตัว</code>",
        f"• ไม้ปิดรอบสะสม: <code>{total} ไม้</code>",
        f"• Win Rate: <code>{win_rate:.1f}%</code> (ชนะ {wins} / แพ้ {total - wins})",
        f"• กำไรสะสมสุทธิ: <code>{total_r:+.2f}R</code>",
    ]
    if win_rs or loss_rs:
        lines.append(f"• ชนะเฉลี่ย: <code>+{avg_win_r:.2f}R</code> | SL เฉลี่ย: <code>{avg_loss_r:.2f}R</code>")
    
    res = send_telegram_message("\n".join(lines))
    print(f"[Telegram] Weekly Forward Test Report sent: {res}")


def run_scan(config_path: str = "config/watchlist.json") -> List[Dict[str, Any]]:
    full_config_path = os.path.join(PROJECT_ROOT, config_path)
    with open(full_config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 1. Sync any queued commands (/buy, /sell, /add, /remove) from Telegram
    cfg = sync_telegram_commands(cfg, full_config_path)

    # Market Holiday Notice
    if is_us_market_holiday():
        print("[Market Notice] วันนี้เป็นวันหยุดตลาดหุ้นสหรัฐฯ (NYSE Holiday / Weekend) — ดำเนินการสแกนต่อเพื่ออัปเดตสถิติล่าสุด")

    portfolio: Dict[str, Dict[str, Any]] = {
        k.upper(): v for k, v in cfg.get("portfolio", {}).items()
    }
    tickers: List[str] = list(dict.fromkeys([t.upper() for t in cfg.get("tickers", [])] + list(portfolio.keys())))
    max_wait_bars: int = int(cfg.get("max_wait_bars", 9))
    ema_fast: int = int(cfg.get("ema_fast", 9))
    ema_slow: int = int(cfg.get("ema_slow", 21))
    macd_fast: int = int(cfg.get("macd_fast", 12))
    macd_slow: int = int(cfg.get("macd_slow", 26))
    macd_signal: int = int(cfg.get("macd_signal", 9))
    kdj_period: int = int(cfg.get("kdj_period", 9))
    kdj_signal: int = int(cfg.get("kdj_signal", 3))

    charts_dir = os.path.join(PROJECT_ROOT, "docs", "charts")
    os.makedirs(charts_dir, exist_ok=True)

    scan_results: List[Dict[str, Any]] = []
    dfs: Dict[str, Any] = {}

    print(f"=== เริ่มสแกนหุ้น US จำนวน {len(tickers)} ตัว (Timeframe 1D) ===")
    for ticker in tickers:
        ticker = ticker.strip().upper()
        if not ticker:
            continue
        try:
            df = yf.Ticker(ticker).history(period="2y", interval="1d", auto_adjust=False)
            if df is None or df.empty or len(df) < 35:
                print(f"[ข้าม] {ticker}: ข้อมูลไม่เพียงพอ")
                continue

            dfs[ticker] = df

            df_ind = compute_all_indicators(
                df,
                ema_fast=ema_fast,
                ema_slow=ema_slow,
                macd_fast=macd_fast,
                macd_slow=macd_slow,
                macd_signal=macd_signal,
                kdj_period=kdj_period,
                kdj_signal=kdj_signal,
            )
            states = evaluate_strategy_timeline(df_ind, max_wait_bars=max_wait_bars)
            latest_state = states[-1]

            chart_path = os.path.join(charts_dir, f"{ticker}.png")
            generate_stock_chart(ticker, df_ind, states, chart_path, lookback_bars=95)

            recent_signals = [
                asdict(st)
                for st in reversed(states[-180:])
                if st.action_today in ("BUY_NOW", "SELL_NOW", "WAIT_CONFIRM_BUY", "WAIT_CONFIRM_SELL")
            ][:10]

            is_liquid = passes_us_liquidity_filter(df)

            scan_results.append(
                {
                    "ticker": ticker,
                    "latest": asdict(latest_state),
                    "recent_signals": recent_signals,
                    "chart_path": chart_path,
                    "is_liquid": is_liquid,
                }
            )
        except Exception as exc:
            print(f"[Error] {ticker}: {exc}")

    # -------------------------------------------------------------
    # 2. Risk Management & Position Evaluation for Bot 1
    # -------------------------------------------------------------
    risk_manager = US6ButtonRiskManager(cfg)
    exit_tracker = US6ButtonExitTracker(cfg)
    exit_actions = []

    scan_date_val = scan_results[0]["latest"]["date"] if scan_results else datetime.now().strftime("%Y-%m-%d")
    scan_results_map = {x["ticker"]: x for x in scan_results}

    # Evaluate Active Portfolio Positions
    updated_portfolio = {}
    for tk, pos in list(portfolio.items()):
        df_pos = dfs.get(tk)
        if df_pos is None or len(df_pos) < 15:
            updated_portfolio[tk] = pos
            continue

        latest_action = scan_results_map.get(tk, {}).get("latest", {}).get("action_today", "")
        up_pos, actions = exit_tracker.evaluate_position(pos, df_pos, action_today=latest_action)
        for act in actions:
            exit_actions.append(act)
            print(f"Action (Bot 1): {act['message']}")

        if up_pos.get("current_shares", 1) == 0 or up_pos.get("status", "").startswith("CLOSED"):
            _record_closed_trade(
                cfg,
                tk,
                pos,
                sell_price=float(up_pos.get("exit_price", df_pos["Close"].iloc[-1])),
                sell_date=str(up_pos.get("exit_date", scan_date_val)),
                exit_reason=str(up_pos.get("exit_reason", "Closed")),
                realized_pnl=float(up_pos.get("total_realized_pnl", 0.0)),
                r_multiple=float(up_pos.get("current_r", 0.0))
            )
            print(f"Auto-Paper Trade Closed (Bot 1): {tk} | Reason: {up_pos.get('exit_reason')}")
        else:
            updated_portfolio[tk] = up_pos

    portfolio = updated_portfolio

    # Process New BUY_NOW Signals with R-Multiple Sizing
    buy_now_list = [x for x in scan_results if x["latest"]["action_today"] == "BUY_NOW"]
    sell_now_list = [x for x in scan_results if x["latest"]["action_today"] == "SELL_NOW"]

    for item in buy_now_list:
        tk = item["ticker"]
        if tk not in portfolio:
            if not item.get("is_liquid", True):
                print(f"[Liquidity] {tk} ไม่ผ่านเกณฑ์สภาพคล่อง US (Avg Vol < 500k หรือ ราคา < $5) -> ข้ามการเข้าซื้อ")
                continue

            df_item = dfs.get(tk)
            st = item["latest"]
            pos_calc = risk_manager.calculate_position(tk, df_item, st["close"])
            if pos_calc:
                pos_calc["buy_date"] = scan_date_val
                pos_calc["entry_date"] = scan_date_val
                pos_calc["buy_price"] = pos_calc["entry_price"]
                pos_calc["auto_paper_trade"] = True
                portfolio[tk] = pos_calc
                print(f"Auto-Paper Trade Entry (Bot 1): {tk} @ ${pos_calc['entry_price']:.2f} | Shares: {pos_calc['shares']} | SL: ${pos_calc['current_sl']:.2f} | 3R: ${pos_calc['target_3r']:.2f}")

    cfg["portfolio"] = portfolio

    # -------------------------------------------------------------
    # 3. Decouple State Persistence: Save config immediately!
    # -------------------------------------------------------------
    today_th = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d")
    cfg["last_daily_scan_date"] = today_th
    save_copy = {k: v for k, v in cfg.items() if not k.startswith("_")}
    _atomic_save_config(full_config_path, save_copy)
    print(f"[State Saved] บันทึกสถานะพอร์ต Bot 1 และประวัติเทรดลงไฟล์เรียบร้อยที่ {full_config_path}")

    # Separate into 3 Zones
    portfolio_tickers = set(portfolio.keys())
    zone1_portfolio = sorted(
        [x for x in scan_results if x["ticker"] in portfolio_tickers],
        key=_score_portfolio_exit_urgency,
    )
    zone2_buy = sorted(
        [x for x in scan_results if x["ticker"] not in portfolio_tickers and (x["latest"].get("dot_colors") or ["W"])[-1] in ("G", "BUY_Rocket", "HOLD_ChartUp")],
        key=_score_stock_progress,
    )
    zone3_sell = sorted(
        [x for x in scan_results if x["ticker"] not in portfolio_tickers and (x["latest"].get("dot_colors") or ["W"])[-1] not in ("G", "BUY_Rocket", "HOLD_ChartUp")],
        key=_score_stock_progress,
    )

    setup_buy_list = [
        x for x in scan_results if x["latest"]["action_today"] in ("WAIT_CONFIRM_BUY", "MACD_DOT_BUY", "COUNTING_BUY")
    ]
    setup_sell_list = [
        x for x in scan_results if x["latest"]["action_today"] in ("WAIT_CONFIRM_SELL", "MACD_DOT_SELL", "COUNTING_SELL")
    ]

    print("\n⚡ ACTION ALERT — สัญญาณต้องจับตาวันนี้")
    print("─" * 35)
    if buy_now_list:
        print(f"🚀 เข้าซื้อวันนี้ ({len(buy_now_list)}):")
        for item in buy_now_list:
            st = item["latest"]
            print(f"  {item['ticker']:<5} {_compact_buttons(st)} ${st['close']:.2f}")
    else:
        print("🚀 เข้าซื้อวันนี้: (ไม่มี)")

    if sell_now_list:
        print(f"🚨 ขายออกวันนี้ ({len(sell_now_list)}):")
        for item in sell_now_list:
            st = item["latest"]
            print(f"  {item['ticker']:<5} {_compact_buttons(st)} ${st['close']:.2f}")
    else:
        print("🚨 ขายออกวันนี้: (ไม่มี)")

    # Build Web Dashboard for Bot 1
    bot1_path = os.path.join(PROJECT_ROOT, "docs", "bot1.html")
    build_dashboard_html(scan_results, portfolio, bot1_path)
    print(f"\n[สำเร็จ] อัปเดตหน้าเว็บกระดานเม็ดกระดุม 3 โซน (Bot 1) เรียบร้อยที่: {bot1_path}")

    # Send Exit Actions to Telegram
    for act in exit_actions:
        send_telegram_message(act["message"])

    # Send Daily Board Telegram Notification
    if scan_results:
        scan_date = scan_results[0]["latest"]["date"]
        board_msg = format_daily_board_message(scan_results, portfolio, scan_date)
        send_telegram_message(board_msg)

        for item in scan_results:
            tk = item["ticker"]
            st = item["latest"]
            in_port = tk in portfolio_tickers
            ext_info = format_ema21_extension_info(st)
            ext_line = f"\n{ext_info}" if ext_info else ""

            if in_port and (
                st["action_today"] in ("SELL_NOW", "WAIT_CONFIRM_SELL", "MACD_DOT_SELL")
                or (st["side"] == "SELL" and st.get("ema_fast", 0) > 0 and st["close"] < st["ema_fast"])
            ):
                pos_info = portfolio.get(tk, {})
                bp = float(pos_info.get("entry_price", pos_info.get("buy_price", 0.0)))
                pnl_str = f" | ทุน ${bp:.2f} ({((st['close'] - bp) / bp) * 100.0:+.1f}%)" if bp > 0 else ""
                reply_markup = {
                    "inline_keyboard": [
                        [{"text": f"💰 บันทึกว่าขาย {tk} ออกแล้ว (${st['close']:.2f})", "callback_data": f"SELL:{tk}:{st['close']:.2f}"}]
                    ]
                }
                caption = (
                    f"🚨 <b>เตือนหุ้นในโซน 1 (พอร์ตกระดุม 6 เม็ด): {tk}</b> (${st['close']:.2f}{pnl_str})\n"
                    f"กระดุม: {st['buttons_visual']}\n"
                    f"สถานะ: <b>{format_portfolio_exit_status(st)}</b>{ext_line}"
                )
                send_telegram_photo(item["chart_path"], caption, reply_markup=reply_markup)

            elif (not in_port) and st["action_today"] in ("BUY_NOW", "WAIT_CONFIRM_BUY") and item.get("is_liquid", True):
                reply_markup = {
                    "inline_keyboard": [
                        [{"text": f"✅ ซื้อ {tk} เข้าพอร์ต (${st['close']:.2f})", "callback_data": f"BUY:{tk}:{st['close']:.2f}"}]
                    ]
                }
                caption = (
                    f"🚀 <b>สัญญาณฝั่งซื้อ Watchlist: {tk}</b> (${st['close']:.2f})\n"
                    f"กระดุม: {st['buttons_visual']}\n"
                    f"สถานะ: <b>{st['status_text']}</b>{ext_line}"
                )
                send_telegram_photo(item["chart_path"], caption, reply_markup=reply_markup)

    # Weekly Summary Report (Friday / Saturday for US)
    if datetime.now().weekday() in (4, 5):
        send_weekly_summary_6button(cfg, is_thai=False, bot_label="US 6-Button (Bot 1)")

    return scan_results


if __name__ == "__main__":
    run_scan()
