"""
Main Orchestration Scanner for Bot 3
(US Trend Leader Pullback & R-Multiple Strategy)

Workflow:
1. Update & Evaluate Active Positions (SL, 3R, 5R, Trailing EMA 9, Overextended Trim)
2. Screener [1/4]: Momentum & VCP Base Candidates
3. Confluence [2/4]: First Retest & Pullback Zone Detection
4. Trigger & Risk Plan [3/4]: Breakout High Trigger, SL, Position Sizing (0.5% Risk)
5. Chart Generation: Visual levels for Entry, SL, 3R, 5R
6. Telegram Notifications: Signals, Exits, and Daily Summary
7. Web Dashboard Generation
"""

from datetime import datetime
import json
import os
import sys
from typing import Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure package root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot3_pullback.src.screener import BaseScreener
from bot3_pullback.src.confluence_engine import ConfluenceEngine
from bot3_pullback.src.risk_manager import RiskManager
from bot3_pullback.src.exit_tracker import ExitTracker
from bot3_pullback.src.chart_generator import generate_pullback_chart
from bot3_pullback.src.telegram_notifier import TelegramNotifier
from bot3_pullback.src.dashboard_builder import build_dashboard_html


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")


def load_config() -> Dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: Dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def run_bot3_pipeline():
    print("=" * 60)
    print("🚀 STARTING BOT 3: US TREND PULLBACK & R-MULTIPLE SCANNER")
    print("=" * 60)

    config = load_config()
    today_str = datetime.now().strftime("%Y-%m-%d")

    screener = BaseScreener(config)
    confluence_engine = ConfluenceEngine(config)
    risk_manager = RiskManager(config)
    exit_tracker = ExitTracker(config)
    notifier = TelegramNotifier()

    # ----------------------------------------------------
    # Phase 1: Evaluate Active Positions (Exit Management)
    # ----------------------------------------------------
    active_positions = config.get("active_positions", {})
    trade_history = config.get("trade_history", [])
    updated_active = {}

    if active_positions:
        print(f"\n[Phase 1] Evaluating {len(active_positions)} active positions...")
        for ticker, pos in list(active_positions.items()):
            df_daily, _ = screener.fetch_data(ticker, period="6mo")
            if df_daily is not None:
                updated_pos, actions = exit_tracker.evaluate_position(pos, df_daily)

                # Send Telegram notifications for actions
                for act in actions:
                    print(f"Action on {ticker}: {act['message']}")
                    notifier.send_message(act["message"])

                # If position closed, move to history
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

    # ----------------------------------------------------
    # Phase 2: Screener [1/4] Strong Base & Momentum
    # ----------------------------------------------------
    universe = config.get("universe", [])
    print(f"\n[Phase 2] Screening Universe of {len(universe)} US Tickers...")
    all_screened = screener.scan_universe(universe)

    strong_base_candidates = [c for c in all_screened if c.get("step1_passed")]
    print(f"-> {len(strong_base_candidates)} tickers qualified Step [1/4] Strong Base.")

    # ----------------------------------------------------
    # Phase 3 & 4: Confluence Support [2/4] & Trigger [3/4]
    # ----------------------------------------------------
    print(f"\n[Phase 3 & 4] Evaluating Confluence Support & Triggers...")
    buy_signals = []
    pullback_candidates = []

    # Evaluate the top candidates
    eval_pool = strong_base_candidates if len(strong_base_candidates) >= 5 else all_screened[:15]
    for cand in eval_pool:
        df_daily = cand["df_daily"]
        tk = cand["ticker"]

        setup_info = confluence_engine.evaluate_entry_trigger(df_daily)
        cand["setup"] = setup_info

        # Check if in pullback zone
        if setup_info["in_pullback_zone"]:
            pullback_candidates.append(cand)

        # Check if Buy Trigger Fired
        if setup_info["status"] == "BUY_TRIGGERED":
            # Step [3/4] Calculate Risk & Sizing Plan
            entry_price = setup_info["curr_close"]
            curr_low = setup_info["curr_low"]
            prior_low = setup_info["prior_low"]

            plan = risk_manager.calculate_trade_plan(
                ticker=tk,
                entry_price=entry_price,
                curr_low=curr_low,
                prior_low=prior_low,
            )

            # Generate Chart with annotated levels
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

            print(f"🔥 BUY TRIGGER for ${tk}: Entry ${plan.entry_price:.2f}, SL ${plan.stop_loss:.2f}, Shares {plan.shares}")

    # Generate charts for remaining pullback candidates so user can view on dashboard
    for cand in pullback_candidates:
        tk = cand["ticker"]
        generate_pullback_chart(
            ticker=tk,
            df=cand["df_daily"],
            setup_info=cand["setup"],
            trade_plan=None,
        )

    # ----------------------------------------------------
    # Phase 5: Build Dashboard & Send Summary
    # ----------------------------------------------------
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

    # Send daily summary report
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
    # Send One-Page Compact Report (แบบที่ 2 มินิมอล ข้อความเดียวจบ)
    notifier.send_compact_daily_report(summary, buy_signals)

    # Update config
    config["last_scan_date"] = today_str
    save_config(config)

    print("\n" + "=" * 60)
    print(f"✅ SCAN COMPLETED! Found {len(buy_signals)} Buy Signals, {len(pullback_candidates)} Pullback Setups.")
    print("=" * 60)
    return {
        "buy_signals": buy_signals,
        "pullback_candidates": pullback_candidates,
        "strong_base_candidates": strong_base_candidates,
        "dashboard_path": dashboard_path,
    }


if __name__ == "__main__":
    run_bot3_pipeline()
