"""
Tier 2 - Boundary & Corner Cases Tests
Validates precision edge conditions:
1. Boundary tick step-downs: 2.00 -> 1.99, 5.00 -> 4.98, 10.00 -> 9.95, 25.00 -> 24.90, 100.00 -> 99.75, 200.00 -> 199.50, 400.00 -> 399.00 THB.
2. Sub-board-lot rejection: when affordable shares < 100 (Bot 4) or < 1 (Bot 3), ensure is_valid == False and shares == 0.
3. Capital cap breach rejection: when entry price exceeds 20% cap, ensure is_valid == False and shares == 0.
4. Single-share (Bot 3) and 100-share (Bot 4) liquidation at TP1 (3R): position marked CLOSED_TP1, exit price recorded, current_shares == 0.
"""

import pytest
import pandas as pd
import numpy as np

# Bot 4 modules
from bot4_thai_pullback.src.indicators import step_tick_down, round_to_set_tick, get_thai_tick_size
from bot4_thai_pullback.src.risk_manager import ThaiRiskManager
from bot4_thai_pullback.src.exit_tracker import ThaiExitTracker

# Bot 3 modules
from bot3_pullback.src.risk_manager import RiskManager as USRiskManager
from bot3_pullback.src.exit_tracker import ExitTracker as USExitTracker


# =====================================================================
# 1. Boundary Tick Step-Downs
# =====================================================================

def test_boundary_tick_step_downs_across_all_tiers():
    """
    Authoritative Source: SET Microstructure Rules & Audit Proposal 2.2.4.
    Stepping down 1 tick at exact tier boundaries must transition into the
    lower tier using the lower tier's tick size.
    Key Boundary Cases:
      - 2.00  -> 1.99   (Tier 2 -> Tier 1: tick 0.01)
      - 5.00  -> 4.98   (Tier 3 -> Tier 2: tick 0.02)
      - 10.00 -> 9.95   (Tier 4 -> Tier 3: tick 0.05)
      - 25.00 -> 24.90  (Tier 5 -> Tier 4: tick 0.10, NOT 24.75!)
      - 100.00 -> 99.75 (Tier 6 -> Tier 5: tick 0.25)
      - 200.00 -> 199.50(Tier 7 -> Tier 6: tick 0.50)
      - 400.00 -> 399.00(Tier 8 -> Tier 7: tick 1.00, NOT 398.00!)
    """
    boundary_cases = [
        (2.00, 1.99),
        (5.00, 4.98),
        (10.00, 9.95),
        (25.00, 24.90),
        (100.00, 99.75),
        (200.00, 199.50),
        (400.00, 399.00),
    ]

    for input_price, expected_step_down in boundary_cases:
        actual = step_tick_down(input_price)
        assert actual == pytest.approx(expected_step_down, rel=1e-5), (
            f"Failed boundary step-down for {input_price}: expected {expected_step_down}, got {actual}"
        )


def test_round_to_set_tick_modes():
    """
    Verifies round_to_set_tick snapping logic (nearest, down, up).
    """
    # Price 24.93 in Tier 4 (tick 0.10)
    assert round_to_set_tick(24.93, mode="nearest") == 24.90
    assert round_to_set_tick(24.93, mode="down") == 24.90
    assert round_to_set_tick(24.93, mode="up") == 25.00

    # Price 100.20 in Tier 6 (tick 0.50)
    assert round_to_set_tick(100.20, mode="nearest") == 100.00
    assert round_to_set_tick(100.20, mode="up") == 100.50
    assert round_to_set_tick(100.20, mode="down") == 100.00

    # Tier 8 price 401.50 (tick 2.00)
    assert round_to_set_tick(401.50, mode="nearest") == 402.00
    assert round_to_set_tick(401.50, mode="down") == 400.00
    assert round_to_set_tick(401.50, mode="up") == 402.00


# =====================================================================
# 2. Sub-Board-Lot Rejection
# =====================================================================

def test_sub_board_lot_rejection_bot4(bot4_default_config):
    """
    Bot 4 Corner Case:
    When 0.5% risk budget (5,000 THB) cannot afford a single 100-share board lot:
    Must return is_valid == False and shares == 0.
    Example: Entry 320.00, Stop Loss 258.00 (Risk per share = 62.00 THB).
    Budget / 62 = 80 shares < 100.
    """
    rm = ThaiRiskManager(bot4_default_config)
    plan = rm.calculate_trade_plan(
        ticker="DELTA",
        entry_price=320.00,
        curr_low=259.00,
        prior_low=260.00
    )
    assert plan.is_valid is False
    assert plan.shares == 0
    assert plan.board_lots == 0
    assert plan.capital_allocated == 0.0
    assert "ไม่พอซื้อ 1 Board Lot" in plan.warning_note


def test_sub_board_lot_rejection_bot3(bot3_default_config):
    """
    Bot 3 Corner Case:
    When 0.5% risk budget ($50.00) cannot afford even 1 whole share:
    Must return is_valid == False and shares == 0.
    Example: Entry $800.00, Stop Loss $720.00 (Risk per share = $80.00).
    Budget / $80 = 0.625 shares -> raw_shares = 0.
    """
    rm = USRiskManager(bot3_default_config)
    plan = rm.calculate_trade_plan(
        ticker="BKNG",
        entry_price=800.00,
        curr_low=720.50,
        prior_low=721.00
    )
    assert plan.is_valid is False
    assert plan.shares == 0
    assert plan.capital_allocated == 0.0


