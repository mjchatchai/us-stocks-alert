"""
Chart Generator for Bot 4 (Thai Stocks SET)
Generates high-contrast candlestick charts with:
- EMAs (9, 21, 50) & AVWAP
- Shaded Support Confluence Zone
- Entry, Stop Loss, 3R, 5R Targets clearly annotated
- Volume & 20D Turnover (Baht)
"""

import os
from typing import Dict, Optional
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .indicators import compute_ema, compute_avwap


def generate_pullback_chart(
    ticker: str,
    df: pd.DataFrame,
    setup_info: Optional[Dict] = None,
    trade_plan: Optional[object] = None,
    output_dir: str = "bot5_thai_hybrid/docs/charts",
    lookback_bars: int = 80,
) -> Optional[str]:
    """Generate and save chart for a Thai stock."""
    try:
        os.makedirs(output_dir, exist_ok=True)
        sub_df = df.iloc[-lookback_bars:].copy()
        if len(sub_df) < 20:
            return None

        clean_tk = ticker.replace(".BK", "").upper()
        close = sub_df["Close"]
        ema9 = compute_ema(close, 9)
        ema21 = compute_ema(close, 21)
        ema50 = compute_ema(close, 50)
        avwap = compute_avwap(sub_df)

        plt.style.use("dark_background")
        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(12, 7), gridspec_kw={"height_ratios": [3, 1]}, sharex=True
        )
        fig.patch.set_facecolor("#0e1117")
        ax1.set_facecolor("#161b22")
        ax2.set_facecolor("#161b22")

        dates = [pd.to_datetime(d) for d in sub_df.index]
        x_indices = np.arange(len(dates))
        width = 0.6
        up = sub_df["Close"] >= sub_df["Open"]
        down = sub_df["Close"] < sub_df["Open"]

        # Green (Up) candles
        ax1.bar(
            x_indices[up],
            sub_df["Close"][up] - sub_df["Open"][up],
            width,
            bottom=sub_df["Open"][up],
            color="#26a69a",
            alpha=0.9,
        )
        ax1.vlines(
            x_indices[up],
            sub_df["Low"][up],
            sub_df["High"][up],
            color="#26a69a",
            linewidth=1.2,
        )

        # Red (Down) candles
        ax1.bar(
            x_indices[down],
            sub_df["Open"][down] - sub_df["Close"][down],
            width,
            bottom=sub_df["Close"][down],
            color="#ef5350",
            alpha=0.9,
        )
        ax1.vlines(
            x_indices[down],
            sub_df["Low"][down],
            sub_df["High"][down],
            color="#ef5350",
            linewidth=1.2,
        )

        ax1.plot(x_indices, ema9, label="EMA 9", color="#00bcd4", linewidth=1.5)
        ax1.plot(x_indices, ema21, label="EMA 21", color="#ff9800", linewidth=1.5)
        ax1.plot(x_indices, ema50, label="EMA 50", color="#e040fb", linewidth=1.3)
        if not avwap.isna().all():
            ax1.plot(x_indices, avwap, label="AVWAP", color="#ffeb3b", linewidth=1.5, linestyle=":")

        if setup_info:
            z_top = setup_info.get("zone_top")
            z_bot = setup_info.get("zone_bottom")
            if z_top and z_bot:
                ax1.axhspan(
                    z_bot,
                    z_top,
                    color="#00e676",
                    alpha=0.15,
                    label=f"Support Zone ({z_bot:.2f}-{z_top:.2f} ฿)",
                )

        if trade_plan:
            entry = getattr(trade_plan, "entry_price", None)
            sl = getattr(trade_plan, "stop_loss", None)
            t3r = getattr(trade_plan, "target_3r", None)
            t5r = getattr(trade_plan, "target_5r", None)

            if sl:
                ax1.axhline(sl, color="#ff5252", linestyle="--", linewidth=1.5, label=f"Stop Loss: {sl:.2f} ฿")
            if entry:
                ax1.axhline(entry, color="#69f0ae", linestyle="--", linewidth=1.5, label=f"Entry: {entry:.2f} ฿")
            if t3r:
                ax1.axhline(t3r, color="#ffd700", linestyle="--", linewidth=1.5, label=f"Target 3R: {t3r:.2f} ฿")
            if t5r:
                ax1.axhline(t5r, color="#00e676", linestyle="--", linewidth=1.5, label=f"Target 5R: {t5r:.2f} ฿")

        latest_c = float(sub_df["Close"].iloc[-1])
        pct_chg = float(((sub_df["Close"].iloc[-1] / sub_df["Close"].iloc[-2]) - 1.0) * 100.0) if len(sub_df) >= 2 else 0.0
        sign = "+" if pct_chg >= 0 else ""
        ax1.set_title(
            f"{clean_tk} (SET) | Price: {latest_c:.2f} ฿ ({sign}{pct_chg:.2f}%) | Bot 4 Thai Pullback Engine",
            fontsize=13,
            fontweight="bold",
            color="#ffffff",
            pad=10,
        )
        ax1.grid(True, linestyle="--", alpha=0.2, color="#757575")
        ax1.legend(loc="upper left", fontsize=8.5, facecolor="#1e222d", edgecolor="#424242")

        vol_colors = ["#26a69a" if u else "#ef5350" for u in up]
        ax2.bar(x_indices, sub_df["Volume"], color=vol_colors, alpha=0.7, width=width)
        vol_sma20 = sub_df["Volume"].rolling(20).mean()
        ax2.plot(x_indices, vol_sma20, color="#ffffff", linewidth=1.0, label="Vol SMA 20")
        ax2.set_ylabel("Volume", fontsize=9, color="#b0bec5")
        ax2.grid(True, linestyle="--", alpha=0.15, color="#757575")

        step = max(1, len(x_indices) // 8)
        ax2.set_xticks(x_indices[::step])
        ax2.set_xticklabels([d.strftime("%b %d") for d in dates[::step]], rotation=0, fontsize=8.5)

        plt.tight_layout()
        filepath = os.path.join(output_dir, f"{clean_tk}.png")
        plt.savefig(filepath, dpi=130, facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)

        return filepath
    except Exception as e:
        print(f"Error generating chart for {ticker}: {e}")
        return None
