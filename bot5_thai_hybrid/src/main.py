"""
Main Execution Pipeline for Bot 5 (Thai Hybrid Master Bot)
Portfolio: 1,000,000 Baht | Risk: 0.5% (5,000 Baht) | Board Lot: 100 shares
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

from bot5_thai_hybrid.src.strategy_engine import ThaiHybridEngine
from bot5_thai_hybrid.src.risk_manager import ThaiRiskManager
from bot5_thai_hybrid.src.exit_tracker import ThaiHybridExitTracker
from bot5_thai_hybrid.src.telegram_notifier import ThaiTelegramNotifier
from bot5_thai_hybrid.src.dashboard_builder import build_dashboard_html

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def run_pipeline():
    print("=" * 60)
    print("🇹🇭 STARTING BOT 5: THAI HYBRID MASTER SCANNER")
    print("=" * 60)

    config = load_config()
    today_str = datetime.now().strftime("%Y-%m-%d")

    engine = ThaiHybridEngine(config)
    risk_manager = ThaiRiskManager(config)
    exit_tracker = ThaiHybridExitTracker(config)
    notifier = ThaiTelegramNotifier()

    active_positions = config.get("active_positions", {})
    trade_history = config.get("trade_history", [])
    updated_active = {}

    # 1. Evaluate Active Positions
    if active_positions:
        print(f"Evaluating {len(active_positions)} active Thai positions...")
        for ticker, pos in list(active_positions.items()):
            try:
                df = yf.download(f"{ticker}.BK", period="6mo", interval="1d", progress=False)
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
    print(f"Scanning {len(universe)} SET Leaders...")

    new_signals = []
    for ticker in universe:
        if ticker in updated_active:
            continue
        try:
            df = yf.download(f"{ticker}.BK", period="1y", interval="1d", progress=False)
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
            new_signals.append({
                "signal": sig,
                "plan": plan
            })

    print(f"Found {len(new_signals)} valid Thai Hybrid setups!")

    # 3. Send Telegram Alerts
    if new_signals:
        lines = [
            "🚀 <b>BOT 5: THAI HYBRID MASTER ALERT</b>",
            f"📅 <i>สแกนประจำวัน: {today_str}</i>",
            "━━━━━━━━━━━━━━━━━━━"
        ]
        for item in new_signals[:3]:
            s = item["signal"]
            p = item["plan"]
            r_pct = (((p.entry_price - p.stop_loss) / p.entry_price) * 100.0)
            tp3_pct = (((p.target_3r - p.entry_price) / p.entry_price) * 100.0)

            lines.append(f"🟢 <b>{s.ticker}</b> (โครงสร้างเทรนด์ใหญ่: กระดุมเขียวคุมรอบ 📈)")
            lines.append(f"• จุดซุ่มยิง: {s.support_type} ({s.support_level:.2f} ฿) + {s.reversal_type}")
            lines.append("• แผนการเทรด & คุมความเสี่ยง (งบ 5,000 ฿):")
            lines.append(f"  ├ <b>ราคาเข้า (Entry):</b> <code>{p.entry_price:.2f} ฿</code>")
            lines.append(f"  ├ <b>Stop Loss:</b> <code>{p.stop_loss:.2f} ฿</code> (-{r_pct:.2f}%)")
            lines.append(f"  ├ <b>จำนวนซื้อ:</b> <b>{p.shares:,} หุ้น</b> (เงินลงทุน {p.capital_allocated:,.0f} ฿)")
            lines.append(f"  ├ <b>เป้า 1 (3R):</b> <code>{p.target_3r:.2f} ฿</code> (+{tp3_pct:.2f}% ➔ <b>ขาย 50% + SL บังทุน</b>)")
            lines.append("  └ <b>เป้า 2 (Mega Trend):</b> ปล่อยรันเทรนด์ยาวจนเกิด 6 เม็ดแดง (🚨 SELL)")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 <i>วินัย: ซื้อแล้วให้ตั้งคำสั่ง Stop Loss ล่วงหน้าใน Streaming ทันทีครับ</i>")

        first_item = new_signals[0]
        f_tk = first_item["signal"].ticker
        f_sh = first_item["plan"].shares
        f_ep = first_item["plan"].entry_price

        markup = {
            "inline_keyboard": [
                [
                    {
                        "text": f"✅ ซื้อ {f_tk} ({f_sh:,} หุ้น)",
                        "callback_data": f"bot5_buy_{f_tk}_{f_sh}_{f_ep:.2f}"
                    },
                    {
                        "text": f"📈 ดูกราฟ {f_tk}",
                        "url": f"https://www.tradingview.com/chart/?symbol={f_tk}"
                    }
                ]
            ]
        }
        notifier.send_message("\n".join(lines), reply_markup=markup)

    config["last_scan_date"] = today_str
    save_config(config)

    os.makedirs("bot5_thai_hybrid/docs", exist_ok=True)
    build_dashboard_html(config, new_signals, "bot5_thai_hybrid/docs/index.html")
    print("Bot 5 Thai Pipeline completed successfully!")

if __name__ == "__main__":
    run_pipeline()
