"""
Technical Indicators for Bot 5 (US Macro Trend Hybrid Scanner)
Includes Wilder's RMA ATR, RSI(14), ADX(14)/DMI, EMA Slope, MACD, KDJ, and Anchored VWAP.
"""
from typing import Optional, Tuple
import pandas as pd
import numpy as np


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def compute_ema_slope_pct(ema_series: pd.Series, lookback: int = 5) -> float:
    """
    Computes normalized per-bar percentage slope of an EMA series over `lookback` bars:
    Slope_k = ((EMA[t] - EMA[t-k]) / (k * EMA[t])) * 100%
    """
    if ema_series is None or len(ema_series) <= lookback:
        return 0.0
    curr_val = float(ema_series.iloc[-1])
    prev_val = float(ema_series.iloc[-1 - lookback])
    if curr_val <= 0 or np.isnan(curr_val) or np.isnan(prev_val):
        return 0.0
    return ((curr_val - prev_val) / (lookback * curr_val)) * 100.0


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


def compute_atr_wilder(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Computes Welles Wilder's Running Moving Average (RMA) Average True Range:
    alpha = 1.0 / period (matches TradingView ta.atr).
    """
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Standard ATR using Wilder's RMA smoothing."""
    return compute_atr_wilder(high, low, close, period=period)


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Computes Welles Wilder's Relative Strength Index (RSI) using RMA (alpha = 1 / period).
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    # Handle completely flat series where both gain and loss are 0
    flat_mask = (avg_gain < 1e-9) & (avg_loss < 1e-9)
    rsi = rsi.mask(flat_mask, 50.0)
    return rsi.fillna(50.0)


def compute_adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Computes Welles Wilder's Average Directional Index (ADX) and Directional Indicators (+DI, -DI).
    Returns: (adx, plus_di, minus_di)
    """
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=close.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=close.index,
    )

    atr = compute_atr_wilder(high, low, close, period=period)
    atr_safe = atr.replace(0, np.nan).fillna(1e-9)

    plus_di = 100.0 * (plus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr_safe)
    minus_di = 100.0 * (minus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr_safe)

    di_sum = plus_di + minus_di
    dx = 100.0 * ((plus_di - minus_di).abs() / (di_sum + 1e-9))
    adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()

    return adx.fillna(0.0), plus_di.fillna(0.0), minus_di.fillna(0.0)


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
