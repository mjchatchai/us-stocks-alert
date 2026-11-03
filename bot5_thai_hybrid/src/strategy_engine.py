"""
Hybrid Strategy Engine for Bot 6 (Thai SET Hybrid Trend Scanner):
1. Macro Benchmark Regime Gate: ^SET.BK / ^SET50.BK > EMA 50
2. Equity Macro Filter: Bullish Trend (Close > EMA 50 > EMA 200, EMA 50 Slope >= 0.025%/bar),
   MACD > 0 & Histogram Bullish/Rising, ADX >= 18 (+DI > -DI), RSI in [38, 75],
   3M/6M Momentum >= 15%, True 20D Turnover >= 20M THB
3. Micro Entry: Orderly pullback to EMA 20 or EMA 50 support with <= 3.0% climax extension ceiling
4. Candlestick Confirmation: Bullish reversal candle closing in top 55% of daily range (range_location >= 0.45),
   rejecting red distribution candles and shooting stars, with SET tick snapping.
"""
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import pandas as pd
from .indicators import (
    compute_ema,
    compute_ema_slope_pct,
    compute_macd,
    compute_atr_wilder,
    compute_rsi,
    compute_adx,
    round_to_set_tick,
)


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
    atr: float = 0.0
    rsi: float = 50.0
    adx: float = 25.0
    rvol: float = 1.0
    ema50_slope_pct: float = 0.0


