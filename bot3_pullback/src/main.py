from datetime import datetime

def send_weekly_summary(notifier, config, is_thai=False, bot_label="US PULLBACK (Bot 3)"):
    history = config.get("trade_history", [])
    active = config.get("active_positions", {})
    total = len(history)
    wins = sum(1 for h in history if float(h.get("realized_pnl", 0)) > 0)
    win_rate = (wins / total * 100.0) if total > 0 else 0.0
    total_r = sum(float(h.get("r_multiple", 0)) for h in history)
    
    win_rs = [float(h.get("r_multiple", 0)) for h in history if float(h.get("r_multiple", 0)) > 0]
    loss_rs = [float(h.get("r_multiple", 0)) for h in history if float(h.get("r_multiple", 0)) < 0]
    avg_win_r = (sum(win_rs) / len(win_rs)) if win_rs else 0.0
    avg_loss_r = (sum(loss_rs) / len(loss_rs)) if loss_rs else 0.0
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"📊 <b>WEEKLY FORWARD TEST REPORT</b> • <code>{today_str}</code>",
        f"<b>{bot_label}</b>",
        "━━━━━━━━━━━━━━━━",
        f"• หุ้นในพอร์ตปัจจุบัน: <code>{len(active)} ตัว</code>",
        f"• ไม้ปิดรอบสะสม: <code>{total} ไม้</code>",
        f"• Win Rate: <code>{win_rate:.1f}%</code> (ชนะ {wins} / แพ้ {total - wins})",
        f"• กำไรสะสมสุทธิ: <code>{total_r:+.2f}R</code>",
    ]
    if win_rs or loss_rs:
        lines.append(f"• ชนะเฉลี่ย: <code>+{avg_win_r:.2f}R</code> | SL เฉลี่ย: <code>{avg_loss_r:.2f}R</code>")
    
    notifier.send_message("\n".join(lines))

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

import json
import os
import sys
import tempfile
import time
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
    max_attempts = 6
    backoff = 0.05
    for attempt in range(max_attempts):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (PermissionError, FileNotFoundError):
            if attempt == max_attempts - 1:
                raise
            time.sleep(backoff)
            backoff *= 2


def save_config(config: Dict):
    dir_name = os.path.dirname(os.path.abspath(CONFIG_PATH))
    os.makedirs(dir_name, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(dir=dir_name, text=True)
    replaced = False
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        max_attempts = 6
        backoff = 0.05
        for attempt in range(max_attempts):
            try:
                os.replace(temp_path, CONFIG_PATH)
                replaced = True
                break
            except PermissionError:
                if attempt == max_attempts - 1:
                    raise
                time.sleep(backoff)
                backoff *= 2
    finally:
        if not replaced and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


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
            try:
                df_daily, _ = screener.fetch_data(ticker, period="6mo")
            except Exception as e:
                print(f"Error fetching data for {ticker}: {e}")
                df_daily = None

            if df_daily is not None:
                try:
                    updated_pos, actions = exit_tracker.evaluate_position(pos, df_daily)

                    # Send Telegram notifications for actions
                    for act in actions:
                        print(f"Action on {ticker}: {act['message']}")
                        notifier.send_message(act["message"])

                    # If position closed, move to history
                    if updated_pos["current_shares"] == 0 or updated_pos.get("status", "").startswith("CLOSED"):
                        init_shares = int(pos.get("initial_shares", pos.get("shares", 0)))
                        init_entry = float(pos.get("entry_price", 0.0))
                        risk_per_sh = float(pos.get("risk_per_share", 0.0))
                        tot_realized = float(updated_pos.get("total_realized_pnl", 0.0))
                        init_risk_dollar = init_shares * risk_per_sh
                        true_r = round(tot_realized / init_risk_dollar, 2) if init_risk_dollar > 0 else 0.0
                        pnl_pct = round((tot_realized / (init_shares * init_entry)) * 100.0, 2) if (init_shares * init_entry) > 0 else 0.0

                        trade_history.append({
                            "ticker": ticker,
                            "entry_date": pos.get("entry_date", "-"),
                            "exit_date": updated_pos.get("exit_date", today_str),
                            "entry_price": init_entry,
                            "exit_price": float(updated_pos.get("exit_price", 0.0)),
                            "shares": init_shares,
                            "realized_pnl": tot_realized,
                            "r_multiple": true_r,
                            "pnl_r": true_r,
                            "pnl_pct": pnl_pct,
                            "exit_reason": updated_pos.get("exit_reason", "-"),
                        })
                    else:
                        updated_active[ticker] = updated_pos
                except Exception as e:
                    print(f"Error evaluating exit for {ticker}: {e}")
                    updated_active[ticker] = pos
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

            if getattr(plan, "is_valid", True) and plan.shares > 0:
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
            else:
                reason = getattr(plan, "invalid_reason", "") or getattr(plan, "warning_note", "Trade plan invalid or 0 shares")
                print(f"⚠️ REJECTED BUY TRIGGER for ${tk}: {reason}")

    # Generate charts for remaining pullback candidates so user can view on dashboard
    for cand in pullback_candidates:
        tk = cand["ticker"]
        generate_pullback_chart(
            ticker=tk,
            df=cand["df_daily"],
            setup_info=cand["setup"],
            trade_plan=None,
        )

    # Auto-Paper Trade Entry (ทุกตัวที่มีสัญญาณซื้อที่ผ่านเกณฑ์)
    auto_bought_pb = []
    for s in buy_signals:
        tk = s["ticker"]
        plan = s["plan"]
        if getattr(plan, "is_valid", True) and plan.shares > 0:
            if tk not in updated_active:
                r_per_sh = round(plan.entry_price - plan.stop_loss, 2)
                updated_active[tk] = {
                    "ticker": tk,
                    "entry_price": plan.entry_price,
                    "current_sl": plan.stop_loss,
                    "stop_loss": plan.stop_loss,
                    "risk_per_share": r_per_sh,
                    "shares": plan.shares,
                    "current_shares": plan.shares,
                    "initial_shares": plan.shares,
                    "target_3r": plan.target_3r,
                    "target_5r": getattr(plan, "target_5r", round(plan.entry_price + 5.0 * r_per_sh, 2)),
                    "entry_date": today_str,
                    "auto_paper_trade": True
                }
                auto_bought_pb.append(tk)
                print(f"Auto-Paper Trade Entry: ${tk} @ ${plan.entry_price:.2f}")

    config["active_positions"] = updated_active

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

    # Weekly Summary Report (Saturday for US)
    if datetime.now().weekday() == 5:
        send_weekly_summary(notifier, config, is_thai=False, bot_label="US PULLBACK (Bot 3)")

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