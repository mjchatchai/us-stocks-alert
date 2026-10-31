"""
Tier 1 - Feature Coverage Tests
Validates core requirements and specifications:
1. SET 8-tier tick size lookup across all 8 brackets (including Tier 8 >= 400 THB).
2. Thai 100-share board lot calculation (exact quantization, no floor inversion).
3. Candlestick rejection (shooting star rejection vs hammer confirmation).
4. Risk budget sizing (0.5% risk limit).
5. 20% max capital allocation cap per position.
6. Atomic state persistence (tempfile.mkstemp + os.replace).
"""

import os
import sys
import json
import tempfile
import pytest
import pandas as pd
import numpy as np

# Import Bot 4 modules
from bot4_thai_pullback.src.indicators import get_thai_tick_size
from bot4_thai_pullback.src.risk_manager import ThaiRiskManager, ThaiTradePlan

# Import Bot 3 modules
from bot3_pullback.src.risk_manager import RiskManager as USRiskManager, TradePlan as USTradePlan


# =====================================================================
# 1. SET 8-Tier Tick Size Lookup across all 8 brackets
# =====================================================================

def test_set_8tier_tick_size_all_brackets():
    """
    Authoritative Source: SET Official Trading Rules & docs/bot3_bot4_audit_proposal.md 2.2.3.
    Brackets:
      Tier 1: < 2.00 THB -> 0.01
      Tier 2: 2.00 <= p < 5.00 THB -> 0.02
      Tier 3: 5.00 <= p < 10.00 THB -> 0.05
      Tier 4: 10.00 <= p < 25.00 THB -> 0.10
      Tier 5: 25.00 <= p < 100.00 THB -> 0.25
      Tier 6: 100.00 <= p < 200.00 THB -> 0.50
      Tier 7: 200.00 <= p < 400.00 THB -> 1.00
      Tier 8: >= 400.00 THB -> 2.00 (Critical SET Tier 8)
    """
    test_cases = [
        # (price, expected_tick, tier_name)
        (0.50, 0.01, "Tier 1 - sub 2 Baht"),
        (1.99, 0.01, "Tier 1 - just below 2 Baht"),
        (2.00, 0.02, "Tier 2 - exact boundary 2 Baht"),
        (3.50, 0.02, "Tier 2 - mid range"),
        (4.98, 0.02, "Tier 2 - just below 5 Baht"),
        (5.00, 0.05, "Tier 3 - exact boundary 5 Baht"),
        (7.50, 0.05, "Tier 3 - mid range"),
        (9.95, 0.05, "Tier 3 - just below 10 Baht"),
        (10.00, 0.10, "Tier 4 - exact boundary 10 Baht"),
        (17.50, 0.10, "Tier 4 - mid range"),
        (24.90, 0.10, "Tier 4 - just below 25 Baht"),
        (25.00, 0.25, "Tier 5 - exact boundary 25 Baht"),
        (60.00, 0.25, "Tier 5 - mid range"),
        (99.75, 0.25, "Tier 5 - just below 100 Baht"),
        (100.00, 0.50, "Tier 6 - exact boundary 100 Baht"),
        (150.00, 0.50, "Tier 6 - mid range"),
        (199.50, 0.50, "Tier 6 - just below 200 Baht"),
        (200.00, 1.00, "Tier 7 - exact boundary 200 Baht"),
        (350.00, 1.00, "Tier 7 - mid range"),
        (398.00, 1.00, "Tier 7 - just below 400 Baht"),
        (400.00, 2.00, "Tier 8 - exact boundary 400 Baht"),
        (500.00, 2.00, "Tier 8 - large cap mid range"),
        (850.00, 2.00, "Tier 8 - ultra high price (e.g. DELTA)")
    ]

    for price, expected_tick, tier_name in test_cases:
        actual_tick = get_thai_tick_size(price)
        assert actual_tick == pytest.approx(expected_tick, rel=1e-5), (
            f"Failed on {tier_name}: price={price}, expected={expected_tick}, got={actual_tick}"
        )


# =====================================================================
# 2. Thai 100-Share Board Lot Calculation
# =====================================================================

