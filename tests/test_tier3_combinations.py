"""
Tier 3 - Cross-Feature Combinations Tests
Validates interaction across multiple subsystems:
1. Blended R-Multiple: 50% sold at TP1 (3R) and runner stopped out at breakeven SL -> true cumulative blended R must equal +1.50R (not 0.0R!).
2. Multi-stage scaling exits (TP1 3R + TP2 5R + Trailing EMA exit) with exact blended R verification.
3. False breakout wick rejection combined with volume/turnover filters.
"""

import pytest
import pandas as pd
import numpy as np

# Bot 3 modules
from bot3_pullback.src.exit_tracker import ExitTracker as USExitTracker
try:
    from bot3_pullback.src.screener import USStockScreener
except ImportError:
    from bot3_pullback.src.screener import BaseScreener as USStockScreener
from bot3_pullback.src.confluence_engine import ConfluenceEngine as USConfluenceEngine

# Bot 4 modules
from bot4_thai_pullback.src.exit_tracker import ThaiExitTracker
try:
    from bot4_thai_pullback.src.screener import ThaiStockScreener
except ImportError:
    from bot4_thai_pullback.src.screener import ThaiBaseScreener as ThaiStockScreener
from bot4_thai_pullback.src.confluence_engine import ThaiConfluenceEngine


# =====================================================================
# 1. True Blended R-Multiple: TP1 (3R) + Breakeven SL
# =====================================================================

def test_blended_r_multiple_tp1_then_breakeven_sl_bot3(bot3_default_config):
    """
    Mathematical Proof:
    Initial Position: 200 shares @ $100.00, SL @ $90.00 (Risk per share = $10.00).
    Initial Risk Dollar = 200 * $10.00 = $2,000.00.
    Target 3R = $130.00.

    Step 1: Price touches $130.00.
      - Sell 50% = 100 shares @ $130.00.
      - Realized PnL 1 = 100 * ($130.00 - $100.00) = +$3,000.00.
      - SL moved to Breakeven ($100.00).
      - Remaining: 100 shares.

    Step 2: Price falls back to $100.00 and stops out at Breakeven.
      - Sell 100 shares @ $100.00.
      - Realized PnL 2 = 100 * ($100.00 - $100.00) = $0.00.
      - Total Realized PnL = $3,000.00 + $0.00 = $3,000.00.
      - True Blended R = $3,000.00 / $2,000.00 = +1.50R.

    Former Defect:
      - Evaluated final exit using current shares ($0 / $1,000 = 0.00R)
      - Master dashboard reported 0.00R and counted as loss or break-even!
    """
    tracker = USExitTracker(bot3_default_config)
    position = {
        "ticker": "AAPL",
        "entry_price": 100.00,
        "entry_date": "2026-10-01",
        "current_sl": 90.00,
        "risk_per_share": 10.00,
        "shares": 200,
        "initial_shares": 200,
        "current_shares": 200,
        "target_3r": 130.00,
        "target_5r": 150.00,
        "tp1_hit": False,
        "tp2_hit": False,
        "total_realized_pnl": 0.0
    }

    # Step 1: Market bar reaches TP1 (3R)
    df_step1 = pd.DataFrame({
        "Open": [125.00],
        "High": [132.00],
        "Low": [124.00],
        "Close": [131.00],
        "Volume": [1000000]
    }, index=pd.to_datetime(["2026-10-05"]))

    pos_after_step1, actions1 = tracker.evaluate_position(position, df_step1)
    assert pos_after_step1["tp1_hit"] is True
    assert pos_after_step1["current_shares"] == 100
    assert pos_after_step1["current_sl"] == 100.00  # Breakeven
    assert pos_after_step1["total_realized_pnl"] == pytest.approx(3000.00, rel=1e-4)

    # Step 2: Next bar drops to Breakeven SL
    df_step2 = pd.DataFrame({
        "Open": [105.00],
        "High": [106.00],
        "Low": [99.50],
        "Close": [100.00],
        "Volume": [1500000]
    }, index=pd.to_datetime(["2026-10-06"]))

    pos_after_step2, actions2 = tracker.evaluate_position(pos_after_step1, df_step2)
    assert pos_after_step2["status"] == "CLOSED_SL"
    assert pos_after_step2["current_shares"] == 0
    assert pos_after_step2["total_realized_pnl"] == pytest.approx(3000.00, rel=1e-4)

    # Critical Assertion: True Cumulative Blended R must equal +1.50R
    assert pos_after_step2["current_r"] == pytest.approx(1.50, rel=1e-2)


