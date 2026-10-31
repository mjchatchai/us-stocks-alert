"""
Indicators & Pattern Detection for Bot 4 (Thai Stocks Pullback & R-Multiple Strategy)
Adapted for SET Market:
- EMAs: 9, 21, 50, 200
- Anchored VWAP (AVWAP)
- ATR & Bollinger Bandwidth (Volatility Contraction / VCP)
- Performance Metrics: 1M, 3M, 6M & 20D Turnover (Baht)
- Swing Pivots (Higher Lows) & Price Gaps
- Official Thai Stock Exchange (SET) Tick Size Table
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


def get_thai_tick_size(price: float) -> float:
    """
    Get official SET Tick Size (spread) based on 8-tier price schedule:
    - Below 2.00 Baht: 0.01
    - 2.00 to 4.98 Baht: 0.02
    - 5.00 to 9.95 Baht: 0.05
    - 10.00 to 24.90 Baht: 0.10
    - 25.00 to 99.75 Baht: 0.25
    - 100.00 to 199.50 Baht: 0.50
    - 200.00 to 398.00 Baht: 1.00
    - 400.00 Baht and above: 2.00 (Tier 8)
    """
    p = float(price)
    if p < 2.0:
        return 0.01
    elif p < 5.0:
        return 0.02
    elif p < 10.0:
        return 0.05
    elif p < 25.0:
        return 0.10
    elif p < 100.0:
        return 0.25
    elif p < 200.0:
        return 0.50
    elif p < 400.0:
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
    - 25.00 -> 24.90
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
    """
    Snaps any arbitrary floating-point price to a legal SET tick increment.
    Modes:
      - 'nearest': Round to closest valid SET tick
      - 'down': Floor to nearest valid SET tick
      - 'up': Ceil to nearest valid SET tick
    """
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
        start_pos = len(df) - lookback + df["Low"].iloc[-lookback:].values.argmin()

    avwap = pd.Series(index=df.index, dtype=float)
    if start_pos < len(df):
        tp_subset = typical_price.iloc[start_pos:]
        vol_subset = volume.iloc[start_pos:]
        cum_tp_vol = (tp_subset * vol_subset).cumsum()
        cum_vol = vol_subset.cumsum()
        avwap.iloc[start_pos:] = cum_tp_vol / cum_vol
        avwap.iloc[:start_pos] = np.nan

    return avwap


def compute_performance_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """Calculate 1M (21 bars), 3M (63 bars), 6M (126 bars) returns and volume/turnover metrics."""
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
    # Average daily turnover in Baht
    turnover_20 = (
        float((df["Volume"] * df["Close"]).iloc[-20:].mean())
        if n >= 20
        else float((df["Volume"] * df["Close"]).mean())
    )

    return {
        "ret_1m": round(ret_1m, 2),
        "ret_3m": round(ret_3m, 2),
        "ret_6m": round(ret_6m, 2),
        "vol_20": round(vol_20, 0),
        "turnover_20": round(turnover_20, 0),
    }


def detect_swing_pivots(
    df: pd.DataFrame, left: int = 3, right: int = 3
) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """Detect swing highs and swing lows."""
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
    """Check if the most recent swing low is higher than prior swing low (Higher Low)."""
    sub_df = df.iloc[-lookback:] if len(df) > lookback else df
    _, lows = detect_swing_pivots(sub_df, left=2, right=2)
    if len(lows) >= 2:
        recent_low = lows[-1][1]
        prior_low = lows[-2][1]
        return recent_low >= prior_low * 0.985, recent_low, prior_low
    return True, None, None


def check_volatility_contraction(df: pd.DataFrame) -> Tuple[bool, float, float]:
    """Detect VCP Volatility Contraction Pattern."""
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
    """Detect unfilled price gap zones."""
    gaps = []
    n = len(df)
    start_i = max(1, n - lookback)

    for i in range(start_i, n):
        prev_high = float(df["High"].iloc[i - 1])
        curr_low = float(df["Low"].iloc[i])
        if curr_low > prev_high * (1.0 + min_gap_pct / 100.0):
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
    """Check if EMA 9 and EMA 21 are flat or turning up."""
    if len(ema_fast) <= lookback or len(ema_slow) <= lookback:
        return True, True, 0.0, 0.0

    f_now = float(ema_fast.iloc[-1])
    f_prev = float(ema_fast.iloc[-lookback])
    f_slope = ((f_now - f_prev) / f_prev) * 100.0 if f_prev > 0 else 0.0

    s_now = float(ema_slow.iloc[-1])
    s_prev = float(ema_slow.iloc[-lookback])
    s_slope = ((s_now - s_prev) / s_prev) * 100.0 if s_prev > 0 else 0.0

    fast_up = f_slope >= -0.2
    slow_up = s_slope >= -0.2
    return fast_up, slow_up, round(f_slope, 2), round(s_slope, 2)
