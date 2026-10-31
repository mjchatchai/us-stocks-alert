"""
Technical Indicators & SET Tick Size Rules for Bot 6 (Thai SET Hybrid Trend Scanner)
"""
from typing import Optional, Dict
import pandas as pd
import numpy as np


def get_thai_tick_size(price: float) -> float:
    """Official 8-tier Stock Exchange of Thailand (SET) tick size schedule."""
    if price < 2.0:
        return 0.01
    elif price < 5.0:
        return 0.02
    elif price < 10.0:
        return 0.05
    elif price < 25.0:
        return 0.10
    elif price < 100.0:
        return 0.25
    elif price < 200.0:
        return 0.50
    elif price < 400.0:
        return 1.00
    else:
        return 2.00  # Official SET Tier 8 (>= 400.0 THB)


def step_tick_down(price: float) -> float:
    """
    Steps down exactly 1 valid SET tick across tier boundaries.
    Correctly transitions boundary prices into the lower tier:
    - 2.00  -> 1.99
    - 5.00  -> 4.98
    - 10.00 -> 9.95
    - 25.00 -> 24.90 (Not 24.75!)
    - 100.00 -> 99.75
    - 200.00 -> 199.50
    - 400.00 -> 399.00
    """
    p = round(float(price), 4)
    if p <= 0.01:
        return 0.01
    if 1.99 < p <= 2.00:
        return 1.99
    elif 4.98 < p <= 5.00:
        return 4.98
    elif 9.95 < p <= 10.00:
        return 9.95
    elif 24.90 < p <= 25.00:
        return 24.90
    elif 99.75 < p <= 100.00:
        return 99.75
    elif 199.50 < p <= 200.00:
        return 199.50
    elif 399.00 < p <= 400.00:
        return 399.00
    else:
        # Step down using the tick size of the region just below current price
        tick = get_thai_tick_size(p - 0.0001)
        return round(max(0.01, p - tick), 2)


def round_to_set_tick(price: float, mode: str = "nearest") -> float:
    """Snaps any arbitrary floating-point price to a legal SET tick increment."""
    p = round(float(price), 4)
    if p <= 0.01:
        return 0.01
    tick = get_thai_tick_size(p)
    if mode == "down":
        val = np.floor(p / tick + 1e-9) * tick
    elif mode == "up":
        val = np.ceil(p / tick - 1e-9) * tick
    else:
        val = np.round(p / tick) * tick

    # Check if snapped value crossed into adjacent tick tier
    new_tick = get_thai_tick_size(val)
    if new_tick != tick:
        if mode == "down":
            val = np.floor(val / new_tick + 1e-9) * new_tick
        elif mode == "up":
            val = np.ceil(val / new_tick - 1e-9) * new_tick
        else:
            val = np.round(val / new_tick) * new_tick

    return round(float(val), 2)


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = compute_ema(series, fast)
    ema_slow = compute_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def compute_kdj(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9, m: int = 3):
    low_min = low.rolling(window=n, min_periods=1).min()
    high_max = high.rolling(window=n, min_periods=1).max()
    hl_range = high_max - low_min
    hl_range_safe = np.where(hl_range == 0, np.nan, hl_range)
    rsv = ((close - low_min) / hl_range_safe) * 100.0
    rsv = pd.Series(rsv, index=close.index).ffill().fillna(50.0)
    k = rsv.ewm(alpha=1.0 / m, adjust=False).mean()
    d = k.ewm(alpha=1.0 / m, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=1).mean()


def compute_avwap(
    df: pd.DataFrame, anchor_idx: Optional[int] = None, anchor_date: Optional[str] = None
) -> pd.Series:
    """
    Calculate Anchored VWAP from an index or date.
    Default: Lowest swing low within the last 60 bars.
    """
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3.0
    volume = df["Volume"].replace(0, np.nan).fillna(1)

    if anchor_date is not None and anchor_date in df.index:
        start_pos = df.index.get_loc(anchor_date)
        if isinstance(start_pos, slice):
            start_pos = start_pos.start
    elif anchor_idx is not None and 0 <= anchor_idx < len(df):
        start_pos = anchor_idx
    else:
        lookback = min(60, len(df))
        start_pos = len(df) - lookback + int(df["Low"].iloc[-lookback:].values.argmin())

    avwap = pd.Series(index=df.index, dtype=float)
    if start_pos < len(df):
        tp_subset = typical_price.iloc[start_pos:]
        vol_subset = volume.iloc[start_pos:]
        cum_tp_vol = (tp_subset * vol_subset).cumsum()
        cum_vol = vol_subset.cumsum()
        avwap.iloc[start_pos:] = cum_tp_vol / cum_vol
        avwap.iloc[:start_pos] = np.nan

    return avwap
