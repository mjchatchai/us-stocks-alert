"""
Technical Indicators & SET Tick Size Rules for Bot 5 Thai Hybrid
"""
import pandas as pd
import numpy as np

def get_thai_tick_size(price: float) -> float:
    if price < 2.0: return 0.01
    elif price < 5.0: return 0.02
    elif price < 10.0: return 0.05
    elif price < 25.0: return 0.10
    elif price < 100.0: return 0.25
    elif price < 200.0: return 0.50
    else: return 1.00

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