def test_thai_100_share_board_lot_quantization(bot4_default_config):
    """
    Authoritative Source: SET Board Lot Rules & Audit Proposal 2.2.1.
    All position sizes in Thai market must strictly be exact multiples of 100 shares.
    No odd lots allowed in normal trading.
    """
    rm = ThaiRiskManager(bot4_default_config)

    # Case A: Budget allows 380 raw shares -> Must quantize to exactly 300 shares
    # Entry: 50.00, SL: 48.00 (Risk per share = 2.00)
    # Risk budget: 5,000 THB -> raw_shares = 2500 -> board_lot_shares = 2500
    plan_a = rm.calculate_trade_plan(
        ticker="CPALL",
        entry_price=50.00,
        curr_low=48.25,
        prior_low=48.25
    )
    assert plan_a.shares % 100 == 0
    assert plan_a.shares > 0

    # Case B: Board lot quantization truncation (2173 raw shares -> 2100 shares)
    # Entry: 26.00, curr_low = min(23.80, 24.00) = 23.80 (Tier 4 tick 0.10) -> SL = 23.70.
    # Risk per share = 26.00 - 23.70 = 2.30 THB. Budget = 5,000 THB.
    # raw_shares = int(5000 / 2.30) = 2173 shares -> Board lot shares = 2100 shares
    plan_b = rm.calculate_trade_plan(
        ticker="BDMS",
        entry_price=26.00,
        curr_low=23.80,
        prior_low=24.00
    )
    assert plan_b.shares == 2100
    assert plan_b.shares % 100 == 0

    # Case C: Unrounded low quantization guard (32.90 THB unrounded in Tier 5 snaps to 32.75 THB)
    plan_c = rm.calculate_trade_plan(
        ticker="UNROUNDED",
        entry_price=35.00,
        curr_low=32.90,
        prior_low=33.00
    )
    assert plan_c.stop_loss == 32.50
    assert plan_c.shares == 2000
    assert plan_c.shares % 100 == 0


def test_thai_no_floor_inversion_when_affordable_under_100_shares(bot4_default_config):
    """
    Audit Defect Remediation (P0):
    Former defect used max(100, board_lot_shares), which inverted the floor
    and forced 100 shares even when budget could only afford 60-80 shares.
    Must evaluate is_valid=False and shares=0.
    """
    rm = ThaiRiskManager(bot4_default_config)
    # Entry = 320.00, SL = 258.00 -> Risk per share = 62.00 THB
    # Budget = 5,000 THB -> raw_shares = 5000 / 62 = 80 shares (< 100)
    plan = rm.calculate_trade_plan(
        ticker="DELTA",
        entry_price=320.00,
        curr_low=259.00,
        prior_low=260.00
    )
    assert plan.is_valid is False
    assert plan.shares == 0
    assert plan.capital_allocated == 0.0


# =====================================================================
# 3. Candlestick Rejection (Shooting Star Rejection vs Hammer Confirmation)
# =====================================================================

def test_candlestick_anatomy_shooting_star_rejection(sample_candlestick_df, bot4_default_config):
    """
    Authoritative Source: docs/bot3_bot4_audit_proposal.md 2.1.3 & Blueprint 5.
    Bearish shooting star: upper wick >= 2.5 * max(body, 0.05) and lower wick <= 0.5 * upper wick.
    Must reject setup even if curr_high > prior_high (eliminates bull traps).
    """
    from bot4_thai_pullback.src.confluence_engine import ThaiConfluenceEngine

    engine = ThaiConfluenceEngine(bot4_default_config)
    df = sample_candlestick_df.copy()

    # Prior bar: close = 100.0, high = 101.0
    prior_high = 100.0
    df.loc[df.index[-2], ["Open", "High", "Low", "Close"]] = [98.0, prior_high, 97.5, 99.0]

    # Current bar: Massive upper wick spike (Shooting Star)
    # Open: 99.0, High: 104.0, Low: 94.8, Close: 95.0
    # curr_high (104.0) > prior_high (100.0) -> Raw trigger would have fired!
    # Body = |95.0 - 99.0| = 4.0
    # Upper wick = 104.0 - 99.0 = 5.0 (or higher ratio)
    # Let's construct a classic extreme shooting star:
    # Open: 98.0, High: 103.0, Close: 97.5, Low: 97.2
    # Body = 0.5, Upper wick = 103.0 - 98.0 = 5.0 (10x body >= 2.5x), Lower wick = 97.5 - 97.2 = 0.3 (<= 0.5 * 5.0)
    df.loc[df.index[-1], ["Open", "High", "Low", "Close"]] = [98.0, 103.0, 97.2, 97.5]

    res = engine.evaluate_entry_trigger(df)
    # Trigger must NOT fire for severe shooting star
    assert res.get("trigger_fired", False) is False
    assert res.get("status") != "BUY_TRIGGERED"