def test_blended_r_multiple_tp1_then_breakeven_sl_bot4(bot4_default_config):
    """
    Thai SET Parity:
    Initial Position: 400 shares @ 50.00 THB, SL @ 45.00 THB (Risk/sh = 5.00 THB).
    Initial Risk Dollar = 400 * 5.00 = 2,000.00 THB.
    Target 3R = 65.00 THB.

    Step 1: Hit 3R -> Sells 200 shares (50%) @ 65.00 -> PnL = 200 * 15.00 = +3,000.00 THB.
            SL moved to Breakeven (50.00 THB).
    Step 2: Drop to Breakeven SL -> Sells remaining 200 shares @ 50.00 -> PnL = 0.
            Total Realized = +3,000.00 THB.
            Blended R = 3000.00 / 2000.00 = +1.50R!
    """
    tracker = ThaiExitTracker(bot4_default_config)
    position = {
        "ticker": "CPALL",
        "entry_price": 50.00,
        "entry_date": "2026-10-01",
        "current_sl": 45.00,
        "risk_per_share": 5.00,
        "shares": 400,
        "initial_shares": 400,
        "current_shares": 400,
        "target_3r": 65.00,
        "target_5r": 75.00,
        "tp1_hit": False,
        "tp2_hit": False,
        "total_realized_pnl": 0.0
    }

    # Step 1: Reach 3R
    df1 = pd.DataFrame({
        "Open": [62.00],
        "High": [66.00],
        "Low": [61.00],
        "Close": [65.00],
        "Volume": [2000000]
    }, index=pd.to_datetime(["2026-10-05"]))

    p1, act1 = tracker.evaluate_position(position, df1)
    assert p1["tp1_hit"] is True
    assert p1["current_shares"] == 200
    assert p1["current_sl"] == 50.00
    assert p1["total_realized_pnl"] == pytest.approx(3000.00, rel=1e-4)

    # Step 2: Stop out at breakeven
    df2 = pd.DataFrame({
        "Open": [52.00],
        "High": [53.00],
        "Low": [49.50],
        "Close": [50.00],
        "Volume": [3000000]
    }, index=pd.to_datetime(["2026-10-06"]))

    p2, act2 = tracker.evaluate_position(p1, df2)
    assert p2["status"] == "CLOSED_SL"
    assert p2["current_shares"] == 0
    assert p2["total_realized_pnl"] == pytest.approx(3000.00, rel=1e-4)
    assert p2["current_r"] == pytest.approx(1.50, rel=1e-2)


# =====================================================================
# 2. Multi-Stage Scale-Out (TP1 3R + TP2 5R + Trailing Exit)
# =====================================================================

