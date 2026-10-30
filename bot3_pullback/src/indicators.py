"""
Indicators & Pattern Detection for Bot 3 (Pullback & R-Multiple Strategy)
Supports:
- EMAs: 9, 21, 50, 200
- Anchored VWAP (AVWAP)
- ATR & Bollinger Bandwidth (Volatility Contraction / VCP)
- Multi-period Returns (1M, 3M, 6M) & Dollar Volume
- Swing Pivots (Higher Lows detection)
- Price Gap detection (Gap Support)
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average (EMA)."""
    return series.ewm(span=period, adjust=False).mean()


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range (ATR)."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=period).mean()


def compute_bollinger_bands(
    df: pd.DataFrame, period: int = 20, num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands and Bandwidth."""
    close = df["Close"]
    sma = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = sma + (std * num_std)
    lower = sma - (std * num_std)
    bandwidth = (upper - lower) / (sma.replace(0, np.nan)) * 100.0
    return upper, sma, lower, bandwidth


def compute_avwap(
    df: pd.DataFrame, anchor_idx: Optional[int] = None, anchor_date: Optional[str] = None
) -> pd.Series:
    """
    Calculate Anchored VWAP from an index or date.
    If no anchor provided, anchors to the lowest low of the last 60 bars.
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
        # Default anchor: lowest swing low within last 60 bars (base foundation)
        lookback = min(60, len(df))
        start_pos = len(df) - lookback + df["Low"].iloc[-lookback:].values.argmin()

    avwap = pd.Series(index=df.index, dtype=float)
    if start_pos < len(df):
        tp_subset = typical_price.iloc[start_pos:]
        vol_subset = volume.iloc[start_pos:]
        cum_tp_vol = (tp_subset * vol_subset).cumsum()
        cum_vol = vol_subset.cumsum()
        avwap.iloc[start_pos:] = cum_tp_vol / cum_vol
        # Forward fill before anchor with first computed value if needed
        avwap.iloc[:start_pos] = np.nan

    return avwap


def compute_performance_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """Calculate 1M (21 bars), 3M (63 bars), 6M (126 bars) returns and volume metrics."""
    n = len(df)
    if n == 0:
        return {}

    curr_close = float(df["Close"].iloc[-1])

    ret_1m = (
        ((curr_close / float(df["Close"].iloc[-22])) - 1.0) * 100.0
        if n >= 22
        else 0.0
    )
    ret_3m = (
        ((curr_close / float(df["Close"].iloc[-64])) - 1.0) * 100.0
        if n >= 64
        else 0.0
    )
    ret_6m = (
        ((curr_close / float(df["Close"].iloc[-127])) - 1.0) * 100.0
        if n >= 127
        else 0.0
    )

    vol_20 = (
        float(df["Volume"].iloc[-20:].mean()) if n >= 20 else float(df["Volume"].mean())
    )
    dollar_vol_20 = (
        float((df["Volume"] * df["Close"]).iloc[-20:].mean())
        if n >= 20
        else float((df["Volume"] * df["Close"]).mean())
    )

    return {
        "ret_1m": round(ret_1m, 2),
        "ret_3m": round(ret_3m, 2),
        "ret_6m": round(ret_6m, 2),
        "vol_20": round(vol_20, 0),
        "dollar_vol_20": round(dollar_vol_20, 0),
    }


def detect_swing_pivots(
    df: pd.DataFrame, left: int = 3, right: int = 3
) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """
    Detect local swing highs and swing lows.
    Returns: (swing_highs, swing_lows) as lists of (bar_index, price).
    """
    highs = []
    lows = []
    n = len(df)
    if n < left + right + 1:
        return highs, lows

    for i in range(left, n - right):
        h = df["High"].iloc[i]
        l = df["Low"].iloc[i]

        is_high = True
        for j in range(i - left, i + right + 1):
            if j != i and df["High"].iloc[j] >= h:
                is_high = False
                break
        if is_high:
            highs.append((i, float(h)))

        is_low = True
        for j in range(i - left, i + right + 1):
            if j != i and df["Low"].iloc[j] <= l:
                is_low = False
                break
        if is_low:
            lows.append((i, float(l)))

    return highs, lows


def check_higher_lows(df: pd.DataFrame, lookback: int = 40) -> Tuple[bool, Optional[float], Optional[float]]:
    """
    Check if the most recent swing low is higher than the preceding swing low.
    Returns: (is_higher_low, recent_low, prior_low)
    """
    sub_df = df.iloc[-lookback:] if len(df) > lookback else df
    _, lows = detect_swing_pivots(sub_df, left=2, right=2)
    if len(lows) >= 2:
        recent_low = lows[-1][1]
        prior_low = lows[-2][1]
        return recent_low >= prior_low * 0.985, recent_low, prior_low
    return True, None, None


def check_volatility_contraction(df: pd.DataFrame) -> Tuple[bool, float, float]:
    """
    Detect Volatility Contraction Pattern (VCP):
    Check if ATR(5) is contracting relative to ATR(20), or recent range is tighter.
    Returns: (is_contracting, contraction_ratio, bb_width)
    """
    if len(df) < 25:
        return False, 1.0, 0.0

    atr5 = compute_atr(df, period=5).iloc[-1]
    atr20 = compute_atr(df, period=20).iloc[-1]
    ratio = float(atr5 / atr20) if atr20 and atr20 > 0 else 1.0

    _, _, _, bb_width = compute_bollinger_bands(df, period=20)
    current_bbw = float(bb_width.iloc[-1]) if not np.isnan(bb_width.iloc[-1]) else 0.0
    avg_bbw = float(bb_width.iloc[-20:].mean()) if len(bb_width) >= 20 else current_bbw

    is_contracting = (ratio <= 0.95) or (current_bbw <= avg_bbw * 0.95)
    return is_contracting, round(ratio, 2), round(current_bbw, 2)


def detect_recent_gaps(
    df: pd.DataFrame, lookback: int = 20, min_gap_pct: float = 0.8
) -> List[Dict[str, float]]:
    """
    Detect unfilled upward price gaps within recent lookback bars.
    Returns list of gap dictionaries with top and bottom prices.
    """
    gaps = []
    n = len(df)
    start_i = max(1, n - lookback)

    for i in range(start_i, n):
        prev_high = float(df["High"].iloc[i - 1])
        curr_low = float(df["Low"].iloc[i])
        if curr_low > prev_high * (1.0 + min_gap_pct / 100.0):
            # Upward gap zone [prev_high, curr_low]
            # Check if price has completely filled it since
            future_lows = df["Low"].iloc[i:n]
            if future_lows.min() > prev_high:
                gaps.append({
                    "date": str(df.index[i])[:10],
                    "bottom": prev_high,
                    "top": curr_low,
                    "mid": round((prev_high + curr_low) / 2.0, 2),
                })
    return gaps


def check_ema_slopes(
    ema_fast: pd.Series, ema_slow: pd.Series, lookback: int = 5
) -> Tuple[bool, bool, float, float]:
    """
    Check if EMA 9 and EMA 21 are flat or turning up.
    Returns: (fast_up, slow_up, fast_slope_pct, slow_slope_pct)
    """
    if len(ema_fast) <= lookback or len(ema_slow) <= lookback:
        return True, True, 0.0, 0.0

    f_now = float(ema_fast.iloc[-1])
    f_prev = float(ema_fast.iloc[-lookback])
    f_slope = ((f_now - f_prev) / f_prev) * 100.0 if f_prev > 0 else 0.0

    s_now = float(ema_slow.iloc[-1])
    s_prev = float(ema_slow.iloc[-lookback])
    s_slope = ((s_now - s_prev) / s_prev) * 100.0 if s_prev > 0 else 0.0

    # Flat or up: slope >= -0.2%
    fast_up = f_slope >= -0.2
    slow_up = s_slope >= -0.2
    return fast_up, slow_up, round(f_slope, 2), round(s_slope, 2)
