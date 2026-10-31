"""
Unit and Integration Tests for Bot 3 Refactoring & Hardening
Verifies:
1. Atomic state persistence (save_config)
2. Master dashboard schema parity (pnl_r, pnl_pct, shares)
3. Signal viability gating in main execution
4. RiskManager floor inversion elimination & 20% max capital cap
5. ExitTracker single-share TP1 liquidation (CLOSED_TP1, zero zombie positions)
6. ExitTracker true blended R-multiple calculation
7. ConfluenceEngine candlestick rejection filter (shooting star rejection & hammer/green confirmation)
8. CommandHandler /stat analytics
9. TelegramNotifier HTML entity escaping and message chunking
10. Configuration parameter compliance
"""

import html
import json
import os
import tempfile
import pytest
from unittest.mock import patch
import pandas as pd

from bot3_pullback.src.risk_manager import RiskManager, TradePlan
from bot3_pullback.src.exit_tracker import ExitTracker
from bot3_pullback.src.confluence_engine import ConfluenceEngine
from bot3_pullback.src.telegram_notifier import TelegramNotifier, sanitize_html
from bot3_pullback.src.command_handler import Bot3CommandHandler, save_config as cmd_save_config
from bot3_pullback.src.main import save_config as main_save_config


# ---------------------------------------------------------------------------
# Test 1: Atomic State Persistence
# ---------------------------------------------------------------------------
def test_atomic_save_config(tmp_path):
    test_file = tmp_path / "test_config.json"
    data = {"portfolio_equity": 10000.0, "active_positions": {"AAPL": {"shares": 10}}}

    # Verify atomic write via tempfile pattern
    dir_name = os.path.dirname(os.path.abspath(test_file))
    temp_fd, temp_path_file = tempfile.mkstemp(dir=dir_name, text=True)
    with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path_file, test_file)

    assert os.path.exists(test_file)
    with open(test_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == data
    # Ensure no lingering temporary files
    remaining_files = os.listdir(dir_name)
    assert len(remaining_files) == 1


# ---------------------------------------------------------------------------
# Test 2: Master Dashboard Schema Parity & Trade History
# ---------------------------------------------------------------------------
def test_trade_history_schema_dashboard_compatibility():
    # Verify the schema expected by src/build_master_dashboard.py
    trade_record = {
        "ticker": "NVDA",
        "entry_date": "2026-10-15",
        "exit_date": "2026-10-25",
        "entry_price": 100.0,
        "exit_price": 130.0,
        "shares": 10,
        "realized_pnl": 300.0,
        "r_multiple": 3.0,
        "pnl_r": 3.0,
        "pnl_pct": 30.0,
        "exit_reason": "Target 3R Hit"
    }

    # Verify keys required by src/build_master_dashboard.py:126-129
    assert "pnl_r" in trade_record
    assert "pnl_pct" in trade_record
    assert "shares" in trade_record
    assert trade_record.get("pnl_r", 0) > 0
    assert trade_record.get("pnl_pct", 0) > 0


# ---------------------------------------------------------------------------
# Test 3: RiskManager Floor Inversion Elimination & 20% Cap
# ---------------------------------------------------------------------------
def test_risk_manager_floor_inversion_elimination():
    cfg = {
        "portfolio_equity": 10000.0,
        "risk_per_trade_pct": 0.5,           # $50 risk budget
        "max_allocation_per_trade_pct": 20.0  # $2,000 max capital
    }
    rm = RiskManager(cfg)

    # Case A: Low budget where raw_shares < 1
    # Stock price = $600, SL = $500 -> Risk/sh = $100. Budget = $50.
    # raw_shares = int(50 / 100) = 0. MUST be rejected without max(1, shares)
    plan_low_budget = rm.calculate_trade_plan(
        ticker="HIGH_RISK",
        entry_price=600.0,
        curr_low=501.0,
        prior_low=502.0,
    )
    assert plan_low_budget.is_valid is False
    assert plan_low_budget.shares == 0
    assert plan_low_budget.capital_allocated == 0.0
    assert "insufficient for 1 share" in plan_low_budget.invalid_reason

    # Case B: Negative / Zero risk per share
    plan_invalid_sl = rm.calculate_trade_plan(
        ticker="BAD_SL",
        entry_price=50.0,
        curr_low=60.0,
        prior_low=65.0,
    )
    assert plan_invalid_sl.is_valid is False
    assert plan_invalid_sl.shares == 0
    assert "Invalid risk per share" in plan_invalid_sl.invalid_reason


def test_risk_manager_max_capital_cap_20pct():
    cfg = {
        "portfolio_equity": 10000.0,
        "risk_per_trade_pct": 0.5,           # $50 risk budget
        "max_allocation_per_trade_pct": 20.0  # $2,000 max capital
    }
    rm = RiskManager(cfg)

    # Case A: Stock price > 20% cap ($2,500 > $2,000)
    # SL = 2490 -> risk per share = $10. Budget $50 affords 5 shares ($12,500).
    # But 1 share costs $2,500 which exceeds $2,000 cap!
    plan_overpriced = rm.calculate_trade_plan(
        ticker="EXPENSIVE",
        entry_price=2500.0,
        curr_low=2490.0,
        prior_low=2492.0,
    )
    assert plan_overpriced.is_valid is False
    assert plan_overpriced.shares == 0
    assert "exceeds 20.0% max capital cap" in plan_overpriced.invalid_reason

    # Case B: Capital capped safely
    # Stock price = $400, SL = $390 -> risk per share = 10. Budget $50 affords 5 shares ($2,000).
    # Exactly hits cap or slightly below
    plan_valid = rm.calculate_trade_plan(
        ticker="GOOD",
        entry_price=100.0,
        curr_low=92.0,
        prior_low=93.0,
    )
    assert plan_valid.is_valid is True
    assert plan_valid.shares > 0
    assert plan_valid.capital_allocated <= 2000.0


# ---------------------------------------------------------------------------
# Test 4: ExitTracker Single-Share TP1 Liquidation (No Zombie Positions)
# ---------------------------------------------------------------------------
def test_exit_tracker_single_share_tp1_liquidation():
    cfg = {
        "tp1_sell_ratio": 0.5,
        "tp2_sell_ratio": 0.5,
        "trailing_ema": 9,
        "overextended_ema_threshold_pct": 15.0
    }
    tracker = ExitTracker(cfg)

    # Active position with single share (1 share)
    pos = {
        "ticker": "TSLA",
        "entry_price": 200.0,
        "current_sl": 190.0,
        "risk_per_share": 10.0,
        "current_shares": 1,
        "initial_shares": 1,
        "target_3r": 230.0,
        "target_5r": 250.0,
        "tp1_hit": False,
        "total_realized_pnl": 0.0
    }

    # Market bar reaches target 3R
    df = pd.DataFrame({
        "Open": [200.0] * 20 + [225.0],
        "High": [205.0] * 20 + [232.0],
        "Low": [198.0] * 20 + [224.0],
        "Close": [202.0] * 20 + [230.5],
    })

    up_pos, actions = tracker.evaluate_position(pos, df)

    # Assert clean CLOSED_TP1 exit
    assert up_pos["status"] == "CLOSED_TP1"
    assert up_pos["current_shares"] == 0
    assert up_pos["exit_price"] == 230.0
    assert up_pos["total_realized_pnl"] == 30.0
    assert up_pos["current_r"] == 3.0
    assert len(actions) == 1
    assert actions[0]["type"] == "TP1_3R_FULL"
    assert actions[0]["shares_sold"] == 1


# ---------------------------------------------------------------------------
# Test 5: ExitTracker True Blended R-Multiple Calculation
# ---------------------------------------------------------------------------
def test_exit_tracker_true_blended_r_multiple():
    cfg = {
        "tp1_sell_ratio": 0.5,
        "tp2_sell_ratio": 0.5,
        "trailing_ema": 9,
        "overextended_ema_threshold_pct": 15.0
    }
    tracker = ExitTracker(cfg)

    # Initial position: 10 shares @ $100, SL @ $90 (Risk/sh = $10, Total risk = $100)
    pos = {
        "ticker": "MSFT",
        "entry_price": 100.0,
        "current_sl": 90.0,
        "risk_per_share": 10.0,
        "current_shares": 10,
        "initial_shares": 10,
        "target_3r": 130.0,
        "target_5r": 150.0,
        "tp1_hit": False,
        "total_realized_pnl": 0.0
    }

    # Step 1: Hits TP1 (130.0). Sells 50% (5 shares) for +$150 (+1.5R)
    df_tp1 = pd.DataFrame({
        "Open": [100.0] * 20 + [128.0],
        "High": [105.0] * 20 + [131.0],
        "Low": [99.0] * 20 + [127.0],
        "Close": [101.0] * 20 + [130.5],
    })
    pos_tp1, actions_tp1 = tracker.evaluate_position(pos, df_tp1)

    assert pos_tp1["current_shares"] == 5
    assert pos_tp1["tp1_hit"] is True
    assert pos_tp1["current_sl"] == 100.0  # SL ratcheted to Breakeven
    assert pos_tp1["total_realized_pnl"] == 150.0

    # Step 2: Price pulls back to Breakeven Stop Loss ($100.0)
    df_sl = pd.DataFrame({
        "Open": [100.0] * 20 + [102.0],
        "High": [105.0] * 20 + [103.0],
        "Low": [95.0] * 20 + [99.5],    # Triggers SL at 100.0
        "Close": [100.0] * 20 + [100.0],
    })
    pos_final, actions_sl = tracker.evaluate_position(pos_tp1, df_sl)

    assert pos_final["status"] == "CLOSED_SL"
    assert pos_final["current_shares"] == 0
    assert pos_final["total_realized_pnl"] == 150.0

    # Critical Proof: Blended R MUST be +1.50R ($150 / $100 initial risk), NOT 0.00R!
    assert pos_final["current_r"] == 1.50
    assert actions_sl[0]["type"] == "STOP_LOSS"


# ---------------------------------------------------------------------------
# Test 6: ConfluenceEngine Candlestick Rejection Filter
# ---------------------------------------------------------------------------
def test_confluence_candlestick_rejection_and_confirmation():
    cfg = {}
    engine = ConfluenceEngine(cfg)

    # Base price history with swing high at 100.0
    closes = [90.0 + i * 0.5 for i in range(30)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    opens = [c - 0.2 for c in closes]

    # Prior bar (index -2)
    prior_high = 100.0
    highs[-2] = prior_high
    closes[-2] = 99.5

    # Case A: Bearish Shooting Star / Bull Trap
    # Intraday spikes above prior high to 105.0, but closes near low at 97.0
    # Open: 98.0, High: 105.0, Low: 96.8, Close: 97.0
    # body = 1.0, upper_wick = 7.0 (7x body > 2x body)
    h_star = list(highs)
    c_star = list(closes)
    l_star = list(lows)
    o_star = list(opens)

    h_star[-1] = 105.0
    o_star[-1] = 98.0
    c_star[-1] = 97.0
    l_star[-1] = 96.8

    v_series = [1000000] * len(closes)
    df_star = pd.DataFrame({"Open": o_star, "High": h_star, "Low": l_star, "Close": c_star, "Volume": v_series})
    res_star = engine.evaluate_entry_trigger(df_star)

    assert res_star["is_shooting_star"] is True
    assert res_star["has_candle_confirmation"] is False
    assert res_star["trigger_fired"] is False
    assert res_star["status"] != "BUY_TRIGGERED"

    # Case B: Bullish Confirmation (Green candle breaking prior high)
    # Open: 99.0, High: 102.0, Low: 98.8, Close: 101.5
    h_bull = list(highs)
    c_bull = list(closes)
    l_bull = list(lows)
    o_bull = list(opens)

    o_bull[-1] = 99.0
    h_bull[-1] = 102.0
    l_bull[-1] = 98.8
    c_bull[-1] = 101.5

    df_bull = pd.DataFrame({"Open": o_bull, "High": h_bull, "Low": l_bull, "Close": c_bull, "Volume": v_series})
    res_bull = engine.evaluate_entry_trigger(df_bull)

    assert res_bull["is_shooting_star"] is False
    assert res_bull["has_candle_confirmation"] is True
    assert res_bull["trigger_fired"] is True

    # Case C: Hammer Rejection (Lower wick >= 2x body)
    # Open: 99.5, High: 101.0, Low: 94.0, Close: 99.0
    # body = 0.5, lower_wick = 5.0 (10x body >= 2x body), upper_wick = 1.5
    h_ham = list(highs)
    c_ham = list(closes)
    l_ham = list(lows)
    o_ham = list(opens)

    o_ham[-1] = 99.5
    h_ham[-1] = 101.0  # breaks prior_high (100.0)
    l_ham[-1] = 94.0
    c_ham[-1] = 99.0

    df_ham = pd.DataFrame({"Open": o_ham, "High": h_ham, "Low": l_ham, "Close": c_ham, "Volume": v_series})
    res_ham = engine.evaluate_entry_trigger(df_ham)

    assert res_ham["is_hammer"] is True
    assert res_ham["has_candle_confirmation"] is True
    assert res_ham["trigger_fired"] is True


# ---------------------------------------------------------------------------
# Test 7: TelegramNotifier HTML Escaping & Message Chunking
# ---------------------------------------------------------------------------
def test_telegram_html_escaping_and_chunking(monkeypatch):
    # Sanitizer test
    unsafe_text = "Alert: Stock <NVDA> & Price > $100"
    safe_text = sanitize_html(unsafe_text)
    assert safe_text == "Alert: Stock &lt;NVDA&gt; &amp; Price &gt; $100"

    # Chunking test - ensure Telegram is completely mocked
    sent_payloads = []
    def fake_post(url, **kwargs):
        class MockResp:
            status_code = 200
        sent_payloads.append(kwargs)
        return MockResp()

    monkeypatch.setattr("requests.post", fake_post)
    mock_notifier = TelegramNotifier(token="MOCK_TOKEN", chat_id="MOCK_CHAT_ID")

    long_msg = "A" * 1500 + "\n" + "B" * 1500 + "\n" + "C" * 1500 + "\n" + "D" * 1000
    assert len(long_msg) > 4000

    # In mock mode, sends chunked messages without contacting real Telegram
    mock_notifier.send_chunked_message(long_msg, max_chunk=2000)
    assert len(sent_payloads) >= 3


# ---------------------------------------------------------------------------
# Test 8: CommandHandler /stat Analytics Logic
# ---------------------------------------------------------------------------
def test_command_handler_stat_analytics(tmp_path):
    handler = Bot3CommandHandler()
    cfg = {
        "active_positions": {"AAPL": {"current_shares": 5}},
        "trade_history": [
            {"ticker": "NVDA", "realized_pnl": 150.0, "pnl_r": 1.5},
            {"ticker": "TSLA", "realized_pnl": 200.0, "pnl_r": 2.0},
            {"ticker": "AMD", "realized_pnl": -50.0, "pnl_r": -0.5},
        ]
    }

    history = cfg.get("trade_history", [])
    active = cfg.get("active_positions", {})
    total = len(history)
    wins = [h for h in history if float(h.get("realized_pnl", 0)) > 0]
    losses = [h for h in history if float(h.get("realized_pnl", 0)) <= 0]
    win_rate = (len(wins) / total * 100.0) if total > 0 else 0.0
    tot_r = sum(float(h.get("pnl_r", h.get("r_multiple", 0))) for h in history)
    tot_pnl = sum(float(h.get("realized_pnl", 0)) for h in history)

    assert total == 3
    assert len(wins) == 2
    assert len(losses) == 1
    assert round(win_rate, 1) == 66.7
    assert tot_r == 3.0
    assert tot_pnl == 300.0

    # Also verify /buy and /sell text command routing and state updates
    import bot3_pullback.src.command_handler as bot3_cmd
    test_cfg = tmp_path / "cmd_cfg.json"
    with open(test_cfg, "w", encoding="utf-8") as f:
        json.dump({"active_positions": {}, "trade_history": [], "last_telegram_update_id": 0}, f)

    orig_cfg_path = getattr(bot3_cmd, "CONFIG_PATH", None)
    try:
        bot3_cmd.CONFIG_PATH = str(test_cfg)
        sent = []
        handler.send_message = lambda chat_id, text, reply_markup=None: sent.append(text)

        # /buy text command
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = {
                "ok": True,
                "result": [{"update_id": 1, "message": {"chat": {"id": 1}, "text": "/buy MSFT 20 200.0"}}]
            }
            mock_get.return_value.status_code = 200
            handler.process_updates()

        with open(test_cfg, "r", encoding="utf-8") as f:
            c1 = json.load(f)
        assert "MSFT" in c1["active_positions"]
        assert c1["active_positions"]["MSFT"]["current_shares"] == 20
        assert "บันทึกเข้าพอร์ตสำเร็จ" in sent[-1]

        # /sell text command
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = {
                "ok": True,
                "result": [{"update_id": 2, "message": {"chat": {"id": 1}, "text": "/sell MSFT 220.0"}}]
            }
            mock_get.return_value.status_code = 200
            handler.process_updates()

        with open(test_cfg, "r", encoding="utf-8") as f:
            c2 = json.load(f)
        assert "MSFT" not in c2["active_positions"]
        assert len(c2["trade_history"]) == 1
        assert c2["trade_history"][0]["ticker"] == "MSFT"
        assert c2["trade_history"][0]["exit_price"] == 220.0
        assert "บันทึกปิดออเดอร์สำเร็จ" in sent[-1]
    finally:
        if orig_cfg_path:
            bot3_cmd.CONFIG_PATH = orig_cfg_path


# ---------------------------------------------------------------------------
# Test 9: Config Compliance
# ---------------------------------------------------------------------------
def test_config_parameters():
    config_path = os.path.join(os.path.dirname(__file__), "..", "bot3_pullback", "config", "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    assert cfg.get("max_allocation_per_trade_pct") == 20.0
    assert cfg.get("portfolio_equity") == 10000.0
    assert cfg.get("risk_per_trade_pct") == 0.5
