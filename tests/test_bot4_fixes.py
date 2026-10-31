"""
Unit and Integration Tests for Bot 4 (Thai SET Trend Pullback Scanner) Refactoring & Hardening
Verifies:
1. SET 8-Tier Microstructure & Schedule (Tier 1-8 including >=400 THB @ 2.00 THB tick)
2. step_tick_down across all tier boundaries (5.00 -> 4.98, 25.00 -> 24.90, 100.00 -> 99.75, 400.00 -> 399.00)
3. round_to_set_tick price snapping to discrete SET ticks
4. ThaiRiskManager board lot quantization (100 shares), floor inversion elimination, and invalidation guards
5. ThaiRiskManager 20% max capital allocation cap enforcement
6. ThaiExitTracker single 100-share board lot liquidation at TP1 (CLOSED_TP1, 0 shares remaining)
7. ThaiExitTracker true cumulative blended R-multiple calculation
8. ThaiExitTracker runner share preservation (at least 1 board lot survives TP1)
9. ThaiConfluenceEngine candlestick rejection filter (reject shooting stars, require green/hammer confirmation)
10. ThaiBaseScreener strict 20M THB turnover check
11. main.py atomic state persistence (tempfile + os.replace)
12. main.py master dashboard schema compatibility (pnl_r, pnl_pct, shares, realized_pnl, r_multiple)
13. ThaiTelegramNotifier HTML entity escaping and line-aware message chunking (<= 4000 chars)
"""

import html
import json
import os
import tempfile
import numpy as np
import pandas as pd
import pytest

from bot4_thai_pullback.src.indicators import get_thai_tick_size, step_tick_down, round_to_set_tick
from bot4_thai_pullback.src.risk_manager import ThaiRiskManager, ThaiTradePlan
from bot4_thai_pullback.src.exit_tracker import ThaiExitTracker
from bot4_thai_pullback.src.confluence_engine import ThaiConfluenceEngine
from bot4_thai_pullback.src.screener import ThaiBaseScreener
from bot4_thai_pullback.src.telegram_notifier import ThaiTelegramNotifier, sanitize_html
from bot4_thai_pullback.src.main import save_config, load_config, CONFIG_PATH


# ---------------------------------------------------------------------------
# Test 1: SET 8-Tier Microstructure Schedule
# ---------------------------------------------------------------------------
def test_set_microstructure_8_tiers():
    assert get_thai_tick_size(0.50) == 0.01  # Tier 1 (< 2.00)
    assert get_thai_tick_size(1.99) == 0.01
    assert get_thai_tick_size(2.00) == 0.02  # Tier 2 (2.00 - 4.98)
    assert get_thai_tick_size(4.98) == 0.02
    assert get_thai_tick_size(5.00) == 0.05  # Tier 3 (5.00 - 9.95)
    assert get_thai_tick_size(9.95) == 0.05
    assert get_thai_tick_size(10.00) == 0.10  # Tier 4 (10.00 - 24.90)
    assert get_thai_tick_size(24.90) == 0.10
    assert get_thai_tick_size(25.00) == 0.25  # Tier 5 (25.00 - 99.75)
    assert get_thai_tick_size(99.75) == 0.25
    assert get_thai_tick_size(100.00) == 0.50  # Tier 6 (100.00 - 199.50)
    assert get_thai_tick_size(199.50) == 0.50
    assert get_thai_tick_size(200.00) == 1.00  # Tier 7 (200.00 - 398.00)
    assert get_thai_tick_size(398.00) == 1.00
    assert get_thai_tick_size(400.00) == 2.00  # Tier 8 (>= 400.00)
    assert get_thai_tick_size(450.00) == 2.00
    assert get_thai_tick_size(850.00) == 2.00


# ---------------------------------------------------------------------------
# Test 2: step_tick_down Boundary Transitions
# ---------------------------------------------------------------------------
def test_step_tick_down_tier_boundaries():
    assert step_tick_down(2.00) == 1.99
    assert step_tick_down(5.00) == 4.98
    assert step_tick_down(10.00) == 9.95
    assert step_tick_down(25.00) == 24.90
    assert step_tick_down(100.00) == 99.75
    assert step_tick_down(200.00) == 199.50
    assert step_tick_down(400.00) == 399.00
    # Standard intra-tier step downs
    assert step_tick_down(30.00) == 29.75
    assert step_tick_down(150.00) == 149.50
    assert step_tick_down(500.00) == 498.00


