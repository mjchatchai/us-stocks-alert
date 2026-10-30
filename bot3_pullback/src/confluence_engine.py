"""
Confluence Support Engine & Entry Trigger for Bot 3 (Step [2/4])
- Identifies Confluence Support Zone:
  * Dynamic EMAs: 9, 21, 50
  * Anchored VWAP (AVWAP) from swing low or breakout anchor
  * Prior Highs / Breakout Pivots (S/R Flip)
  * Price Gaps (Gap Support)
- Detects "First Retest" setup after breaking out
- Evaluates Entry Trigger: Price tests support, bounces, and breaks above Prior Candle High
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from .indicators import (
    compute_ema,
    compute_avwap,
    detect_swing_pivots,
    detect_recent_gaps,
)


class ConfluenceEngine:
    def __init__(self, config: Dict):
        self.config = config

    def calculate_confluence_support(self, df: pd.DataFrame) -> Dict:
        """
        Calculate all support levels and find the Confluence Support Zone.
        """
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        curr_close = float(close.iloc[-1])
        curr_high = float(high.iloc[-1])
        curr_low = float(low.iloc[-1])
        prior_high = float(high.iloc[-2]) if len(df) >= 2 else curr_high
        prior_low = float(low.iloc[-2]) if len(df) >= 2 else curr_low

        # 1. EMAs
        ema9 = float(compute_ema(close, 9).iloc[-1])
        ema21 = float(compute_ema(close, 21).iloc[-1])
        ema50 = float(compute_ema(close, 50).iloc[-1])

        # 2. AVWAP
        avwap_series = compute_avwap(df)
        curr_avwap = float(avwap_series.iloc[-1]) if not np.isnan(avwap_series.iloc[-1]) else ema21

        # 3. Prior Resistance turned Support (Breakout Pivots)
        piv_highs, _ = detect_swing_pivots(df.iloc[-40:], left=2, right=2)
        breakout_pivot = None
        # Find highest pivot below current close (or close to current price)
        for _, p_price in reversed(piv_highs):
            if p_price <= curr_close * 1.02 and p_price >= ema50 * 0.95:
                breakout_pivot = p_price
                break

        # 4. Gaps
        recent_gaps = detect_recent_gaps(df, lookback=25)
        active_gap = recent_gaps[-1] if recent_gaps else None

        # Build list of key levels near current price
        key_levels = [
            {"name": "EMA 9", "price": round(ema9, 2), "type": "Dynamic"},
            {"name": "EMA 21", "price": round(ema21, 2), "type": "Dynamic"},
            {"name": "EMA 50", "price": round(ema50, 2), "type": "Dynamic"},
            {"name": "AVWAP", "price": round(curr_avwap, 2), "type": "Volume"},
        ]
        if breakout_pivot:
            key_levels.append(
                {"name": "Prior High (Pivot S/R)", "price": round(breakout_pivot, 2), "type": "Structure"}
            )
        if active_gap:
            key_levels.append(
                {"name": f"Gap Support ({active_gap['date']})", "price": round(active_gap["mid"], 2), "type": "Gap"}
            )

        # Primary Confluence Zone:
        # Top of zone is typically around EMA 9 or Pivot
        # Bottom of zone is around EMA 21 / AVWAP / EMA 50
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
            "key_levels": key_levels,
            "zone_top": round(zone_top, 2),
            "zone_bottom": round(zone_bottom, 2),
            "prior_high": round(prior_high, 2),
            "prior_low": round(prior_low, 2),
            "curr_low": round(curr_low, 2),
            "curr_high": round(curr_high, 2),
            "curr_close": round(curr_close, 2),
        }

    def check_first_retest(self, df: pd.DataFrame) -> Tuple[bool, int]:
        """
        Check if current pullback is the FIRST retest following a breakout to a 20-bar high.
        Returns: (is_first_retest, bars_since_high)
        """
        if len(df) < 25:
            return False, 0

        highs = df["High"].iloc[-25:]
        highest_idx = int(np.argmax(highs.values))
        bars_since_high = len(highs) - 1 - highest_idx

        # A First Retest typically occurs 1 to 6 bars after printing a swing high/breakout
        is_first_retest = 1 <= bars_since_high <= 7
        return is_first_retest, bars_since_high

    def evaluate_entry_trigger(self, df: pd.DataFrame) -> Dict:
        """
        Evaluate full Step [2/4] entry setup:
        1. Support Confluence Zone
        2. First Retest Check
        3. Price in / near support zone
        4. Trigger: Price breaks above Prior Candle High
        """
        support_info = self.calculate_confluence_support(df)
        is_first_retest, bars_since_high = self.check_first_retest(df)

        curr_close = support_info["curr_close"]
        curr_high = support_info["curr_high"]
        curr_low = support_info["curr_low"]
        prior_high = support_info["prior_high"]
        prior_low = support_info["prior_low"]

        zone_top = support_info["zone_top"]
        zone_bottom = support_info["zone_bottom"]

        # Check if price has tested or is currently within support zone
        # Tested support: Low dipped into or near zone (within 1.5% of zone_top or zone_bottom)
        tested_support = (curr_low <= zone_top * 1.015) and (curr_close >= zone_bottom * 0.98)
        in_pullback_zone = tested_support or (abs(curr_close - zone_top) / zone_top <= 0.02)

        # Trigger condition:
        # Price bounced and breaks above Prior Candle High
        trigger_fired = (curr_high > prior_high) or (curr_close > prior_high)

        # Setup status classification
        if in_pullback_zone and trigger_fired:
            status = "BUY_TRIGGERED"  # S-Tier Buy Signal!
            action = "BUY_NOW"
        elif in_pullback_zone:
            status = "IN_PULLBACK_ZONE"  # In zone, waiting for trigger break
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
            "status": status,
            "action": action,
            "trigger_price": prior_high,
        }
