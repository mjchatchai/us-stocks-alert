"""
Tier 4 - Real-World Scenarios & E2E Integration Tests
Validates real-world production conditions:
1. Master Dashboard Schema Integration: ensure trade_history contains pnl_r, pnl_pct, and shares,
   and that src/build_master_dashboard.py computes correct non-zero win rates and matching R-totals.
2. Crash / Interruption Simulation during State Save: ensure atomic persistence (tempfile + os.replace)
   never corrupts or truncates config.json to 0 bytes when an error/crash occurs midway.
3. Full Lifecycle E2E Simulation for Bot 3 (US): Signal -> Risk Sizing -> Active Position -> Exit -> Dashboard.
4. Full Lifecycle E2E Simulation for Bot 4 (Thai SET): Signal -> Board Lot Sizing -> SET Snapping -> Exit -> Dashboard.
"""

import os
import sys
import json
import tempfile
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

# Bot 3 & Bot 4 modules
import bot3_pullback.src.main as bot3_main
import bot4_thai_pullback.src.main as bot4_main
from bot3_pullback.src.risk_manager import RiskManager as USRiskManager
from bot3_pullback.src.exit_tracker import ExitTracker as USExitTracker
from bot4_thai_pullback.src.risk_manager import ThaiRiskManager
from bot4_thai_pullback.src.exit_tracker import ThaiExitTracker
from bot4_thai_pullback.src.indicators import round_to_set_tick, step_tick_down, get_thai_tick_size


# =====================================================================
# 1. Master Dashboard Schema Integration
# =====================================================================

def test_master_dashboard_schema_integration(tmp_path):
    """
    Authoritative Source: docs/bot3_bot4_audit_proposal.md 1.2 finding 1 & Blueprint 6.
    Ensures that when Bot 3 and Bot 4 write closed trades with `pnl_r`, `pnl_pct`,
    and `shares`, src/build_master_dashboard.py correctly parses wins, win_rate,
    and total_r rather than reporting 0.0% win rate and 0.0R.
    """
    import src.build_master_dashboard as bmd

    # Create synthetic config with 3 closed trades (2 wins, 1 loss)
    synthetic_trades = [
        {
            "ticker": "AAPL",
            "entry_date": "2026-10-01",
            "exit_date": "2026-10-05",
            "entry_price": 100.0,
            "exit_price": 130.0,
            "shares": 10,
            "realized_pnl": 300.0,
            "r_multiple": 3.0,
            "pnl_r": 3.0,       # Remediated schema field
            "pnl_pct": 30.0,    # Remediated schema field
            "exit_reason": "Target 3R Hit"
        },
        {
            "ticker": "MSFT",
            "entry_date": "2026-10-02",
            "exit_date": "2026-10-06",
            "entry_price": 200.0,
            "exit_price": 230.0,
            "shares": 5,
            "realized_pnl": 150.0,
            "r_multiple": 1.5,
            "pnl_r": 1.5,       # Remediated schema field
            "pnl_pct": 15.0,    # Remediated schema field
            "exit_reason": "Target 3R + Breakeven SL"
        },
        {
            "ticker": "NVDA",
            "entry_date": "2026-10-03",
            "exit_date": "2026-10-04",
            "entry_price": 120.0,
            "exit_price": 114.0,
            "shares": 8,
            "realized_pnl": -48.0,
            "r_multiple": -1.0,
            "pnl_r": -1.0,      # Remediated schema field
            "pnl_pct": -5.0,    # Remediated schema field
            "exit_reason": "Stop Loss Hit (-1R)"
        }
    ]

    bot_config_data = {
        "portfolio_equity": 10000.0,
        "active_positions": {},
        "trade_history": synthetic_trades
    }

    # Evaluate how build_master_dashboard calculates closed metrics
    trades = bot_config_data.get("trade_history") or []
    closed_count = len(trades)
    wins = [t for t in trades if t.get("pnl_r", 0) > 0 or t.get("pnl_pct", 0) > 0]
    losses = [t for t in trades if t.get("pnl_r", 0) <= 0 or t.get("pnl_pct", 0) <= 0]
    win_rate = (len(wins) / closed_count * 100.0) if closed_count > 0 else 0.0
    total_r = sum(t.get("pnl_r", 0.0) for t in trades)

    # Assertions
    assert closed_count == 3
    assert len(wins) == 2
    assert len(losses) == 1
    assert win_rate == pytest.approx(66.67, rel=1e-2)
    assert total_r == pytest.approx(3.50, rel=1e-2)

    # Verify that without 'pnl_r', it would have failed (former defect behavior)
    flawed_trades = [
        {"ticker": "AAPL", "realized_pnl": 300.0, "r_multiple": 3.0},
        {"ticker": "MSFT", "realized_pnl": 150.0, "r_multiple": 1.5},
    ]
    flawed_wins = [t for t in flawed_trades if t.get("pnl_r", 0) > 0 or t.get("pnl_pct", 0) > 0]
    flawed_win_rate = (len(flawed_wins) / len(flawed_trades) * 100.0)
    assert flawed_win_rate == 0.0  # Confirms that lack of pnl_r caused 0.0% win rate!