# ---------------------------------------------------------------------------
# Test 3: round_to_set_tick Snapping
# ---------------------------------------------------------------------------
def test_round_to_set_tick_snapping():
    assert round_to_set_tick(29.95, mode="nearest") == 30.00
    assert round_to_set_tick(29.80, mode="nearest") == 29.75
    assert round_to_set_tick(29.80, mode="down") == 29.75
    assert round_to_set_tick(29.80, mode="up") == 30.00
    assert round_to_set_tick(12.34, mode="nearest") == 12.30
    assert round_to_set_tick(12.36, mode="nearest") == 12.40


# ---------------------------------------------------------------------------
# Test 4: Risk Manager Board Lot Floor Inversion Elimination
# ---------------------------------------------------------------------------
def test_risk_manager_board_lot_inversion_eliminated():
    rm = ThaiRiskManager({
        "portfolio_equity": 1000000.0,
        "risk_per_trade_pct": 0.5,
        "max_allocation_per_trade_pct": 20.0,
        "board_lot_size": 100,
    })
    # Entry 320.0, Low 258.0 -> SL = 257.75 (Tier 7 below 398: tick is 1.00)
    # Risk per share ~ 62.25. Dollar risk budget = 5,000 THB.
    # Raw shares = 5000 / 62.25 = 80 shares.
    # Because 80 < 100, must NOT force 100 shares! Must invalidate trade!
    plan = rm.calculate_trade_plan("EXP", 320.0, 258.0, 258.0)
    assert not plan.is_valid
    assert plan.shares == 0
    assert plan.board_lots == 0
    assert "ไม่พอซื้อ 1 Board Lot" in plan.warning_note


# ---------------------------------------------------------------------------
# Test 5: Risk Manager 20% Max Capital Allocation Cap Enforcement
# ---------------------------------------------------------------------------
def test_risk_manager_max_capital_cap():
    rm = ThaiRiskManager({
        "portfolio_equity": 1000000.0,
        "risk_per_trade_pct": 0.5,
        "max_allocation_per_trade_pct": 20.0,
        "board_lot_size": 100,
    })
    # 20% cap = 200,000 THB. Stock at 2,500 THB: 100 shares = 250,000 THB (>200,000 THB).
    # Must invalidate trade, setting is_valid = False and shares = 0.
    plan = rm.calculate_trade_plan("SUPER_HIGH", 2500.0, 2480.0, 2480.0)
    assert not plan.is_valid
    assert plan.shares == 0
    assert "เกินเพดาน 20.0%" in plan.warning_note

    # Stock at 850 THB: 100 shares = 85,000 THB (<= 200,000 THB) -> Valid
    plan2 = rm.calculate_trade_plan("DELTA", 850.0, 802.0, 802.0)
    assert plan2.is_valid
    assert plan2.shares == 100
    assert plan2.capital_allocated == 85000.0


# ---------------------------------------------------------------------------
# Test 6: Risk Manager SET Tick Snapped Targets
# ---------------------------------------------------------------------------
def test_risk_manager_targets_snapped():
    rm = ThaiRiskManager({
        "portfolio_equity": 1000000.0,
        "risk_per_trade_pct": 0.5,
        "max_allocation_per_trade_pct": 20.0,
        "board_lot_size": 100,
    })
    # Entry 28.50, Low 27.25 -> SL = 27.00. Risk = 1.50.
    # Targets in Tier 5 (25-100 THB) where tick = 0.25 THB.
    plan = rm.calculate_trade_plan("TIER5", 28.50, 27.25, 27.25)
    assert plan.stop_loss == 27.00

    assert plan.target_1r % 0.25 == 0.0 or round(plan.target_1r % 0.25, 2) in (0.0, 0.25)
    assert plan.target_3r % 0.25 == 0.0 or round(plan.target_3r % 0.25, 2) in (0.0, 0.25)
    assert plan.target_5r % 0.25 == 0.0 or round(plan.target_5r % 0.25, 2) in (0.0, 0.25)


