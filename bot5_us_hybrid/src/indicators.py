"""
Technical Indicators for Bot 5 US Hybrid
"""
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
    rsv = ((close - low_min) / (high_max - low_min).replace(0, np.nan)) * 100.0
    rsv = rsv.fillna(50.0)
    k = rsv.ewm(alpha=1.0/m, adjust=False).mean()
    d = k.ewm(alpha=1.0/m, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j

def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()