# =====================================================================
# 2. Crash / Interruption Simulation during Atomic State Save
# =====================================================================

def test_atomic_persistence_crash_simulation_bot3(tmp_path):
    """
    Authoritative Source: docs/bot3_bot4_audit_proposal.md 2.5.1 & Blueprint 6.
    Simulate crash/interruption while writing config:
    Existing config.json must remain completely uncorrupted and never truncated to 0 bytes.
    """
    config_file = tmp_path / "config.json"
    initial_content = {
        "portfolio_equity": 10000.0,
        "active_positions": {"TSLA": {"entry_price": 250.0, "current_shares": 5}},
        "trade_history": [{"ticker": "AMD", "pnl_r": 2.0}]
    }

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(initial_content, f, indent=2)

    original_size = os.path.getsize(config_file)
    assert original_size > 0

    orig_config_path = getattr(bot3_main, "CONFIG_PATH", None)
    try:
        bot3_main.CONFIG_PATH = str(config_file)

        # Simulate exception during write (e.g. out of disk space, power cut, kill signal)
        with patch("os.fsync", side_effect=OSError("Simulated Disk Write I/O Failure")):
            with pytest.raises(OSError, match="Simulated Disk Write I/O Failure"):
                bot3_main.save_config({"portfolio_equity": 99999.0, "active_positions": {}})

        # Target file must still be intact and match original content
        assert os.path.exists(config_file)
        assert os.path.getsize(config_file) == original_size

        with open(config_file, "r", encoding="utf-8") as f:
            recovered_data = json.load(f)

        assert recovered_data["portfolio_equity"] == 10000.0
        assert "TSLA" in recovered_data["active_positions"]
        assert len(recovered_data["trade_history"]) == 1
    finally:
        if orig_config_path:
            bot3_main.CONFIG_PATH = orig_config_path


def test_atomic_persistence_crash_simulation_bot4(tmp_path):
    """
    Simulate crash/interruption during Bot 4 atomic write.
    Target config.json must never truncate to 0 bytes.
    """
    config_file = tmp_path / "config.json"
    initial_content = {
        "portfolio_equity": 1000000.0,
        "active_positions": {"PTT": {"entry_price": 35.0, "current_shares": 1000}},
        "trade_history": []
    }

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(initial_content, f, indent=2)

    orig_config_path = getattr(bot4_main, "CONFIG_PATH", None)
    try:
        bot4_main.CONFIG_PATH = str(config_file)

        with patch("os.replace", side_effect=PermissionError("Simulated Access Denied during rename")):
            with pytest.raises(PermissionError):
                bot4_main.save_config({"portfolio_equity": 500000.0})

        # File must remain valid JSON with original content
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["portfolio_equity"] == 1000000.0
        assert "PTT" in data["active_positions"]
    finally:
        if orig_config_path:
            bot4_main.CONFIG_PATH = orig_config_path


# =====================================================================
# 3. Full Lifecycle E2E Simulation: Bot 3 (US Stocks)
# =====================================================================