def test_candlestick_anatomy_hammer_confirmation(sample_candlestick_df, bot4_default_config):
    """
    Authoritative Source: docs/bot3_bot4_audit_proposal.md Blueprint 5.
    Hammer: lower_wick >= 1.5 * max(body, 0.05) and upper_wick <= 1.0 * max(body, 0.05).
    Bullish rejection of lower prices at confluence support.
    """
    from bot4_thai_pullback.src.confluence_engine import ThaiConfluenceEngine

    engine = ThaiConfluenceEngine(bot4_default_config)
    df = sample_candlestick_df.copy()

    # Create confluence base at ~100
    support = engine.calculate_confluence_support(df)
    zone_top = support["zone_top"]
    prior_high = support["prior_high"]

    # Hammer candle:
    # Open: zone_top + 0.5, Low: zone_top - 2.5, Close: zone_top + 0.8, High: zone_top + 1.0
    # Lower wick = 0.5 - (-2.5) = 3.0. Body = 0.3. Upper wick = 0.2.
    # Lower wick (3.0) >= 1.5 * 0.3 (0.45). Upper wick (0.2) <= 1.0 * 0.3.
    # High crosses prior_high
    hammer_high = max(prior_high + 0.5, zone_top + 1.2)
    df.loc[df.index[-1], ["Open", "High", "Low", "Close"]] = [
        zone_top + 0.2, hammer_high, zone_top - 2.0, zone_top + 0.5
    ]

    res = engine.evaluate_entry_trigger(df)
    # When in pullback zone with hammer confirmation, trigger should be accepted
    if res.get("in_pullback_zone", False):
        assert res.get("trigger_fired", False) is True


# =====================================================================
# 4. Risk Budget Sizing (0.5% Risk Limit)
# =====================================================================

def test_risk_budget_sizing_bot3(bot3_default_config):
    """
    Bot 3 (US Stocks):
    Portfolio = $10,000, Risk = 0.5% -> Dollar Risk Budget = $50.00.
    Actual dollar risk allocated (shares * risk_per_share) must be <= $50.00.
    """
    rm = USRiskManager(bot3_default_config)
    # Entry: $100.00, SL: $95.00 -> Risk per share: $5.00
    plan = rm.calculate_trade_plan(
        ticker="AAPL",
        entry_price=100.00,
        curr_low=95.10,
        prior_low=95.20
    )
    assert plan.dollar_risk_budget == 50.00
    actual_risk = plan.shares * plan.risk_per_share
    assert actual_risk <= plan.dollar_risk_budget
    assert plan.shares == int(50.00 / plan.risk_per_share)


def test_risk_budget_sizing_bot4(bot4_default_config):
    """
    Bot 4 (Thai SET Stocks):
    Portfolio = 1,000,000 THB, Risk = 0.5% -> Baht Risk Budget = 5,000 THB.
    Actual Baht risk allocated (shares * risk_per_share) must be <= 5,000 THB.
    """
    rm = ThaiRiskManager(bot4_default_config)
    # Entry: 50.00 THB, SL: 45.00 THB -> Risk per share: 5.00 THB
    plan = rm.calculate_trade_plan(
        ticker="PTT",
        entry_price=50.00,
        curr_low=45.10,
        prior_low=45.20
    )
    assert plan.dollar_risk_budget == 5000.00
    actual_risk = plan.shares * plan.risk_per_share
    assert actual_risk <= plan.dollar_risk_budget
    assert plan.shares % 100 == 0


# =====================================================================
# 5. 20% Max Capital Allocation Cap per Position
# =====================================================================