def test_multistage_scaleout_full_lifecycle(bot4_default_config):
    """
    Validates 3-stage partial take profit:
      Initial: 400 shares @ 100.00 THB, SL @ 90.00 THB (Risk/sh = 10.00 THB).
      Initial Risk = 4,000.00 THB.
      Target 3R = 130.00 THB.
      Target 5R = 150.00 THB.

      Stage 1: 3R hit -> Sell 200 shares @ 130.00 (+6,000 THB). Remaining: 200 shares.
      Stage 2: 5R hit -> Sell 100 shares @ 150.00 (+5,000 THB). Remaining: 100 shares.
      Stage 3: Trailing EMA exit @ 140.00 -> Sell 100 shares @ 140.00 (+4,000 THB).
      Total Realized = 6000 + 5000 + 4000 = +15,000 THB.
      True Blended R = 15,000 / 4,000 = +3.75R!
    """
    tracker = ThaiExitTracker(bot4_default_config)
    position = {
        "ticker": "ADVANC",
        "entry_price": 100.00,
        "entry_date": "2026-10-01",
        "current_sl": 90.00,
        "risk_per_share": 10.00,
        "shares": 400,
        "initial_shares": 400,
        "current_shares": 400,
        "target_3r": 130.00,
        "target_5r": 150.00,
        "tp1_hit": False,
        "tp2_hit": False,
        "total_realized_pnl": 0.0
    }

    # Stage 1: Hit 3R
    df1 = pd.DataFrame({
        "Open": [128.00], "High": [132.00], "Low": [127.00], "Close": [131.00], "Volume": [1000000]
    }, index=pd.to_datetime(["2026-10-05"]))
    pos, _ = tracker.evaluate_position(position, df1)
    assert pos["current_shares"] == 200
    assert pos["total_realized_pnl"] == 6000.00

    # Stage 2: Hit 5R
    df2 = pd.DataFrame({
        "Open": [148.00], "High": [152.00], "Low": [147.00], "Close": [151.00], "Volume": [1000000]
    }, index=pd.to_datetime(["2026-10-10"]))
    pos, _ = tracker.evaluate_position(pos, df2)
    assert pos["current_shares"] == 100
    assert pos["total_realized_pnl"] == 11000.00

    # Stage 3: Trailing exit below EMA
    # Create longer history for EMA computation where close drops below EMA 9
    dates = pd.date_range("2026-09-01", periods=30, freq="B")
    hist_close = np.linspace(100.0, 160.0, 30)
    # On last day, drop sharply to 140 below EMA 9
    hist_close[-1] = 140.0
    df3 = pd.DataFrame({
        "Open": hist_close - 1,
        "High": hist_close + 2,
        "Low": hist_close - 2,
        "Close": hist_close,
        "Volume": np.full(30, 1000000)
    }, index=dates)

    pos, _ = tracker.evaluate_position(pos, df3)
    assert pos["current_shares"] == 0
    # Final PnL = 11,000 + (140 - 100)*100 = 15,000 THB
    assert pos["total_realized_pnl"] == pytest.approx(15000.00, rel=1e-4)
    # Blended R = 15,000 / 4,000 = +3.75R
    assert pos["current_r"] == pytest.approx(3.75, rel=1e-2)


# =====================================================================
# 3. False Breakout Wick Rejection Combined with Turnover Filters
# =====================================================================

def test_shooting_star_rejected_despite_massive_turnover(bot4_default_config, sample_candlestick_df):
    """
    Cross-Feature Scenario:
    A Thai stock has massive institutional turnover (e.g. 100,000,000 THB >> 20,000,000 THB),
    and crosses prior high intraday, BUT finishes with a massive upper shadow (Shooting Star).
    The confluence engine candlestick filter must reject the setup!
    """
    engine = ThaiConfluenceEngine(bot4_default_config)
    df = sample_candlestick_df.copy()

    # Configure massive volume (5,000,000 shares * 50 THB = 250M THB turnover)
    df["Volume"] = 5000000

    # Ensure prior high
    prior_high = 50.00
    df.loc[df.index[-2], ["Open", "High", "Low", "Close"]] = [48.0, prior_high, 47.5, 49.0]

    # Extreme distribution candle on current day:
    # Intraday spikes to 54.00 (> prior_high), but dumped into close at 48.00
    df.loc[df.index[-1], ["Open", "High", "Low", "Close"]] = [49.0, 54.0, 47.8, 48.0]

    res = engine.evaluate_entry_trigger(df)
    assert res.get("trigger_fired", False) is False
    assert res.get("status") != "BUY_TRIGGERED"


def test_screener_strict_min_turnover_threshold(bot4_default_config, sample_candlestick_df):
    """
    Authoritative Source: Audit Proposal 2.1.5 (P1 Screener Turnover Halving Defect).
    Former defect: `if turnover_20 < self.min_turnover and turnover_20 < 10000000`
    silently halved liquidity requirements.
    Remediation mandates strict: `if turnover_20 < self.min_turnover: return None`.
    Verify that a stock with 15,000,000 THB turnover is REJECTED when min_turnover is 20,000,000 THB.
    """
    screener = ThaiStockScreener(bot4_default_config)
    assert screener.min_turnover == 20000000.0

    df = sample_candlestick_df.copy()
    # Close = ~50 THB. Set volume so turnover = 15,000,000 THB (< 20,000,000 THB)
    df["Close"] = 50.0
    df["Volume"] = 300000  # 50 * 300,000 = 15,000,000 THB

    res = screener.evaluate_candidate("SUB_LIQUID", df, None)
    # Must be rejected due to insufficient turnover
    assert res is None
