"""
Indicators calculation matching TradingView Pine Script exact formulas:
1. EMA 9 & EMA 21
2. CM_Ult_MacD_MTF (ChrisMoody Ultimate MACD - Signal uses SMA(9))
3. KDJ (ll21LAMBO21 - Period=9, Signal=3 using bcwsma smoothing)
"""

import numpy as np
import pandas as pd


def pine_ema(series: pd.Series, length: int) -> pd.Series:
    """
    Matches TradingView Pine Script ta.ema(source, length).
    Uses alpha = 2 / (length + 1) with adjust=False.
    """
    return series.ewm(span=length, adjust=False).mean()


def pine_sma(series: pd.Series, length: int) -> pd.Series:
    """
    Matches TradingView Pine Script ta.sma(source, length).
    """
    return series.rolling(window=length, min_periods=length).mean()


def pine_bcwsma(series: pd.Series, length: int, weight: int = 1) -> pd.Series:
    """
    Matches ll21LAMBO21's Pine Script custom function:
    bcwsma(s, l, m) =>
        _bcwsma := (m * s + (l - m) * nz(_bcwsma[1])) / l
    """
    values = series.to_numpy(dtype=float)
    result = np.full_like(values, np.nan, dtype=float)
    prev = 0.0  # nz(_bcwsma[1]) defaults to 0.0 when previous value is na
    for i, val in enumerate(values):
        if np.isnan(val):
            continue
        curr = (weight * val + (length - weight) * prev) / length
        result[i] = curr
        prev = curr
    return pd.Series(result, index=series.index)


def compute_all_indicators(
    df: pd.DataFrame,
    ema_fast: int = 9,
    ema_slow: int = 21,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    kdj_period: int = 9,
    kdj_signal: int = 3,
) -> pd.DataFrame:
    """
    Computes all 3 indicators and their exact TradingView signals on OHLCV DataFrame.
    Expects columns: ['Open', 'High', 'Low', 'Close', 'Volume'].
    """
    out = df.copy()
    close = out["Close"].astype(float)
    high = out["High"].astype(float)
    low = out["Low"].astype(float)

    # ---------------------------------------------------------
    # 1. EMA 9 & EMA 21
    # ---------------------------------------------------------
    out["ema_fast"] = pine_ema(close, ema_fast)
    out["ema_slow"] = pine_ema(close, ema_slow)

    # EMA Crossover / Crossunder
    prev_ema_fast = out["ema_fast"].shift(1)
    prev_ema_slow = out["ema_slow"].shift(1)
    out["ema_cross_up"] = (prev_ema_fast <= prev_ema_slow) & (out["ema_fast"] > out["ema_slow"])
    out["ema_cross_down"] = (prev_ema_fast >= prev_ema_slow) & (out["ema_fast"] < out["ema_slow"])
    out["ema_bullish"] = out["ema_fast"] > out["ema_slow"]
    out["ema_bearish"] = out["ema_fast"] < out["ema_slow"]

    # ---------------------------------------------------------
    # 2. ChrisMoody MACD (CM_Ult_MacD_MTF)
    # fastMA = ema(close, 12), slowMA = ema(close, 26)
    # macd = fastMA - slowMA
    # signal = sma(macd, 9)  <-- ChrisMoody uses SMA for signal line!
    # ---------------------------------------------------------
    fast_ma = pine_ema(close, macd_fast)
    slow_ma = pine_ema(close, macd_slow)
    out["macd"] = fast_ma - slow_ma
    out["macd_signal"] = pine_sma(out["macd"], macd_signal)
    out["macd_hist"] = out["macd"] - out["macd_signal"]

    prev_macd = out["macd"].shift(1)
    prev_sig = out["macd_signal"].shift(1)
    out["macd_green_dot"] = (prev_macd <= prev_sig) & (out["macd"] > out["macd_signal"])
    out["macd_red_dot"] = (prev_macd >= prev_sig) & (out["macd"] < out["macd_signal"])
    out["macd_bullish"] = out["macd"] >= out["macd_signal"]
    out["macd_bearish"] = out["macd"] < out["macd_signal"]

    # ChrisMoody 4-Color Histogram
    prev_hist = out["macd_hist"].shift(1)
    hist_color = np.where(
        (out["macd_hist"] > 0) & (out["macd_hist"] >= prev_hist),
        "aqua",
        np.where(
            (out["macd_hist"] > 0) & (out["macd_hist"] < prev_hist),
            "blue",
            np.where(
                (out["macd_hist"] <= 0) & (out["macd_hist"] <= prev_hist),
                "red",
                "maroon",
            ),
        ),
    )
    out["macd_hist_color"] = hist_color

    # ---------------------------------------------------------
    # 3. KDJ by ll21LAMBO21 (period=9, signal=3)
    # ---------------------------------------------------------
    highest_h = high.rolling(window=kdj_period, min_periods=1).max()
    lowest_l = low.rolling(window=kdj_period, min_periods=1).min()
    hl_range = highest_h - lowest_l
    rsv = np.where(hl_range == 0, 0.0, 100.0 * ((close - lowest_l) / hl_range))
    out["rsv"] = pd.Series(rsv, index=out.index)

    out["kdj_k"] = pine_bcwsma(out["rsv"], kdj_signal, 1)
    out["kdj_d"] = pine_bcwsma(out["kdj_k"], kdj_signal, 1)
    out["kdj_j"] = 3.0 * out["kdj_k"] - 2.0 * out["kdj_d"]

    # In ll21LAMBO21 KDJ: background is green when J > D, red when J <= D
    out["kdj_green"] = out["kdj_j"] > out["kdj_d"]
    out["kdj_red"] = ~out["kdj_green"]

    return out
