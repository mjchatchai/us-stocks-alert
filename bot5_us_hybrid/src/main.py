from dataclasses import asdict
"""
Main Execution Pipeline for Bot 5 (US Hybrid Master Bot)
"""
import os
import sys
import json
from datetime import datetime
import yfinance as yf
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot5_us_hybrid.src.strategy_engine import USHybridEngine
from bot5_us_hybrid.src.risk_manager import USRiskManager
from bot5_us_hybrid.src.exit_tracker import USHybridExitTracker
from bot5_us_hybrid.src.telegram_notifier import USTelegramNotifier
from bot5_us_hybrid.src.dashboard_builder import build_dashboard_html

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def run_pipeline():
    print("=" * 60)
    print("🇺🇸 STARTING BOT 5: US HYBRID MASTER SCANNER")
    print("=" * 60)

    config = load_config()
    today_str = datetime.now().strftime("%Y-%m-%d")

    engine = USHybridEngine(config)
    risk_manager = USRiskManager(config)
    exit_tracker = USHybridExitTracker(config)
    notifier = USTelegramNotifier()

    active_positions = config.get("active_positions", {})
    trade_history = config.get("trade_history", [])
    updated_active = {}

    # 1. Evaluate Active Positions
    if active_positions:
        print(f"Evaluating {len(active_positions)} active positions...")
        for ticker, pos in list(active_positions.items()):
            try:
                df = yf.download(ticker, period="6mo", interval="1d", progress=False)
                if df.columns.nlevels > 1:
                    df.columns = df.columns.get_level_values(0)
            except Exception:
                df = None

            if df is not None and len(df) >= 30:
                up_pos, actions = exit_tracker.evaluate_position(pos, df)
                for act in actions:
                    print(f"Action: {act['message']}")
                    notifier.send_message(act["message"])

                if up_pos["current_shares"] == 0 or up_pos.get("status", "").startswith("CLOSED"):
                    trade_history.append({
                        "ticker": ticker,
                        "entry_date": up_pos.get("entry_date", "-"),
                        "exit_date": up_pos.get("exit_date", today_str),
                        "entry_price": up_pos.get("entry_price", 0.0),
                        "exit_price": up_pos.get("exit_price", 0.0),
                        "shares": pos.get("shares", 0),
                        "realized_pnl": up_pos.get("total_realized_pnl", 0.0),
                        "r_multiple": up_pos.get("current_r", 0.0),
                        "exit_reason": up_pos.get("exit_reason", "-")
                    })
                else:
                    updated_active[ticker] = up_pos
            else:
                updated_active[ticker] = pos

        config["active_positions"] = updated_active
        config["trade_history"] = trade_history

    # 2. Scan Universe for New Signals
    universe = config.get("universe", [])
    print(f"Scanning {len(universe)} US Leaders...")

    new_signals = []
    for ticker in universe:
        if ticker in updated_active:
            continue
        try:
            df = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df.columns.nlevels > 1:
                df.columns = df.columns.get_level_values(0)
        except Exception:
            continue

        sig = engine.evaluate_ticker(ticker, df)
        if sig:
            plan = risk_manager.calculate_trade_plan(
                ticker=sig.ticker,
                entry_price=sig.entry_price,
                curr_low=sig.curr_low,
                prior_low=sig.prior_low
            )
            s_dict = asdict(sig)
            s_dict["curr_close"] = sig.entry_price
            s_dict["curr_high"] = sig.entry_price * 1.01
            s_dict["zone_bottom"] = sig.support_level * 0.99
            s_dict["zone_top"] = sig.support_level * 1.01
            s_dict["ema9"] = sig.entry_price
            s_dict["ema21"] = sig.support_level
            s_dict["avwap"] = sig.support_level
            s_dict["prior_high"] = sig.entry_price
            s_dict["is_first_retest"] = True
            s_dict["reversal_confirmed"] = True
            s_dict["in_pullback_zone"] = True
            s_dict["stage"] = "Stage 2 (Pullback Retest)"
            new_signals.append({
                "ticker": sig.ticker,
                "signal": sig,
                "setup": s_dict,
                "plan": plan,
                "close": sig.entry_price,
                "rs_percentile": 85,
                "ret_1m": sig.perf_3m / 3.0,
                "ret_3m": sig.perf_3m,
                "ret_6m": sig.perf_6m,
                "vol_20": getattr(sig, 'volume_20d', getattr(sig, 'turnover_20d', 1000000)),
                "higher_low_ok": True,
                "vcp_ok": True,
                "ema_flattening_or_up": True
            })

    print(f"Found {len(new_signals)} valid Hybrid setups!")

    # 3. Send Telegram Alerts
    lines = [
        f"🎯 <b>US HYBRID SCAN</b> • <code>{today_str}</code>",
        "━━━━━━━━━━━━━━"
    ]
    buttons = []
    if new_signals:
        for item in new_signals[:3]:
            s = item["signal"]
            p = item["plan"]
            r_pct = (((p.entry_price - p.stop_loss) / p.entry_price) * 100.0)

            lines.append(f"🟢 <b>${s.ticker}</b>")
            lines.append(f"├ เข้า: <code>${p.entry_price:.2f}</code> | SL: <code>${p.stop_loss:.2f}</code> (-{r_pct:.1f}%)")
            lines.append(f"├ ซื้อ: <b>{p.shares} sh</b> (${p.capital_allocated:,.0f})")
            lines.append(f"└ เป้า 3R: <code>${p.target_3r:.2f}</code>")
            lines.append("")

            buttons.append([
                {"text": f"✅ ซื้อ ${s.ticker} ({p.shares} sh)", "callback_data": f"bot5_buy_{s.ticker}_{p.shares}_{p.entry_price:.2f}"},
                {"text": f"📈 กราฟ ${s.ticker}", "url": f"https://www.tradingview.com/chart/?symbol={s.ticker}"}
            ])
    else:
        lines.append("⚪ <b>ไม่มีสัญญาณซื้อใหม่</b>")

    markup = {"inline_keyboard": buttons} if buttons else None
    notifier.send_message("\n".join(lines), reply_markup=markup)

    config["last_scan_date"] = today_str
    save_config(config)

    # 4. Build Web Dashboard
    os.makedirs("bot5_us_hybrid/docs", exist_ok=True)
    build_dashboard_html(
        config=config,
        buy_signals=new_signals,
        pullback_candidates=new_signals,
        all_screened=new_signals,
        active_positions=config.get("active_positions", {}),
        trade_history=config.get("trade_history", []),
        last_scan_date=today_str,
        output_path="bot5_us_hybrid/docs/index.html"
    )
    print("Bot 5 Pipeline completed successfully!")

if __name__ == "__main__":
    run_pipeline()
