"""
Main Pipeline for Bot 4 (Thai Stocks Pullback & R-Multiple Strategy)
Portfolio: 1,000,000 Baht | Risk: 0.5% (5,000 Baht) | Board Lot: 100 shares
"""

from datetime import datetime
import json
import os
import sys
from typing import Dict, List

# Ensure utf-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot4_thai_pullback.src.screener import ThaiBaseScreener
from bot4_thai_pullback.src.confluence_engine import ThaiConfluenceEngine
from bot4_thai_pullback.src.risk_manager import ThaiRiskManager
from bot4_thai_pullback.src.exit_tracker import ThaiExitTracker
from bot4_thai_pullback.src.chart_generator import generate_pullback_chart
from bot4_thai_pullback.src.telegram_notifier import ThaiTelegramNotifier
from bot4_thai_pullback.src.dashboard_builder import build_dashboard_html


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")


def load_config() -> Dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: Dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def run_bot4_pipeline():
    print("=" * 60)
    print("🇹🇭 STARTING BOT 4: THAI STOCKS PULLBACK & R-MULTIPLE SCANNER")
    print("=" * 60)

    config = load_config()
    today_str = datetime.now().strftime("%Y-%m-%d")

    screener = ThaiBaseScreener(config)
    confluence_engine = ThaiConfluenceEngine(config)
    risk_manager = ThaiRiskManager(config)
    exit_tracker = ThaiExitTracker(config)
    notifier = ThaiTelegramNotifier()

    # 1. Evaluate Active Positions
    active_positions = config.get("active_positions", {})
    trade_history = config.get("trade_history", [])
    updated_active = {}

    if active_positions:
        print(f"\n[Phase 1] Evaluating {len(active_positions)} active Thai positions...")
        for ticker, pos in list(active_positions.items()):
            df_daily, _ = screener.fetch_data(ticker, period="6mo")
            if df_daily is not None:
                updated_pos, actions = exit_tracker.evaluate_position(pos, df_daily)
                for act in actions:
                    print(f"Action on {ticker}: {act['message']}")
                    notifier.send_message(act["message"])

                if updated_pos["current_shares"] == 0 or updated_pos.get("status", "").startswith("CLOSED"):
                    trade_history.append({
                        "ticker": ticker,
                        "entry_date": updated_pos.get("entry_date", "-"),
                        "exit_date": updated_pos.get("exit_date", today_str),
                        "entry_price": updated_pos.get("entry_price", 0.0),
                        "exit_price": updated_pos.get("exit_price", 0.0),
                        "exit_reason": updated_pos.get("exit_reason", "-"),
                        "realized_pnl": updated_pos.get("total_realized_pnl", 0.0),
                        "r_multiple": updated_pos.get("current_r", 0.0),
                    })
                else:
                    updated_active[ticker] = updated_pos
            else:
                updated_active[ticker] = pos

        config["active_positions"] = updated_active
        config["trade_history"] = trade_history

    # 2. Screener [1/4]
    universe = config.get("universe", [])
    print(f"\n[Phase 2] Screening Universe of {len(universe)} Thai Tickers...")
    all_screened = screener.scan_universe(universe)
    strong_base_candidates = [c for c in all_screened if c.get("step1_passed")]
    print(f"-> {len(strong_base_candidates)} tickers qualified Step [1/4] Strong Base.")

    # 3 & 4. Confluence Support [2/4] & Trigger [3/4]
    print(f"\n[Phase 3 & 4] Evaluating Confluence Support & Triggers...")
    buy_signals = []
    pullback_candidates = []

    eval_pool = strong_base_candidates if len(strong_base_candidates) >= 5 else all_screened[:15]
    for cand in eval_pool:
        df_daily = cand["df_daily"]
        tk = cand["ticker"]

        setup_info = confluence_engine.evaluate_entry_trigger(df_daily)
        cand["setup"] = setup_info

        if setup_info["in_pullback_zone"]:
            pullback_candidates.append(cand)

        if setup_info["status"] == "BUY_TRIGGERED":
            entry_price = setup_info["curr_close"]
            curr_low = setup_info["curr_low"]
            prior_low = setup_info["prior_low"]

            plan = risk_manager.calculate_trade_plan(
                ticker=tk,
                entry_price=entry_price,
                curr_low=curr_low,
                prior_low=prior_low,
            )

            chart_path = generate_pullback_chart(
                ticker=tk,
                df=df_daily,
                setup_info=setup_info,
                trade_plan=plan,
            )

            buy_signals.append({
                "ticker": tk,
                "plan": plan,
                "setup": setup_info,
                "chart_path": chart_path,
            })
            print(f"🔥 BUY TRIGGER for {tk}: Entry {plan.entry_price:.2f} B, SL {plan.stop_loss:.2f} B, Shares {plan.shares:,}")

    for cand in pullback_candidates:
        tk = cand["ticker"]
        generate_pullback_chart(
            ticker=tk,
            df=cand["df_daily"],
            setup_info=cand["setup"],
            trade_plan=None,
        )

    # 5. Build Dashboard & Send Summary
    print(f"\n[Phase 5] Building HTML Dashboard...")
    dashboard_path = build_dashboard_html(
        config=config,
        buy_signals=buy_signals,
        pullback_candidates=pullback_candidates,
        all_screened=all_screened,
        active_positions=config.get("active_positions", {}),
        trade_history=config.get("trade_history", []),
        last_scan_date=today_str,
    )
    print(f"-> Dashboard saved to {dashboard_path}")

    summary = {
        "date": today_str,
        "total_scanned": len(universe),
        "strong_base_count": len(strong_base_candidates),
        "in_pullback_count": len(pullback_candidates),
        "buy_signals_count": len(buy_signals),
        "open_trades_count": len(config.get("active_positions", {})),
        "buy_tickers": [s["ticker"] for s in buy_signals],
        "pullback_tickers": [p["ticker"] for p in pullback_candidates],
    }

    # Send One-Page Compact Report
    notifier.send_compact_daily_report(summary, buy_signals)

    config["last_scan_date"] = today_str
    save_config(config)

    print("\n" + "=" * 60)
    print(f"✅ BOT 4 SCAN COMPLETED! Found {len(buy_signals)} Buy Signals, {len(pullback_candidates)} Pullback Setups.")
    print("=" * 60)
    return {
        "buy_signals": buy_signals,
        "pullback_candidates": pullback_candidates,
        "strong_base_candidates": strong_base_candidates,
        "dashboard_path": dashboard_path,
    }


if __name__ == "__main__":
    run_bot4_pipeline()
