"""
Technical Indicators for Bot 5 (US Macro Trend Hybrid Scanner)
"""
from typing import Optional
import pandas as pd
import numpy as np


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
