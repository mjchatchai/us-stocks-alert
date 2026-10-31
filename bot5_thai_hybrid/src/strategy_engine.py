"""
Hybrid Strategy Engine for Bot 6 (Thai SET Hybrid Trend Scanner):
1. Macro Filter: Bullish Trend (Close > EMA 50 > EMA 200, MACD > 0, 3M/6M Momentum >= 15%, 20D Turnover >= 20M THB)
2. Micro Entry: High-conviction pullback bounce to EMA 20 or EMA 50 support
3. Candlestick Confirmation: Bullish reversal candle (rejecting shooting stars and breakdowns)
"""
from dataclasses import dataclass
from typing import Dict, Optional
import pandas as pd
from .indicators import compute_ema, compute_macd


@dataclass
class ThaiHybridSignal:
    ticker: str
    entry_price: float
    curr_low: float
    prior_low: float
    support_level: float
    support_type: str
    reversal_type: str
    dist_ema50_pct: float
    perf_3m: float
    perf_6m: float
    turnover_20d: float


class ThaiHybridEngine:
    def __init__(self, config: Dict):
        self.config = config
        self.min_perf = float(config.get("min_perf_3m_or_6m_pct", 15.0))
        self.min_turnover = float(config.get("min_dollar_volume_20d", 20000000.0))

    def evaluate_ticker(self, ticker: str, df: pd.DataFrame) -> Optional[ThaiHybridSignal]:
        if df is None or len(df) < 60:
            return None

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        vol = df["Volume"]

        curr_close = float(close.iloc[-1])
        curr_high = float(high.iloc[-1])
        curr_low = float(low.iloc[-1])
        curr_open = float(df["Open"].iloc[-1]) if "Open" in df.columns else curr_close
        prior_close = float(close.iloc[-2])
        prior_low = float(low.iloc[-2])

        ema9 = compute_ema(close, 9)
        ema20 = compute_ema(close, 20)
        ema50 = compute_ema(close, 50)
        ema200 = compute_ema(close, 200)

        e9 = float(ema9.iloc[-1])
        e20 = float(ema20.iloc[-1])
        e50 = float(ema50.iloc[-1])
        e200 = float(ema200.iloc[-1]) if len(close) >= 120 else 0.0

        macd, _, _ = compute_macd(close)
        m_val = float(macd.iloc[-1])

        # -------------------------------------------------------------
        # Step 1: Macro Trend & Momentum Filter
        # -------------------------------------------------------------
        is_uptrend = (curr_close > e50 > e200) if e200 > 0 else (curr_close > e50)
        macd_bull = m_val > 0

        perf_3m = float(close.pct_change(min(63, len(close) - 1)).iloc[-1] * 100.0) if len(close) >= 30 else 0.0
        perf_6m = float(close.pct_change(min(126, len(close) - 1)).iloc[-1] * 100.0) if len(close) >= 60 else 0.0
        has_momentum = (perf_3m >= self.min_perf or perf_6m >= self.min_perf)

        turnover_20d = float((close * vol).rolling(20, min_periods=5).mean().iloc[-1])
        has_liquidity = turnover_20d >= self.min_turnover

        if not (is_uptrend and macd_bull and has_momentum and has_liquidity):
            return None

        # -------------------------------------------------------------
        # Step 2: Micro Pullback Test (Must test support zone without breaking down)
        # -------------------------------------------------------------
        near_e20 = (curr_low <= e20 * 1.015) and (curr_close >= e20 * 0.995)
        near_e50 = (curr_low <= e50 * 1.015) and (curr_close >= e50 * 0.995)

        if not (near_e20 or near_e50):
            return None

        support_type = "Daily EMA 20" if near_e20 else "Daily EMA 50"
        support_level = e20 if near_e20 else e50

        # -------------------------------------------------------------
        # Step 3: Reversal Confirmation (Bullish candle off support)
        # -------------------------------------------------------------
        body = abs(curr_close - curr_open)
        upper_wick = curr_high - max(curr_close, curr_open)
        lower_wick = min(curr_close, curr_open) - curr_low

        is_green = curr_close > curr_open
        hammer = (lower_wick >= 1.5 * max(body, 0.02)) and (upper_wick <= 1.0 * max(body, 0.02))
        bounce_e9 = curr_close > e9 and curr_close > prior_close
        is_shooting_star = (upper_wick >= 2.5 * max(body, 0.02)) and (lower_wick <= 0.5 * upper_wick)

        # Reject severe shooting stars / upper rejection dojis
        if is_shooting_star:
            return None

        if not (is_green or hammer or bounce_e9):
            return None

        reversal_type = "Hammer / Tail Rejection" if hammer else "Bullish Candle off EMA Support"
        dist_ema50 = ((curr_close - e50) / e50) * 100.0

        return ThaiHybridSignal(
            ticker=ticker,
            entry_price=round(curr_close, 2),
            curr_low=round(curr_low, 2),
            prior_low=round(prior_low, 2),
            support_level=round(support_level, 2),
            support_type=support_type,
            reversal_type=reversal_type,
            dist_ema50_pct=round(dist_ema50, 1),
            perf_3m=round(perf_3m, 1),
            perf_6m=round(perf_6m, 1),
            turnover_20d=round(turnover_20d, 0)
        )