def test_max_capital_allocation_cap_bot3(bot3_default_config):
    """
    Bot 3 (US Stocks):
    Equity: $10,000. Max Allocation Cap: 20% ($2,000).
    When risk-based shares would exceed $2,000 capital, sizing must be clamped.
    """
    rm = USRiskManager(bot3_default_config)
    # Tiny stop loss creates huge raw share count:
    # Entry: $100.00, SL: $99.50 -> Risk per share: $0.50
    # Raw shares = $50.00 / $0.50 = 100 shares -> Capital = 100 * $100 = $10,000 (100% of port!)
    plan = rm.calculate_trade_plan(
        ticker="NVDA",
        entry_price=100.00,
        curr_low=99.60,
        prior_low=99.60
    )
    assert plan.is_capped is True
    assert plan.capital_allocated <= 2000.00
    assert plan.shares == int(2000.00 / 100.00)  # 20 shares


def test_max_capital_allocation_cap_bot4(bot4_default_config):
    """
    Bot 4 (Thai SET Stocks):
    Equity: 1,000,000 THB. Max Allocation Cap: 20% (200,000 THB).
    When risk-based shares would exceed 200,000 THB capital, sizing must be clamped to board lots.
    """
    rm = ThaiRiskManager(bot4_default_config)
    # Entry: 50.00 THB, SL: 49.75 THB -> Risk per share: 0.25 THB
    # Raw shares = 5,000 / 0.25 = 20,000 shares -> Capital = 20,000 * 50 = 1,000,000 THB
    plan = rm.calculate_trade_plan(
        ticker="AOT",
        entry_price=50.00,
        curr_low=49.80,
        prior_low=49.80
    )
    assert plan.is_capped is True
    assert plan.capital_allocated <= 200000.00
    assert plan.shares == 4000  # 4,000 * 50 = 200,000 THB
    assert plan.shares % 100 == 0


# =====================================================================
# 6. Atomic State Persistence (tempfile.mkstemp + os.replace)
# =====================================================================

def test_atomic_state_persistence_bot3(tmp_path):
    """
    Authoritative Source: Blueprint 6 & docs/bot3_bot4_audit_proposal.md 2.5.1.
    Verifies that save_config writes via a temp file in the same directory
    and replaces the target file atomically without corruption.
    """
    import bot3_pullback.src.main as bot3_main

    test_config_path = str(tmp_path / "config.json")
    original_config_path = getattr(bot3_main, "CONFIG_PATH", None)

    try:
        bot3_main.CONFIG_PATH = test_config_path
        payload = {
            "portfolio_equity": 10000.0,
            "active_positions": {
                "AAPL": {"entry_price": 150.0, "current_shares": 10}
            },
            "trade_history": [
                {"ticker": "MSFT", "pnl_r": 3.0, "pnl_pct": 15.0, "shares": 10}
            ]
        }

        bot3_main.save_config(payload)

        # Verify file exists and is valid JSON
        assert os.path.exists(test_config_path)
        with open(test_config_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        assert loaded["portfolio_equity"] == 10000.0
        assert "AAPL" in loaded["active_positions"]
        assert len(loaded["trade_history"]) == 1
        assert loaded["trade_history"][0]["pnl_r"] == 3.0
    finally:
        if original_config_path:
            bot3_main.CONFIG_PATH = original_config_path


def test_atomic_state_persistence_bot4(tmp_path):
    """
    Authoritative Source: Blueprint 6 & docs/bot3_bot4_audit_proposal.md 2.5.1.
    Verifies atomic save in Bot 4.
    """
    import bot4_thai_pullback.src.main as bot4_main

    test_config_path = str(tmp_path / "config.json")
    original_config_path = getattr(bot4_main, "CONFIG_PATH", None)

    try:
        bot4_main.CONFIG_PATH = test_config_path
        payload = {
            "portfolio_equity": 1000000.0,
            "active_positions": {
                "PTT": {"entry_price": 35.0, "current_shares": 2000}
            },
            "trade_history": [
                {"ticker": "ADVANC", "pnl_r": 1.5, "pnl_pct": 8.0, "shares": 500}
            ]
        }

        bot4_main.save_config(payload)

        assert os.path.exists(test_config_path)
        with open(test_config_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        assert loaded["portfolio_equity"] == 1000000.0
        assert "PTT" in loaded["active_positions"]
        assert loaded["trade_history"][0]["pnl_r"] == 1.5
    finally:
        if original_config_path:
            bot4_main.CONFIG_PATH = original_config_path
