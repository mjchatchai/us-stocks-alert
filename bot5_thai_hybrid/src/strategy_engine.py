"""
Hybrid Strategy Engine for Bot 5 Thai SET
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
        if df is None or len(df) < 80:
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
        e200 = float(ema200.iloc[-1])

        macd, _, _ = compute_macd(close)
        m_val = float(macd.iloc[-1])

        # Step 1: Macro Trend Filter (6-Button Green Alignment)
        is_uptrend = (curr_close > e50 > e200) if e200 > 0 else (curr_close > e50)
        macd_bull = m_val > 0

        perf_3m = float(close.pct_change(63).iloc[-1] * 100.0) if len(close) >= 63 else 0.0
        perf_6m = float(close.pct_change(126).iloc[-1] * 100.0) if len(close) >= 126 else 0.0
        has_momentum = (perf_3m >= self.min_perf or perf_6m >= self.min_perf)

        turnover_20d = float((close * vol).rolling(20).mean().iloc[-1]) if len(vol) >= 20 else 0.0
        has_liquidity = turnover_20d >= self.min_turnover

        if not (is_uptrend and macd_bull and has_momentum and has_liquidity):
            return None

        # Step 2: Micro Pullback to EMA 20 or EMA 50
        dist_e20 = abs(curr_close - e20) / e20 * 100.0
        dist_e50 = abs(curr_close - e50) / e50 * 100.0

        near_e20 = dist_e20 <= 2.5 or (curr_low <= e20 <= curr_high)
        near_e50 = dist_e50 <= 2.5 or (curr_low <= e50 <= curr_high)

        if not (near_e20 or near_e50):
            return None

        support_type = "Daily EMA 20" if near_e20 else "Daily EMA 50"
        support_level = e20 if near_e20 else e50

        # Step 3: Reversal Confirmation
        is_green = curr_close > curr_open
        hammer = (min(curr_open, curr_close) - curr_low) >= 1.5 * abs(curr_close - curr_open)
        bounce_e9 = curr_close > e9 and curr_close > prior_close

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
