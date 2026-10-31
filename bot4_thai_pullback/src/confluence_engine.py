"""
Confluence Support Engine & Entry Trigger for Bot 4 (Thai Stocks SET - Step [2/4])
- Identifies Confluence Support Zone:
  * Dynamic EMAs: 9, 21, 50
  * Anchored VWAP (AVWAP) from swing low foundation
  * Prior Resistance turned Support (Breakout Pivots)
  * Price Gaps (Gap Support)
- Detects First Retest setup
- Evaluates Entry Trigger: Breakout above Prior Candle High
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

try:
    from .indicators import (
        compute_ema,
        compute_avwap,
        detect_swing_pivots,
        detect_recent_gaps,
    )
except ImportError:
    from indicators import (
        compute_ema,
        compute_avwap,
        detect_swing_pivots,
        detect_recent_gaps,
    )



class ThaiConfluenceEngine:
    def __init__(self, config: Dict):
        self.config = config

    def calculate_confluence_support(self, df: pd.DataFrame) -> Dict:
        """Calculate support confluence levels for Thai stock."""
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        curr_close = float(close.iloc[-1])
        curr_high = float(high.iloc[-1])
        curr_low = float(low.iloc[-1])
        prior_high = float(high.iloc[-2]) if len(df) >= 2 else curr_high
        prior_low = float(low.iloc[-2]) if len(df) >= 2 else curr_low

        ema9 = float(compute_ema(close, 9).iloc[-1])
        ema21 = float(compute_ema(close, 21).iloc[-1])
        ema50 = float(compute_ema(close, 50).iloc[-1])

        avwap_series = compute_avwap(df)
        curr_avwap = float(avwap_series.iloc[-1]) if not np.isnan(avwap_series.iloc[-1]) else ema21

        piv_highs, _ = detect_swing_pivots(df.iloc[-40:], left=2, right=2)
        breakout_pivot = None
        for _, p_price in reversed(piv_highs):
            if p_price <= curr_close * 1.02 and p_price >= ema50 * 0.95:
                breakout_pivot = p_price
                break

        recent_gaps = detect_recent_gaps(df, lookback=25)
        active_gap = recent_gaps[-1] if recent_gaps else None

        candidates_top = [ema9, curr_close * 1.005]
        if breakout_pivot and breakout_pivot <= curr_close * 1.01:
            candidates_top.append(breakout_pivot)
        zone_top = max(min(candidates_top), ema21)

        candidates_bot = [ema21, curr_avwap]
        if breakout_pivot and breakout_pivot <= ema21:
            candidates_bot.append(breakout_pivot)
        zone_bottom = min(candidates_bot)
        if zone_bottom > zone_top:
            zone_bottom = ema21 * 0.99

        return {
            "ema9": round(ema9, 2),
            "ema21": round(ema21, 2),
            "ema50": round(ema50, 2),
            "avwap": round(curr_avwap, 2),
            "breakout_pivot": round(breakout_pivot, 2) if breakout_pivot else None,
            "gap": active_gap,
            "zone_top": round(zone_top, 2),
            "zone_bottom": round(zone_bottom, 2),
            "prior_high": round(prior_high, 2),
            "prior_low": round(prior_low, 2),
            "curr_low": round(curr_low, 2),
            "curr_high": round(curr_high, 2),
            "curr_close": round(curr_close, 2),
        }

    def check_first_retest(self, df: pd.DataFrame) -> Tuple[bool, int]:
        """Check if current pullback is the first retest within 1-6 bars after high."""
        if len(df) < 25:
            return False, 0
        highs = df["High"].iloc[-25:]
        highest_idx = int(np.argmax(highs.values))
        bars_since_high = len(highs) - 1 - highest_idx
        return 1 <= bars_since_high <= 7, bars_since_high

    def evaluate_entry_trigger(self, df: pd.DataFrame) -> Dict:
        """Evaluate full Step [2/4] entry trigger."""
        support_info = self.calculate_confluence_support(df)
        is_first_retest, bars_since_high = self.check_first_retest(df)

        curr_close = support_info["curr_close"]
        curr_high = support_info["curr_high"]
        curr_low = support_info["curr_low"]
        prior_high = support_info["prior_high"]

        zone_top = support_info["zone_top"]
        zone_bottom = support_info["zone_bottom"]

        # Support zone test: price must actively hold support, not slice down through it
        tested_support = (curr_low <= zone_top * 1.015) and (curr_close >= zone_bottom * 0.995)
        in_pullback_zone = tested_support or (abs(curr_close - zone_top) / zone_top <= 0.02 and curr_close >= zone_bottom * 0.995)

        # Candlestick anatomy analysis
        curr_open = float(df["Open"].iloc[-1]) if "Open" in df.columns else curr_close
        body = abs(curr_close - curr_open)
        upper_wick = curr_high - max(curr_close, curr_open)
        lower_wick = min(curr_close, curr_open) - curr_low

        is_green = curr_close > curr_open
        hammer = (lower_wick >= 2.0 * max(body, 0.02)) or (
            (lower_wick >= 1.5 * max(body, 0.02)) and (upper_wick <= 1.0 * max(body, 0.02))
        )
        bounce_e9 = curr_close > support_info["ema9"] and curr_close > prior_high * 0.995
        is_shooting_star = (upper_wick > 2.0 * max(body, 0.02)) and (lower_wick <= 0.5 * upper_wick)

        # Require bullish confirmation and strictly reject shooting stars / bull traps
        has_candle_confirmation = (is_green or hammer or bounce_e9) and not is_shooting_star
        trigger_fired = ((curr_high > prior_high) or (curr_close > prior_high)) and has_candle_confirmation

        if in_pullback_zone and trigger_fired:
            status = "BUY_TRIGGERED"
            action = "BUY_NOW"
        elif in_pullback_zone:
            status = "IN_PULLBACK_ZONE"
            action = "WATCH_TRIGGER"
        elif is_first_retest:
            status = "FIRST_RETEST_WAIT"
            action = "WAIT_SUPPORT"
        else:
            status = "TRENDING_OR_BASE"
            action = "MONITOR"

        return {
            **support_info,
            "is_first_retest": is_first_retest,
            "bars_since_high": bars_since_high,
            "in_pullback_zone": in_pullback_zone,
            "trigger_fired": trigger_fired,
            "has_candle_confirmation": has_candle_confirmation,
            "is_shooting_star": is_shooting_star,
            "is_green": is_green,
            "hammer": hammer,
            "bounce_e9": bounce_e9,
            "status": status,
            "action": action,
            "trigger_price": prior_high,
        }

