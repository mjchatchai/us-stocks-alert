"""
Main Scanner Script for US Stock 6-Button Strategy (3-Zone Edition)
- Syncs /buy, /sell, /add, /remove commands from Telegram Bot
- Reads config/watchlist.json
- Fetches 1D OHLCV data for each US stock
- Computes EMA 9/21, ChrisMoody MACD (12,26,9), and ll21LAMBO21 KDJ (9,3)
- Runs the 6-Button Sequential Strategy Engine (แบบ ก. Strict Reset)
- Separates output into 3 distinct sections:
  1. 💼 โซนที่ 1: หุ้นในพอร์ต (สั่งซื้อแล้ว — รอจังหวะขายออกเมื่อครบ 6 เม็ดแดง)
  2. 🟢 โซนที่ 2: Watchlist ขาขึ้น (KDJ เขียว — รอจังหวะเข้าซื้อเมื่อครบ 6 เม็ดเขียว)
  3. 🔴 โซนที่ 3: Watchlist ขาลง (KDJ แดง — พักตัว/ขาลง)
- Generates 3-pane TradingView-style charts (docs/charts/*.png)
- Builds the Web Dashboard (docs/index.html)
- Sends Telegram summary & chart alerts with interactive buttons
"""

import json
import os
import sys
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
from src.telegram_notifier import (
    _compact_buttons,
    _score_portfolio_exit_urgency,
    _score_stock_progress,
    format_daily_board_message,
    format_portfolio_exit_status,
    send_telegram_message,
    send_telegram_photo,
    sync_telegram_commands,
)


def run_scan(config_path: str = "config/watchlist.json") -> List[Dict[str, Any]]:
    full_config_path = os.path.join(PROJECT_ROOT, config_path)
    with open(full_config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # 1. Sync any queued commands (/buy, /sell, /add, /remove) from Telegram
    cfg = sync_telegram_commands(cfg, full_config_path)

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

            scan_results.append(
                {
                    "ticker": ticker,
                    "latest": asdict(latest_state),
                    "recent_signals": recent_signals,
                    "chart_path": chart_path,
                }
            )
        except Exception as exc:
            print(f"[Error] {ticker}: {exc}")

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

    buy_now_list = [x for x in scan_results if x["latest"]["action_today"] == "BUY_NOW"]
    sell_now_list = [x for x in scan_results if x["latest"]["action_today"] == "SELL_NOW"]
    setup_buy_list = [
        x for x in scan_results if x["latest"]["action_today"] in ("WAIT_CONFIRM_BUY", "MACD_DOT_BUY", "COUNTING_BUY")
    ]
    setup_sell_list = [
        x for x in scan_results if x["latest"]["action_today"] in ("WAIT_CONFIRM_SELL", "MACD_DOT_SELL", "COUNTING_SELL")
    ]

    print("\n⚡ ACTION ALERT — สัญญาณต้องจับตาวันนี้")
    print("─" * 35)
    print(f"  🚀 เข้าซื้อวันนี้ (BUY NOW): {', '.join(x['ticker'] for x in buy_now_list) if buy_now_list else '(ไม่มี)'}")
    print(f"  🚨 ขายออกวันนี้ (SELL NOW): {', '.join(x['ticker'] for x in sell_now_list) if sell_now_list else '(ไม่มี)'}")
    if setup_buy_list:
        print(f"  🟢 จ่อซื้อ (เม็ด 2–4): {', '.join(f\"{x['ticker']}({_compact_buttons(x['latest'])})\" for x in setup_buy_list)}")
    if setup_sell_list:
        print(f"  ⚠️ เฝ้าระวังย่อ/จ่อขาย (เม็ดแดง 2–4): {', '.join(f\"{x['ticker']}({_compact_buttons(x['latest'])})\" for x in setup_sell_list)}")

    print(f"\n💼 โซน 1: หุ้นในพอร์ต ({len(zone1_portfolio)})")
    print("─" * 35)
    for item in zone1_portfolio:
        st = item["latest"]
        print(f"  {item['ticker']:<5} {_compact_buttons(st)} ${st['close']:.2f}")

    print(f"\n🟢 โซน 2: Watchlist ขาขึ้น ({len(zone2_buy)})")
    print("─" * 35)
    for item in zone2_buy:
        st = item["latest"]
        print(f"  {item['ticker']:<5} {_compact_buttons(st)} ${st['close']:.2f}")

    print(f"\n🔴 โซน 3: Watchlist ขาลง ({len(zone3_sell)})")
    print("─" * 35)
    for item in zone3_sell:
        st = item["latest"]
        print(f"  {item['ticker']:<5} {_compact_buttons(st)} ${st['close']:.2f}")

    # Build Web Dashboard
    dashboard_path = os.path.join(PROJECT_ROOT, "docs", "index.html")
    build_dashboard_html(scan_results, portfolio, dashboard_path)
    print(f"\n[สำเร็จ] อัปเดตหน้าเว็บกระดานเม็ดกระดุม 3 โซนเรียบร้อยที่: {dashboard_path}")

    # Send Telegram Notifications if configured
    if scan_results:
        scan_date = scan_results[0]["latest"]["date"]
        board_msg = format_daily_board_message(scan_results, portfolio, scan_date)
        sent = send_telegram_message(board_msg)
        if sent:
            for item in scan_results:
                tk = item["ticker"]
                st = item["latest"]
                in_port = tk in portfolio_tickers

                if in_port and st["action_today"] in ("SELL_NOW", "WAIT_CONFIRM_SELL"):
                    reply_markup = {
                        "inline_keyboard": [
                            [{"text": f"💰 บันทึกว่าขาย {tk} ออกแล้ว", "callback_data": f"SELL:{tk}"}]
                        ]
                    }
                    caption = (
                        f"🚨 <b>เตือนขายหุ้นในพอร์ต: {tk}</b> (${st['close']:.2f})\n"
                        f"กระดุม: {st['buttons_visual']}\n"
                        f"สถานะ: <b>{format_portfolio_exit_status(st)}</b>"
                    )
                    send_telegram_photo(item["chart_path"], caption, reply_markup=reply_markup)

                elif (not in_port) and st["action_today"] in ("BUY_NOW", "WAIT_CONFIRM_BUY"):
                    reply_markup = {
                        "inline_keyboard": [
                            [{"text": f"✅ ซื้อ {tk} เข้าพอร์ต (${st['close']:.2f})", "callback_data": f"BUY:{tk}:{st['close']:.2f}"}]
                        ]
                    }
                    caption = (
                        f"🚀 <b>สัญญาณฝั่งซื้อ Watchlist: {tk}</b> (${st['close']:.2f})\n"
                        f"กระดุม: {st['buttons_visual']}\n"
                        f"สถานะ: <b>{st['status_text']}</b>"
                    )
                    send_telegram_photo(item["chart_path"], caption, reply_markup=reply_markup)

    return scan_results


if __name__ == "__main__":
    run_scan()
