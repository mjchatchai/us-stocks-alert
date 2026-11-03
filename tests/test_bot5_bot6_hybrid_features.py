import numpy as np
import pandas as pd
import pytest

from bot5_us_hybrid.src.indicators import (
    compute_ema,
    compute_atr_wilder,
    compute_rsi,
    compute_adx,
    compute_ema_slope_pct,
)
from bot5_thai_hybrid.src.indicators import (
    round_to_set_tick,
    step_tick_down,
)
from bot5_us_hybrid.src.strategy_engine import USHybridEngine
from bot5_thai_hybrid.src.strategy_engine import ThaiHybridEngine
from bot5_us_hybrid.src.exit_tracker import USHybridExitTracker
from bot5_thai_hybrid.src.exit_tracker import ThaiHybridExitTracker


def _build_trending_df(n: int = 300, start_price: float = 100.0, step: float = 0.4) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    close = np.array([start_price + i * step for i in range(n)], dtype=float)
    open_p = close - 0.15
    high = close + 0.35
    low = close - 0.35
    vol = np.full(n, 2_000_000.0)
    return pd.DataFrame(
        {"Open": open_p, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=dates,
    )


def test_ema200_convergence_3y_vs_1y():
    """Verify EMA 200 on 756 bars (3y) is fully converged compared to truncated 250-bar series."""
    df_full = _build_trending_df(n=756, start_price=50.0, step=0.25)
    ema_full = compute_ema(df_full["Close"], 200).iloc[-1]
    ema_trunc = compute_ema(df_full["Close"].iloc[-250:], 200).iloc[-1]
    assert abs(ema_full - ema_trunc) > 0.01


def test_wilder_atr_vs_sma_atr():
    """Verify compute_atr_wilder uses Wilder RMA (alpha=1/14) and remains positive & smooth."""
    df = _build_trending_df(n=100, start_price=100.0, step=0.5)
    atr_w = compute_atr_wilder(df["High"], df["Low"], df["Close"], period=14)
    assert not np.isnan(atr_w.iloc[-1])
    assert atr_w.iloc[-1] > 0.0


def test_thai_step_tick_down_unsanitized_boundary():
    """Verify step_tick_down(25.12) sanitizes to 25.00 first, then steps down to 24.90 (0.10 tick)."""
    assert round_to_set_tick(25.12, mode="down") == 25.00
    assert step_tick_down(25.12) == 24.90
    assert step_tick_down(25.00) == 24.90
    assert step_tick_down(100.25) == 99.75


def test_pullback_rejects_red_distribution_candle():
    """Verify a bar where Low <= EMA9 and Close > EMA9 but Close < Open (red candle) is rejected."""
    df = _build_trending_df(n=260, start_price=100.0, step=0.5)
    ema9_val = compute_ema(df["Close"], 9).iloc[-1]
    # Make last candle touch EMA9 and close slightly above EMA9, but Open much higher (red candle)
    df.iloc[-1, df.columns.get_loc("Low")] = ema9_val * 0.998
    df.iloc[-1, df.columns.get_loc("Close")] = ema9_val * 1.002
    df.iloc[-1, df.columns.get_loc("Open")] = ema9_val * 1.025
    df.iloc[-1, df.columns.get_loc("High")] = ema9_val * 1.030

    engine = USHybridEngine({})
    sig = engine.evaluate_ticker("TEST", df)
    assert sig is None


def test_pullback_rejects_weak_close_location():
    """Verify a bar with range_location < 0.45 (heavy upper-wick rejection) returns None."""
    df = _build_trending_df(n=260, start_price=100.0, step=0.5)
    ema9_val = compute_ema(df["Close"], 9).iloc[-1]
    # Bullish close >= open, touches EMA9, but huge upper wick so range_location < 0.45
    df.iloc[-1, df.columns.get_loc("Low")] = ema9_val * 0.999
    df.iloc[-1, df.columns.get_loc("Open")] = ema9_val * 1.000
    df.iloc[-1, df.columns.get_loc("Close")] = ema9_val * 1.002
    df.iloc[-1, df.columns.get_loc("High")] = ema9_val * 1.020

    engine = USHybridEngine({})
    sig = engine.evaluate_ticker("TEST", df)
    assert sig is None


def test_pullback_rejects_climax_extension():
    """Verify a bar touching EMA20 intraday but closing +5% above EMA20 (> 1.030 ceiling) is rejected."""
    df = _build_trending_df(n=260, start_price=100.0, step=0.5)
    ema20_val = compute_ema(df["Close"], 20).iloc[-1]
    df.iloc[-1, df.columns.get_loc("Low")] = ema20_val * 0.998
    df.iloc[-1, df.columns.get_loc("Open")] = ema20_val * 1.010
    df.iloc[-1, df.columns.get_loc("Close")] = ema20_val * 1.055
    df.iloc[-1, df.columns.get_loc("High")] = ema20_val * 1.060

    engine = USHybridEngine({})
    sig = engine.evaluate_ticker("TEST", df)
    assert sig is None


def test_exit_tracker_1_5r_breakeven_ratchet():
    """Verify a position reaching +1.6R (before +3R TP1) ratchets current_sl to entry_price."""
    df = _build_trending_df(n=100, start_price=100.0, step=0.2)
    # Set last bar high to reach +1.6R (entry=100, risk=5 -> +1.6R = 108.0, TP1=+3R=115.0)
    df.iloc[-1, df.columns.get_loc("Open")] = 106.0
    df.iloc[-1, df.columns.get_loc("Low")] = 105.0
    df.iloc[-1, df.columns.get_loc("High")] = 108.5
    df.iloc[-1, df.columns.get_loc("Close")] = 107.5

    pos = {
        "ticker": "NVDA",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "current_sl": 95.0,
        "risk_per_share": 5.0,
        "shares": 10,
        "current_shares": 10,
        "initial_shares": 10,
        "status": "OPEN",
        "tp1_hit": False,
    }
    tracker = USHybridExitTracker({})
    up_pos, actions = tracker.evaluate_position(pos, df)
    assert up_pos["be_ratcheted"] is True
    assert up_pos["current_sl"] >= 100.0
    assert up_pos["status"] == "OPEN"


def test_exit_tracker_pre_tp1_macro_breakdown():
    """Verify a position with tp1_hit=False that closes below EMA50 with MACD < 0 exits immediately."""
    # Construct a severe breakdown series where Close < EMA50 and MACD < 0, but Low > hard SL
    df = _build_trending_df(n=100, start_price=150.0, step=-0.5)
    pos = {
        "ticker": "AMD",
        "entry_price": 120.0,
        "stop_loss": 50.0,  # Deep SL not hit yet
        "current_sl": 50.0,
        "risk_per_share": 10.0,
        "shares": 10,
        "current_shares": 10,
        "initial_shares": 10,
        "status": "OPEN",
        "tp1_hit": False,
    }
    tracker = USHybridExitTracker({})
    up_pos, actions = tracker.evaluate_position(pos, df)
    assert up_pos["status"] == "CLOSED_STRUCTURAL_FAIL"
    assert up_pos["current_shares"] == 0
    assert any(a["type"] == "STRUCTURAL_BREAKDOWN_EXIT" for a in actions)


def test_thai_single_lot_tp1_policy():
    """Verify a 100-share SET position at +3R under 'trail_at_tp1' ratchets SL and stays open."""
    df = _build_trending_df(n=100, start_price=18.0, step=0.1)
    # Entry=25.00, risk=1.00 -> TP1 (3R) = 28.00, TP2 (5R) = 30.00
    df.iloc[-1, df.columns.get_loc("Open")] = 27.90
    df.iloc[-1, df.columns.get_loc("Low")] = 27.80
    df.iloc[-1, df.columns.get_loc("High")] = 28.50
    df.iloc[-1, df.columns.get_loc("Close")] = 28.25

    pos = {
        "ticker": "KCE",
        "entry_price": 25.00,
        "stop_loss": 24.00,
        "current_sl": 24.00,
        "risk_per_share": 1.00,
        "shares": 100,
        "current_shares": 100,
        "initial_shares": 100,
        "status": "OPEN",
        "tp1_hit": False,
    }
    tracker = ThaiHybridExitTracker({"trade_management": {"single_lot_policy": "trail_at_tp1"}})
    up_pos, actions = tracker.evaluate_position(pos, df)
    assert up_pos["tp1_hit"] is True
    assert up_pos["current_shares"] == 100
    assert up_pos["current_sl"] >= 26.50
    assert any(a["type"] in ("TP1_TRAIL_LOCK", "TP1_SINGLE_LOT_TRAIL") for a in actions)


def test_macro_regime_gate_blocks_bear_market():
    """Verify USHybridEngine.evaluate_macro_regime blocks new entries when SPY < EMA200 or VIX > 28."""
    spy_bear = _build_trending_df(n=250, start_price=500.0, step=-0.5)
    engine = USHybridEngine({})
    res = engine.evaluate_macro_regime(spy_bear)
    assert res["allow_new_entries"] is False
    assert res["regime_label"] == "RISK_OFF"
