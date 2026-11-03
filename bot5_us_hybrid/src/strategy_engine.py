"""
Hybrid Strategy Engine for Bot 5 (US Macro Trend Hybrid Scanner):
1. Macro Benchmark Regime Gate: SPY / QQQ > EMA 50, ^VIX <= 26.0
2. Equity Macro Filter: Bullish Trend (Close > EMA 50 > EMA 200, EMA 50 Slope >= 0.03%/bar),
   MACD > 0 & Histogram Bullish/Rising, ADX >= 20 (+DI > -DI), RSI in [40, 78],
   3M/6M Momentum >= 25%, True 20D Dollar Turnover >= $20M
3. Micro Entry: Orderly pullback to EMA 20 or EMA 50 support with <= 3.0% climax extension ceiling
4. Candlestick Confirmation: Bullish reversal candle closing in top 55% of daily range (range_location >= 0.45),
   rejecting red distribution candles and shooting stars.
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
)


@dataclass
class HybridSignal:
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
    volume_20d: float
    atr: float = 0.0
    rsi: float = 50.0
    adx: float = 25.0
    rvol: float = 1.0
    ema50_slope_pct: float = 0.0


class USHybridEngine:
    def __init__(self, config: Dict):
        self.config = config
        vol_cfg = config.get("volume_parameters", {})
        trend_cfg = config.get("trend_parameters", {})
        mom_cfg = config.get("momentum_parameters", {})
        reg_cfg = config.get("regime_parameters", {})
        ent_cfg = config.get("entry_filters", {})
        macro_cfg = config.get("macro_regime_filter", {})

        self.min_perf = float(vol_cfg.get("min_perf_3m_or_6m_pct", config.get("min_perf_3m_or_6m_pct", 25.0)))
        self.min_vol = float(vol_cfg.get("min_volume_20d", config.get("min_volume_20d", 500000.0)))
        self.min_dollar_vol = float(vol_cfg.get("min_dollar_volume_20d", config.get("min_dollar_volume_20d", 20000000.0)))
        self.require_rvol_surge = bool(vol_cfg.get("require_reversal_volume_surge", False))
        self.min_reversal_rvol = float(vol_cfg.get("min_reversal_rvol", 1.0))

        self.min_ema50_slope = float(trend_cfg.get("min_ema50_slope_pct", config.get("min_ema50_slope_pct", 0.0)))
        self.macd_req_hist = bool(mom_cfg.get("macd_require_hist_bullish", config.get("macd_require_hist_bullish", True)))
        self.rsi_period = int(mom_cfg.get("rsi_period", 14))
        self.rsi_min = float(mom_cfg.get("rsi_min_bull_support", 40.0))
        self.rsi_max = float(mom_cfg.get("rsi_max_overbought", 78.0))

        self.adx_period = int(reg_cfg.get("adx_period", 14))
        self.min_adx = float(reg_cfg.get("min_adx_trend_strength", config.get("min_adx_trend_strength", 18.0)))
        self.min_di_spread = float(reg_cfg.get("min_di_spread", 0.0))
        self.max_ma_squeeze_pct = float(reg_cfg.get("max_ma_spread_squeeze_pct", 0.5))

        self.min_range_loc = float(ent_cfg.get("min_range_close_location", config.get("min_range_close_location", 0.45)))
        self.max_pullback_ext_pct = float(ent_cfg.get("max_pullback_extension_pct", config.get("max_pullback_extension_pct", 3.0)))
        self.reject_red_candles = bool(ent_cfg.get("reject_red_distribution_candles", config.get("reject_red_distribution_candles", True)))

        self.max_vix_allowed = float(macro_cfg.get("max_vix_allowed", 26.0))

    def evaluate_macro_regime(
        self,
        spy_df: Optional[pd.DataFrame],
        qqq_df: Optional[pd.DataFrame] = None,
        vix_df: Optional[pd.DataFrame] = None,
    ) -> dict:
        """
        Evaluates broad US market macro regime using SPY, QQQ, and ^VIX.
        Returns dict with allow_new_entries, regime_label, and reason.
        """
        if spy_df is None or len(spy_df) < 50:
            return {"allow_new_entries": False, "regime_label": "RISK_OFF", "reason": "Insufficient SPY benchmark data"}

        spy_close = spy_df["Close"]
        spy_curr = float(spy_close.iloc[-1])
        spy_e20 = float(compute_ema(spy_close, 20).iloc[-1])
        spy_e50 = float(compute_ema(spy_close, 50).iloc[-1])
        spy_e200 = float(compute_ema(spy_close, 200).iloc[-1])

        if spy_curr <= spy_e200 or spy_curr <= spy_e50 or spy_e20 < spy_e50 * 0.995:
            return {
                "allow_new_entries": False,
                "regime_label": "RISK_OFF",
                "reason": f"DEFENSIVE: SPY (${spy_curr:.2f}) below EMA50/200 (${spy_e50:.2f}/${spy_e200:.2f})",
            }

        if qqq_df is not None and len(qqq_df) >= 50:
            qqq_close = qqq_df["Close"]
            qqq_curr = float(qqq_close.iloc[-1])
            qqq_e50 = float(compute_ema(qqq_close, 50).iloc[-1])
            if qqq_curr <= qqq_e50:
                return {
                    "allow_new_entries": False,
                    "regime_label": "RISK_OFF",
                    "reason": f"DEFENSIVE: QQQ (${qqq_curr:.2f}) below EMA50 (${qqq_e50:.2f})",
                }

        if vix_df is not None and len(vix_df) >= 20:
            vix_close = vix_df["Close"]
            vix_curr = float(vix_close.iloc[-1])
            vix_sma20 = float(vix_close.rolling(20, min_periods=5).mean().iloc[-1])
            if vix_curr > self.max_vix_allowed or vix_curr > vix_sma20 * 1.20:
                return {
                    "allow_new_entries": False,
                    "regime_label": "RISK_OFF",
                    "reason": f"DEFENSIVE: ^VIX ({vix_curr:.2f}) exceeds safety threshold ({self.max_vix_allowed})",
                }

        return {
            "allow_new_entries": True,
            "regime_label": "RISK_ON",
            "reason": f"BULLISH: SPY (${spy_curr:.2f}) > EMA50 (${spy_e50:.2f})",
        }

    def evaluate_ticker(self, ticker: str, df: pd.DataFrame) -> Optional[HybridSignal]:
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
        true_dollar_vol_20d = float((close * vol).rolling(20, min_periods=5).mean().iloc[-1])
        rvol = float(vol.iloc[-1]) / vol_20d if vol_20d > 0 else 1.0
        has_liquidity = (vol_20d >= self.min_vol) and (true_dollar_vol_20d >= self.min_dollar_vol)

        if self.require_rvol_surge and rvol < self.min_reversal_rvol:
            return None

        if not (is_uptrend and macd_bull and rsi_ok and adx_ok and ma_spread_ok and has_momentum and has_liquidity):
            return None

        # -------------------------------------------------------------
        # Step 2: Micro Pullback to EMA 20 or EMA 50 (with Climax Extension Ceiling)
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
            (lower_wick >= 2.0 * max(body, 0.05))
            and (upper_wick <= 0.5 * max(body, 0.05))
            and (range_location >= 0.45)
        )
        hammer = (
            (lower_wick >= 1.5 * max(body, 0.05))
            and (upper_wick <= 1.0 * max(body, 0.05))
            and (is_green or strict_hammer)
        )
        bounce_e9 = is_green and (curr_close > e9) and (curr_close > prior_close)
        is_shooting_star = (upper_wick >= 2.0 * max(body, 0.05)) and (lower_wick <= 0.5 * upper_wick)

        if is_shooting_star:
            return None

        if self.reject_red_candles and not is_green and not strict_hammer:
            return None

        if not (is_green or hammer or bounce_e9):
            return None

        reversal_type = "Hammer / Bullish Rejection" if hammer else "Bullish Candle off EMA Support"
        dist_ema50 = ((curr_close - e50) / e50) * 100.0

        return HybridSignal(
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
            volume_20d=round(vol_20d, 0),
            atr=round(curr_atr, 2),
            rsi=round(curr_rsi, 1),
            adx=round(curr_adx, 1),
            rvol=round(rvol, 2),
            ema50_slope_pct=round(ema50_slope, 3),
        )