class ThaiHybridEngine:
    def __init__(self, config: Dict):
        self.config = config
        vol_cfg = config.get("volume_parameters", {})
        trend_cfg = config.get("trend_parameters", {})
        mom_cfg = config.get("momentum_parameters", {})
        reg_cfg = config.get("regime_parameters", {})
        ent_cfg = config.get("entry_filters", {})

        self.min_perf = float(vol_cfg.get("min_perf_3m_or_6m_pct", config.get("min_perf_3m_or_6m_pct", 15.0)))
        self.min_turnover = float(
            vol_cfg.get(
                "min_turnover_20d",
                vol_cfg.get("min_dollar_volume_20d", config.get("min_dollar_volume_20d", 20000000.0)),
            )
        )
        self.require_rvol_surge = bool(vol_cfg.get("require_reversal_volume_surge", False))
        self.min_reversal_rvol = float(vol_cfg.get("min_reversal_rvol", 1.0))

        self.min_ema50_slope = float(trend_cfg.get("min_ema50_slope_pct", config.get("min_ema50_slope_pct", 0.0)))
        self.macd_req_hist = bool(mom_cfg.get("macd_require_hist_bullish", config.get("macd_require_hist_bullish", True)))
        self.rsi_period = int(mom_cfg.get("rsi_period", 14))
        self.rsi_min = float(mom_cfg.get("rsi_min_bull_support", 38.0))
        self.rsi_max = float(mom_cfg.get("rsi_max_overbought", 75.0))

        self.adx_period = int(reg_cfg.get("adx_period", 14))
        self.min_adx = float(reg_cfg.get("min_adx_trend_strength", config.get("min_adx_trend_strength", 18.0)))
        self.min_di_spread = float(reg_cfg.get("min_di_spread", 0.0))
        self.max_ma_squeeze_pct = float(reg_cfg.get("max_ma_spread_squeeze_pct", 0.5))

        self.min_range_loc = float(ent_cfg.get("min_range_close_location", config.get("min_range_close_location", 0.45)))
        self.max_pullback_ext_pct = float(ent_cfg.get("max_pullback_extension_pct", config.get("max_pullback_extension_pct", 3.0)))
        self.reject_red_candles = bool(ent_cfg.get("reject_red_distribution_candles", config.get("reject_red_distribution_candles", True)))

    def evaluate_macro_regime(
        self,
        set_df: Optional[pd.DataFrame],
        set50_df: Optional[pd.DataFrame] = None,
    ) -> dict:
        """
        Evaluates Thai SET Index macro regime using ^SET.BK (and optional ^SET50.BK).
        Returns dict with allow_new_entries, regime_label, and reason.
        """
        if set_df is None or len(set_df) < 50:
            return {"allow_new_entries": False, "regime_label": "RISK_OFF", "reason": "Insufficient ^SET.BK benchmark data"}

        set_close = set_df["Close"]
        set_curr = float(set_close.iloc[-1])
        set_e20 = float(compute_ema(set_close, 20).iloc[-1])
        set_e50 = float(compute_ema(set_close, 50).iloc[-1])
        macd_line, _, _ = compute_macd(set_close)
        m_curr = float(macd_line.iloc[-1])

        if set_curr <= set_e50 and m_curr <= 0:
            return {
                "allow_new_entries": False,
                "regime_label": "RISK_OFF",
                "reason": f"DEFENSIVE: ^SET.BK ({set_curr:,.2f}) below EMA50 ({set_e50:,.2f}) & MACD <= 0",
            }

        if set50_df is not None and len(set50_df) >= 50:
            s50_close = set50_df["Close"]
            s50_curr = float(s50_close.iloc[-1])
            s50_e50 = float(compute_ema(s50_close, 50).iloc[-1])
            if s50_curr <= s50_e50 and m_curr <= 0:
                return {
                    "allow_new_entries": False,
                    "regime_label": "RISK_OFF",
                    "reason": f"DEFENSIVE: ^SET50.BK ({s50_curr:,.2f}) below EMA50 ({s50_e50:,.2f})",
                }

        return {
            "allow_new_entries": True,
            "regime_label": "RISK_ON",
            "reason": f"BULLISH: ^SET.BK ({set_curr:,.2f}) > EMA50 ({set_e50:,.2f}) or MACD > 0",
        }

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
        ema50_slope = compute_ema_slope_pct(ema50, lookback=5)

        macd_line, _, hist = compute_macd(close)
        m_val = float(macd_line.iloc[-1])
        h_curr = float(hist.iloc[-1])
        h_prev = float(hist.iloc[-2]) if len(hist) >= 2 else h_curr

        atr_series = compute_atr_wilder(high, low, close, period=14)
        curr_atr = float(atr_series.iloc[-1])

        rsi_series = compute_rsi(close, period=self.rsi_period)
        curr_rsi = float(rsi_series.iloc[-1])

        adx_series, plus_di, minus_di = compute_adx(high, low, close, period=self.adx_period)
        curr_adx = float(adx_series.iloc[-1])
        p_di = float(plus_di.iloc[-1])
        m_di = float(minus_di.iloc[-1])

        # -------------------------------------------------------------
        # Step 1: Macro Trend, Momentum, Regime & Liquidity Filter
        # -------------------------------------------------------------
        is_uptrend = ((curr_close > e50 > e200) if e200 > 0 else (curr_close > e50)) and (
            ema50_slope >= self.min_ema50_slope
        )
        macd_bull = (m_val > 0) and (
            not self.macd_req_hist or (h_curr > 0 or h_curr >= h_prev - 1e-6)
        )
        rsi_ok = self.rsi_min <= curr_rsi <= self.rsi_max
        adx_ok = (curr_adx >= self.min_adx) and ((p_di - m_di) >= self.min_di_spread)

        ma_spread_pct = ((max(e9, e20, e50) - min(e9, e20, e50)) / e50) * 100.0 if e50 > 0 else 0.0
        ma_spread_ok = ma_spread_pct >= self.max_ma_squeeze_pct

        perf_3m = float(close.pct_change(min(63, len(close) - 1)).iloc[-1] * 100.0) if len(close) >= 30 else 0.0
        perf_6m = float(close.pct_change(min(126, len(close) - 1)).iloc[-1] * 100.0) if len(close) >= 60 else 0.0
        has_momentum = (perf_3m >= self.min_perf) or (perf_6m >= self.min_perf)

        vol_20d = float(vol.rolling(20, min_periods=5).mean().iloc[-1])
        turnover_20d = float((close * vol).rolling(20, min_periods=5).mean().iloc[-1])
        rvol = float(vol.iloc[-1]) / vol_20d if vol_20d > 0 else 1.0
        has_liquidity = turnover_20d >= self.min_turnover

        if self.require_rvol_surge and rvol < self.min_reversal_rvol:
            return None

        if not (is_uptrend and macd_bull and rsi_ok and adx_ok and ma_spread_ok and has_momentum and has_liquidity):
            return None

        # -------------------------------------------------------------
        # Step 2: Micro Pullback Test (with Climax Extension Ceiling)
        # -------------------------------------------------------------
        max_ext_mult = 1.0 + (self.max_pullback_ext_pct / 100.0)
        near_e20 = (curr_low <= e20 * 1.015) and (e20 * 0.995 <= curr_close <= e20 * max_ext_mult)
        near_e50 = (curr_low <= e50 * 1.015) and (e50 * 0.995 <= curr_close <= e50 * max_ext_mult)

        if not (near_e20 or near_e50):
            return None

        support_type = "Daily EMA 20" if near_e20 else "Daily EMA 50"
        support_level = e20 if near_e20 else e50

        # -------------------------------------------------------------
        # Step 3: Reversal Confirmation (Range Location & Red Candle Rejection)
        # -------------------------------------------------------------
        body = abs(curr_close - curr_open)
        upper_wick = curr_high - max(curr_close, curr_open)
        lower_wick = min(curr_close, curr_open) - curr_low
        hl_range = curr_high - curr_low
        range_location = (curr_close - curr_low) / hl_range if hl_range > 1e-9 else 0.5

        if range_location < self.min_range_loc:
            return None

        is_green = curr_close > curr_open
        strict_hammer = (
            (lower_wick >= 2.0 * max(body, 0.02))
            and (upper_wick <= 0.5 * max(body, 0.02))
            and (range_location >= 0.45)
        )
        hammer = (
            (lower_wick >= 1.5 * max(body, 0.02))
            and (upper_wick <= 1.0 * max(body, 0.02))
            and (is_green or strict_hammer)
        )
        bounce_e9 = is_green and (curr_close > e9) and (curr_close > prior_close)
        is_shooting_star = (upper_wick >= 2.0 * max(body, 0.02)) and (lower_wick <= 0.5 * upper_wick)

        if is_shooting_star:
            return None

        if self.reject_red_candles and not is_green and not strict_hammer:
            return None

        if not (is_green or hammer or bounce_e9):
            return None

        reversal_type = "Hammer / Tail Rejection" if hammer else "Bullish Candle off EMA Support"
        dist_ema50 = ((curr_close - e50) / e50) * 100.0

        return ThaiHybridSignal(
            ticker=ticker,
            entry_price=round_to_set_tick(curr_close, mode="nearest"),
            curr_low=round_to_set_tick(curr_low, mode="down"),
            prior_low=round_to_set_tick(prior_low, mode="down"),
            support_level=round_to_set_tick(support_level, mode="nearest"),
            support_type=support_type,
            reversal_type=reversal_type,
            dist_ema50_pct=round(dist_ema50, 1),
            perf_3m=round(perf_3m, 1),
            perf_6m=round(perf_6m, 1),
            turnover_20d=round(turnover_20d, 0),
            atr=round(curr_atr, 2),
            rsi=round(curr_rsi, 1),
            adx=round(curr_adx, 1),
            rvol=round(rvol, 2),
            ema50_slope_pct=round(ema50_slope, 3),
        )