# =====================================================================
# 3. Capital Cap Breach Rejection
# =====================================================================

def test_capital_cap_breach_rejection_bot4(bot4_default_config):
    """
    Bot 4 Corner Case:
    When stock price is so high that purchasing just 1 Board Lot (100 shares)
    breaches the 20% max portfolio allocation cap (200,000 THB):
    Must invalidate the setup (is_valid == False, shares == 0).
    Example: Entry 2,500.00 THB -> 1 Board Lot requires 250,000 THB > 200,000 THB.
    """
    rm = ThaiRiskManager(bot4_default_config)
    # Entry 2,500 THB, tiny risk to keep risk budget satisfied
    plan = rm.calculate_trade_plan(
        ticker="ULTRA_HIGH",
        entry_price=2500.00,
        curr_low=2490.00,
        prior_low=2490.00
    )
    assert plan.is_valid is False
    assert plan.shares == 0
    assert plan.board_lots == 0
    assert plan.capital_allocated == 0.0


def test_capital_cap_breach_rejection_bot3(bot3_default_config):
    """
    Bot 3 Corner Case:
    When stock price exceeds the 20% max allocation cap ($2,000) for a single share:
    Must invalidate the setup (is_valid == False, shares == 0).
    Example: Entry $2,500.00 > $2,000.00 cap.
    """
    rm = USRiskManager(bot3_default_config)
    plan = rm.calculate_trade_plan(
        ticker="EXPENSIVE",
        entry_price=2500.00,
        curr_low=2480.00,
        prior_low=2480.00
    )
    assert plan.is_valid is False
    assert plan.shares == 0
    assert plan.capital_allocated == 0.0


# =====================================================================
# 4. Single-Share / Single Board Lot Liquidation at TP1 (3R)
# =====================================================================

def test_single_share_liquidation_at_tp1_bot3(bot3_default_config):
    """
    Authoritative Source: Blueprint 4 & docs/bot3_bot4_audit_proposal.md 2.3.2.
    Zombie 0-Share Bug Remediation:
    When holding curr_shares == 1 and price hits Target 3R:
    Position must be 100% liquidated, status marked 'CLOSED_TP1',
    exit_price recorded, and current_shares set to 0.
    """
    tracker = USExitTracker(bot3_default_config)
    position = {
        "ticker": "TSLA",
        "entry_price": 200.00,
        "entry_date": "2026-10-01",
        "current_sl": 190.00,
        "risk_per_share": 10.00,
        "shares": 1,
        "initial_shares": 1,
        "current_shares": 1,
        "target_3r": 230.00,
        "target_5r": 250.00,
        "tp1_hit": False,
        "tp2_hit": False,
        "total_realized_pnl": 0.0
    }

    # Market bar hitting 3R
    df = pd.DataFrame({
        "Open": [220.00],
        "High": [232.00],  # Above 230.00 (3R)
        "Low": [219.00],
        "Close": [231.00],
        "Volume": [1000000]
    }, index=pd.to_datetime(["2026-10-05"]))

    updated_pos, actions = tracker.evaluate_position(position, df)

    assert updated_pos["status"] == "CLOSED_TP1"
    assert updated_pos["current_shares"] == 0
    assert updated_pos["exit_price"] == 230.00
    assert updated_pos["total_realized_pnl"] == pytest.approx(30.00, rel=1e-4)
    assert any(a["type"] == "TP1_3R_FULL" for a in actions)


def test_single_board_lot_liquidation_at_tp1_bot4(bot4_default_config):
    """
    Authoritative Source: Blueprint 4 & docs/bot3_bot4_audit_proposal.md 2.3.2.
    When holding curr_shares == 100 (1 Board Lot) and price hits Target 3R:
    Position must be 100% liquidated as CLOSED_TP1.
    """
    tracker = ThaiExitTracker(bot4_default_config)
    position = {
        "ticker": "KBANK",
        "entry_price": 150.00,
        "entry_date": "2026-10-01",
        "current_sl": 145.00,
        "risk_per_share": 5.00,
        "shares": 100,
        "initial_shares": 100,
        "current_shares": 100,
        "target_3r": 165.00,
        "target_5r": 175.00,
        "tp1_hit": False,
        "tp2_hit": False,
        "total_realized_pnl": 0.0
    }

    df = pd.DataFrame({
        "Open": [160.00],
        "High": [166.00],  # Above 165.00 (3R)
        "Low": [159.00],
        "Close": [165.50],
        "Volume": [2000000]
    }, index=pd.to_datetime(["2026-10-05"]))

    updated_pos, actions = tracker.evaluate_position(position, df)

    assert updated_pos["status"] == "CLOSED_TP1"
    assert updated_pos["current_shares"] == 0
    assert updated_pos["exit_price"] == 165.00
    assert updated_pos["total_realized_pnl"] == pytest.approx(1500.00, rel=1e-4)
    assert any(a["type"] == "TP1_3R_FULL" for a in actions)
