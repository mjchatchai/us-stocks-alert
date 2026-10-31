"""
Screener Module for Bot 3 (Step [1/4])
- Performance Ranking: 1M, 3M, 6M returns (> 30% focus)
- Relative Strength Percentile (Top 20-30%)
- Liquidity Filtering (Volume > 500k, Dollar Vol > $5M)
- Weekly Chart Trend & Higher Lows Check
- Daily Base Building: Volatility Contraction (VCP), Higher Lows, EMA 9/21 Alignment & Slope
"""

import concurrent.futures
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import yfinance as yf

from .indicators import (
    compute_ema,
    compute_atr,
    compute_bollinger_bands,
    compute_performance_metrics,
    check_higher_lows,
    check_volatility_contraction,
    check_ema_slopes,
)


class BaseScreener:
    def __init__(self, config: Dict):
        self.config = config
        self.min_vol = config.get("min_volume_20d", 500000)
        self.min_dollar_vol = config.get("min_dollar_volume_20d", 5000000)
        self.min_perf = config.get("min_perf_3m_or_6m_pct", 30.0)
        self.top_rs_pct = config.get("top_rs_percentile", 70.0)

    def fetch_data(
        self, ticker: str, period: str = "1y"
    ) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """Fetch Daily and Weekly data for a ticker."""
        try:
            tk = yf.Ticker(ticker)
            df_daily = tk.history(period=period, interval="1d")
            if df_daily is None or len(df_daily) < 60:
                return None, None
            if hasattr(df_daily.columns, "nlevels") and df_daily.columns.nlevels > 1:
                df_daily.columns = df_daily.columns.get_level_values(0)

            df_weekly = tk.history(period=period, interval="1wk")
            if df_weekly is not None and hasattr(df_weekly.columns, "nlevels") and df_weekly.columns.nlevels > 1:
                df_weekly.columns = df_weekly.columns.get_level_values(0)
            return df_daily, df_weekly
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            return None, None

    def evaluate_candidate(
        self, ticker: str, df_daily: pd.DataFrame, df_weekly: Optional[pd.DataFrame]
    ) -> Optional[Dict]:
        """
        Evaluate single ticker against Step [1/4] criteria.
        """
        if len(df_daily) < 60:
            return None

        # 1. Performance & Volume Metrics
        perf = compute_performance_metrics(df_daily)
        vol_20 = perf.get("vol_20", 0)
        dollar_vol_20 = perf.get("dollar_vol_20", 0)
        ret_1m = perf.get("ret_1m", 0)
        ret_3m = perf.get("ret_3m", 0)
        ret_6m = perf.get("ret_6m", 0)

        # Liquidity check: must satisfy both volume and dollar volume
        if vol_20 < self.min_vol or dollar_vol_20 < self.min_dollar_vol:
            return None

        # Momentum check: 3M or 6M > min_perf (e.g. 30%)
        max_perf = max(ret_3m, ret_6m)
        has_strong_momentum = max_perf >= self.min_perf

        # 2. Daily EMAs & Slope
        close = df_daily["Close"]
        ema9 = compute_ema(close, 9)
        ema21 = compute_ema(close, 21)
        ema50 = compute_ema(close, 50)
        curr_close = float(close.iloc[-1])
        curr_ema9 = float(ema9.iloc[-1])
        curr_ema21 = float(ema21.iloc[-1])
        curr_ema50 = float(ema50.iloc[-1])

        # Price standing above EMA 9 and EMA 21
        price_above_ema9_21 = (curr_close >= curr_ema9 * 0.99) and (
            curr_close >= curr_ema21 * 0.99
        )
        fast_up, slow_up, f_slope, s_slope = check_ema_slopes(ema9, ema21, lookback=5)
        ema_flattening_or_up = fast_up or slow_up

        # 3. Base Building: Higher Lows & Volatility Contraction
        hl_ok, rec_low, prior_low = check_higher_lows(df_daily, lookback=40)
        vcp_ok, vcp_ratio, bb_width = check_volatility_contraction(df_daily)

        # 4. Weekly Chart Check
        weekly_ok = True
        if df_weekly is not None and len(df_weekly) >= 20:
            w_close = df_weekly["Close"]
            w_ema10 = compute_ema(w_close, 10).iloc[-1]
            w_curr = float(w_close.iloc[-1])
            weekly_ok = w_curr >= w_ema10 * 0.97  # Trend is intact in weekly view

        # Calculate a combined Base & Momentum Score (0-100)
        # Weighted score based on returns and base tightness
        raw_score = (
            (ret_1m * 0.2)
            + (ret_3m * 0.4)
            + (ret_6m * 0.4)
            + (10.0 if hl_ok else 0.0)
            + (10.0 if vcp_ok else 0.0)
            + (10.0 if price_above_ema9_21 else 0.0)
            + (10.0 if weekly_ok else 0.0)
        )

        return {
            "ticker": ticker,
            "close": round(curr_close, 2),
            "ret_1m": ret_1m,
            "ret_3m": ret_3m,
            "ret_6m": ret_6m,
            "max_perf": max_perf,
            "has_strong_momentum": has_strong_momentum,
            "vol_20": vol_20,
            "dollar_vol_20": dollar_vol_20,
            "ema9": round(curr_ema9, 2),
            "ema21": round(curr_ema21, 2),
            "ema50": round(curr_ema50, 2),
            "price_above_ema9_21": price_above_ema9_21,
            "ema_flattening_or_up": ema_flattening_or_up,
            "f_slope": f_slope,
            "s_slope": s_slope,
            "higher_low_ok": hl_ok,
            "recent_low": round(rec_low, 2) if rec_low else None,
            "prior_low": round(prior_low, 2) if prior_low else None,
            "vcp_ok": vcp_ok,
            "vcp_ratio": vcp_ratio,
            "bb_width": bb_width,
            "weekly_ok": weekly_ok,
            "raw_score": raw_score,
            "df_daily": df_daily,
        }

    def scan_universe(self, tickers: List[str]) -> List[Dict]:
        """
        Scan full list of tickers using multi-threading for high performance,
        rank by RS Percentile, and filter Top candidates.
        """
        results = []
        total = len(tickers)
        print(f"Scanning {total} tickers for Step [1/4] Strong Base Candidates (Multi-threaded)...")

        def _worker(tk: str):
            try:
                df_daily, df_weekly = self.fetch_data(tk)
                if df_daily is not None:
                    return self.evaluate_candidate(tk, df_daily, df_weekly)
            except Exception:
                pass
            return None

        # Fetch up to 12 workers concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            future_to_tk = {executor.submit(_worker, tk): tk for tk in tickers}
            done_count = 0
            for future in concurrent.futures.as_completed(future_to_tk):
                cand = future.result()
                done_count += 1
                if done_count % 50 == 0 or done_count == total:
                    print(f"  -> Progress: {done_count}/{total} tickers evaluated...")
                if cand is not None:
                    results.append(cand)

        if not results:
            return []

        # Calculate Relative Strength (RS) Percentile Rank across screened results
        scores = [r["raw_score"] for r in results]
        p_ranks = pd.Series(scores).rank(pct=True) * 100.0

        for idx, r in enumerate(results):
            r["rs_percentile"] = round(float(p_ranks.iloc[idx]), 1)
            # Qualifies Step 1/4 if:
            # - Has strong momentum (> 30% in 3M/6M) OR top RS percentile >= top_rs_pct
            # - AND price above EMA 9/21 with flat/up slope
            # - AND weekly intact
            r["step1_passed"] = (
                (r["has_strong_momentum"] or r["rs_percentile"] >= self.top_rs_pct)
                and r["price_above_ema9_21"]
                and r["ema_flattening_or_up"]
                and r["weekly_ok"]
            )

        # Sort descending by RS Percentile & Score
        results.sort(key=lambda x: x["rs_percentile"], reverse=True)
        return results