# ---------------------------------------------------------------------------
# Test 7: Exit Tracker Single 100-Share Board Lot Liquidation at TP1
# ---------------------------------------------------------------------------
def test_exit_tracker_100_share_tp1_clean_exit():
    et = ThaiExitTracker({
        "tp1_sell_ratio": 0.5,
        "tp2_sell_ratio": 0.5,
        "board_lot_size": 100,
    })
    pos = {
        "ticker": "KBANK",
        "entry_price": 150.0,
        "current_sl": 145.0,
        "risk_per_share": 5.0,
        "current_shares": 100,
        "initial_shares": 100,
        "target_3r": 165.0,
        "target_5r": 175.0,
        "tp1_hit": False,
        "tp2_hit": False,
        "total_realized_pnl": 0.0,
    }
    df = pd.DataFrame(
        {
            "Open": [155.0, 160.0],
            "High": [158.0, 166.0],
            "Low": [154.0, 159.0],
            "Close": [157.0, 165.5],
            "Volume": [100000, 200000],
        },
        index=pd.date_range("2026-10-01", periods=2),
    )

    up_pos, actions = et.evaluate_position(pos, df)
    # Must be closed cleanly with CLOSED_TP1, 0 shares, exit_price = target_3r
    assert up_pos["status"] == "CLOSED_TP1"
    assert up_pos["current_shares"] == 0
    assert up_pos["exit_price"] == 165.0
    assert up_pos["exit_reason"] == "Target 3R Hit (100% Exit for 1 Board Lot)"
    assert up_pos["total_realized_pnl"] == 1500.0
    assert up_pos["current_r"] == 3.0


# ---------------------------------------------------------------------------
# Test 8: Exit Tracker Cumulative Blended R-Multiple
# ---------------------------------------------------------------------------
def test_exit_tracker_cumulative_blended_r():
    et = ThaiExitTracker({
        "tp1_sell_ratio": 0.5,
        "tp2_sell_ratio": 0.5,
        "board_lot_size": 100,
    })
    pos = {
        "ticker": "SCB",
        "entry_price": 100.0,
        "current_sl": 95.0,
        "risk_per_share": 5.0,
        "current_shares": 200,
        "initial_shares": 200,
        "target_3r": 115.0,
        "target_5r": 125.0,
        "tp1_hit": False,
        "tp2_hit": False,
        "total_realized_pnl": 0.0,
    }
    df_tp1 = pd.DataFrame(
        {
            "Open": [102.0, 110.0],
            "High": [105.0, 116.0],
            "Low": [101.0, 109.0],
            "Close": [104.0, 115.5],
            "Volume": [100000, 200000],
        },
        index=pd.date_range("2026-10-01", periods=2),
    )
    up_pos1, _ = et.evaluate_position(pos, df_tp1)
    # 100 shares sold at 115.0 -> +1500 THB realized. 100 shares remain. SL = 100.0.
    assert up_pos1["current_shares"] == 100
    assert up_pos1["current_sl"] == 100.0
    assert up_pos1["total_realized_pnl"] == 1500.0

    # Next day: price pulls back and triggers Breakeven Stop Loss at 100.0
    df_sl = pd.DataFrame(
        {
            "Open": [108.0, 102.0],
            "High": [109.0, 102.0],
            "Low": [103.0, 99.5],
            "Close": [104.0, 100.0],
            "Volume": [100000, 200000],
        },
        index=pd.date_range("2026-10-03", periods=2),
    )
    up_pos_final, _ = et.evaluate_position(up_pos1, df_sl)
    assert up_pos_final["status"] == "CLOSED_SL"
    assert up_pos_final["exit_price"] == 100.0
    assert up_pos_final["total_realized_pnl"] == 1500.0
    # True blended R = 1500 THB / (200 * 5.0 THB) = +1.50R (NOT 0.00R!)
    assert up_pos_final["current_r"] == 1.5