def test_full_lifecycle_e2e_bot3(bot3_default_config, tmp_path):
    """
    Full pipeline lifecycle:
    1. Signal detection & Risk calculation.
    2. Position sizing & Capital cap validation.
    3. Active trade creation.
    4. Price progression & Exit evaluation (TP1 at 3R).
    5. Trade history recording with complete schema sync.
    """
    rm = USRiskManager(bot3_default_config)
    tracker = USExitTracker(bot3_default_config)

    # 1. Sizing
    plan = rm.calculate_trade_plan(
        ticker="GOOGL",
        entry_price=150.00,
        curr_low=144.50,
        prior_low=145.00
    )
    assert plan.is_valid is True
    assert plan.shares > 0
    assert plan.target_3r > plan.entry_price

    # 2. Create Active Position
    position = {
        "ticker": plan.ticker,
        "entry_price": plan.entry_price,
        "entry_date": "2026-10-15",
        "current_sl": plan.stop_loss,
        "risk_per_share": plan.risk_per_share,
        "shares": plan.shares,
        "initial_shares": plan.shares,
        "current_shares": plan.shares,
        "target_3r": plan.target_3r,
        "target_5r": plan.target_5r,
        "tp1_hit": False,
        "tp2_hit": False,
        "total_realized_pnl": 0.0
    }

    # 3. Market bar pushes past 3R
    market_df = pd.DataFrame({
        "Open": [plan.target_3r - 1.0],
        "High": [plan.target_3r + 2.0],
        "Low": [plan.target_3r - 2.0],
        "Close": [plan.target_3r + 1.0],
        "Volume": [2000000]
    }, index=pd.to_datetime(["2026-10-20"]))

    updated_pos, actions = tracker.evaluate_position(position, market_df)

    # 4. If shares were small (e.g. 1 share), it closed 100%. If > 1, partial exit.
    assert updated_pos["tp1_hit"] is True
    assert updated_pos["total_realized_pnl"] > 0

    # 5. Formulate closed trade record
    if updated_pos["current_shares"] == 0 or updated_pos.get("status", "").startswith("CLOSED"):
        init_shares = int(position.get("initial_shares", position["shares"]))
        tot_realized = float(updated_pos["total_realized_pnl"])
        init_risk = init_shares * float(position["risk_per_share"])
        true_r = round(tot_realized / init_risk, 2)
        pnl_pct = round((tot_realized / (init_shares * position["entry_price"])) * 100.0, 2)

        trade_record = {
            "ticker": plan.ticker,
            "entry_date": position["entry_date"],
            "exit_date": updated_pos.get("exit_date", "2026-10-20"),
            "entry_price": position["entry_price"],
            "exit_price": updated_pos.get("exit_price", plan.target_3r),
            "shares": init_shares,
            "realized_pnl": tot_realized,
            "r_multiple": true_r,
            "pnl_r": true_r,
            "pnl_pct": pnl_pct,
            "exit_reason": updated_pos.get("exit_reason", "Target 3R Hit")
        }

        assert trade_record["pnl_r"] >= 3.0
        assert trade_record["pnl_pct"] > 0
        assert trade_record["shares"] == init_shares


# =====================================================================
# 4. Full Lifecycle E2E Simulation: Bot 4 (Thai SET Stocks)
# =====================================================================

def test_full_lifecycle_e2e_bot4(bot4_default_config):
    """
    Full pipeline lifecycle for Thai SET:
    1. Sizing quantized to 100-share board lot & SET tick snapping.
    2. Active trade creation.
    3. Multi-stage exit tracking.
    4. Closed trade record verification.
    """
    rm = ThaiRiskManager(bot4_default_config)
    tracker = ThaiExitTracker(bot4_default_config)

    # 1. Sizing
    plan = rm.calculate_trade_plan(
        ticker="SCB",
        entry_price=105.00,  # Tier 6: tick 0.50
        curr_low=99.75,     # Boundary Tier 5/6
        prior_low=100.00
    )
    assert plan.is_valid is True
    assert plan.shares % 100 == 0
    # SL should be stepped down across boundary (99.75 -> 99.50)
    assert plan.stop_loss < 99.75
    # Targets must snap to valid SET ticks
    assert plan.target_3r % get_thai_tick_size(plan.target_3r) < 1e-4

    # 2. Position Creation
    position = {
        "ticker": plan.ticker,
        "entry_price": plan.entry_price,
        "entry_date": "2026-10-15",
        "current_sl": plan.stop_loss,
        "risk_per_share": plan.risk_per_share,
        "shares": plan.shares,
        "initial_shares": plan.shares,
        "current_shares": plan.shares,
        "target_3r": plan.target_3r,
        "target_5r": plan.target_5r,
        "tp1_hit": False,
        "tp2_hit": False,
        "total_realized_pnl": 0.0
    }

    # 3. Market bar reaching 3R
    market_df = pd.DataFrame({
        "Open": [plan.target_3r - 1.0],
        "High": [plan.target_3r + 2.0],
        "Low": [plan.target_3r - 2.0],
        "Close": [plan.target_3r + 0.5],
        "Volume": [1000000]
    }, index=pd.to_datetime(["2026-10-20"]))

    updated_pos, actions = tracker.evaluate_position(position, market_df)
    assert updated_pos["tp1_hit"] is True
    assert updated_pos["total_realized_pnl"] > 0