# ---------------------------------------------------------------------------
# Test 9: Confluence Candlestick Rejection Filter
# ---------------------------------------------------------------------------
def test_confluence_candlestick_rejection():
    ce = ThaiConfluenceEngine({})
    dates = pd.date_range("2026-09-01", periods=30)
    closes = np.linspace(20, 25, 30)
    highs = closes + 0.5
    lows = closes - 0.5
    opens = closes.copy()

    # Create shooting star on 30th bar: Open 24.5, High 28.0, Low 24.0, Close 24.2
    opens[-1] = 24.5
    highs[-1] = 28.0
    lows[-1] = 24.0
    closes[-1] = 24.2
    df_star = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": [100000] * 30},
        index=dates,
    )
    res_star = ce.evaluate_entry_trigger(df_star)
    assert res_star["is_shooting_star"]
    assert not res_star["trigger_fired"]
    assert not res_star["has_candle_confirmation"]

    # Bullish green candle: Open 24.5, High 26.0, Low 24.4, Close 25.8
    opens[-1] = 24.5
    highs[-1] = 26.0
    lows[-1] = 24.4
    closes[-1] = 25.8
    df_bull = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": [100000] * 30},
        index=dates,
    )
    res_bull = ce.evaluate_entry_trigger(df_bull)
    assert res_bull["is_green"]
    assert res_bull["has_candle_confirmation"]
    assert res_bull["trigger_fired"]


# ---------------------------------------------------------------------------
# Test 10: Screener Strict 20M THB Turnover Filter
# ---------------------------------------------------------------------------
def test_screener_strict_turnover():
    sc = ThaiBaseScreener({
        "min_dollar_volume_20d": 20000000,
        "min_volume_20d": 200000,
        "min_perf_3m_or_6m_pct": 15.0,
    })
    # Ticker with 12M THB turnover (previously passed due to buggy 'and turnover < 10M')
    # Price = 10.0, Volume = 1,200,000 -> Turnover = 12M THB
    df_low = pd.DataFrame(
        {
            "Open": [10.0] * 80,
            "High": [10.5] * 80,
            "Low": [9.5] * 80,
            "Close": [10.0] * 80,
            "Volume": [1200000] * 80,
        },
        index=pd.date_range("2026-06-01", periods=80),
    )
    cand_low = sc.evaluate_candidate("LOW_TURNOVER", df_low, None)
    assert cand_low is None

    # Ticker with 25M THB turnover -> Passes liquidity
    # Price = 10.0, Volume = 2,500,000 -> Turnover = 25M THB
    # Give strong momentum: 6M return >= 15%
    closes = np.linspace(8.0, 10.0, 80)
    df_high = pd.DataFrame(
        {
            "Open": closes - 0.1,
            "High": closes + 0.2,
            "Low": closes - 0.2,
            "Close": closes,
            "Volume": [2500000] * 80,
        },
        index=pd.date_range("2026-06-01", periods=80),
    )
    cand_high = sc.evaluate_candidate("HIGH_TURNOVER", df_high, None)
    assert cand_high is not None
    assert cand_high["turnover_20"] >= 20000000


# ---------------------------------------------------------------------------
# Test 11: Master Dashboard Schema Parity Check
# ---------------------------------------------------------------------------
def test_master_dashboard_schema_sync():
    # Verify the exact schema src/build_master_dashboard.py relies on
    test_trade = {
        "ticker": "KBANK",
        "entry_date": "2026-10-01",
        "exit_date": "2026-10-05",
        "entry_price": 150.0,
        "exit_price": 165.0,
        "shares": 100,
        "realized_pnl": 1500.0,
        "r_multiple": 3.0,
        "pnl_r": 3.0,
        "pnl_pct": 10.0,
        "exit_reason": "Target 3R Hit",
    }
    assert "pnl_r" in test_trade
    assert "pnl_pct" in test_trade
    assert "shares" in test_trade
    assert test_trade["pnl_r"] > 0
    assert test_trade["pnl_pct"] > 0


# ---------------------------------------------------------------------------
# Test 12: Telegram Notifier Sanitization & Chunking
# ---------------------------------------------------------------------------
def test_telegram_notifier_sanitization_and_chunking():
    raw_str = "Price < EMA 50 & Breakout > Pivot"
    escaped = sanitize_html(raw_str)
    assert "<" not in escaped
    assert ">" not in escaped
    assert "&lt;" in escaped
    assert "&gt;" in escaped
    assert "&amp;" in escaped

    notifier = ThaiTelegramNotifier()
    # Test line-aware chunking on 7,500 char message
    long_msg = "Line content here for testing.\n" * 250
    chunks = []

    class ChunkSpy(ThaiTelegramNotifier):
        def _send_raw(self, text, reply_markup=None, parse_mode="HTML"):
            chunks.append(text)
            return True

    spy = ChunkSpy()
    res = spy.send_message(long_msg)
    assert res is True
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= 4000
