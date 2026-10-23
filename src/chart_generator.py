"""
Generates a 3-pane TradingView-style dark-mode chart image for a stock:
- Pane 1: Candlesticks + EMA 9 (Yellow) + EMA 21 (Blue) + BUY/SELL Signal markers
- Pane 2: ChrisMoody MACD (Green/Red MACD line, Yellow Signal line, 4-Color Histogram, Green/Red Dots)
- Pane 3: ll21LAMBO21 KDJ (%K Blue, %D Orange, %J Pink/White + Green/Red Background Bands)
"""

import os
from typing import List
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from src.strategy_engine import BarState


def generate_stock_chart(
    ticker: str,
    df: pd.DataFrame,
    states: List[BarState],
    output_path: str,
    lookback_bars: int = 90,
) -> str:
    """
    Renders a 3-pane TradingView-style chart for the last `lookback_bars` bars
    and saves it to `output_path`.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    sub_df = df.tail(lookback_bars).copy()
    sub_states = states[-len(sub_df):]
    n = len(sub_df)
    x = np.arange(n)
    dates = [
        idx.strftime("%d %b '%y") if hasattr(idx, "strftime") else str(idx)
        for idx in sub_df.index
    ]

    bg_color = "#131722"
    panel_color = "#131722"
    grid_color = "#2a2e39"
    text_color = "#d1d4dc"

    fig = plt.figure(figsize=(14, 9), facecolor=bg_color)
    gs = fig.add_gridspec(3, 1, height_ratios=[3.2, 1.4, 1.4], hspace=0.08)

    ax_price = fig.add_subplot(gs[0], facecolor=panel_color)
    ax_macd = fig.add_subplot(gs[1], facecolor=panel_color, sharex=ax_price)
    ax_kdj = fig.add_subplot(gs[2], facecolor=panel_color, sharex=ax_price)

    for ax in (ax_price, ax_macd, ax_kdj):
        ax.grid(True, color=grid_color, linestyle="--", linewidth=0.5, alpha=0.6)
        ax.tick_params(colors=text_color, labelsize=8)
        ax.yaxis.tick_right()
        for spine in ax.spines.values():
            spine.set_color(grid_color)

    # ---------------------------------------------------------
    # PANE 1: Candlesticks + EMA 9 (Yellow) + EMA 21 (Blue)
    # ---------------------------------------------------------
    opens = sub_df["Open"].to_numpy(dtype=float)
    highs = sub_df["High"].to_numpy(dtype=float)
    lows = sub_df["Low"].to_numpy(dtype=float)
    closes = sub_df["Close"].to_numpy(dtype=float)

    width = 0.62
    for i in range(n):
        is_up = closes[i] >= opens[i]
        c_color = "#26a69a" if is_up else "#ef5350"
        ax_price.plot([x[i], x[i]], [lows[i], highs[i]], color=c_color, linewidth=1.0, zorder=2)
        body_bottom = min(opens[i], closes[i])
        body_height = max(abs(closes[i] - opens[i]), (highs[i] - lows[i]) * 0.015)
        rect = Rectangle(
            (x[i] - width / 2, body_bottom),
            width,
            body_height,
            facecolor=c_color,
            edgecolor=c_color,
            zorder=3,
        )
        ax_price.add_patch(rect)

    ema9 = sub_df["ema_fast"].to_numpy(dtype=float)
    ema21 = sub_df["ema_slow"].to_numpy(dtype=float)
    ax_price.plot(x, ema9, color="#ffeb3b", linewidth=1.5, label=f"EMA 9 ({ema9[-1]:.2f})", zorder=4)
    ax_price.plot(x, ema21, color="#2962ff", linewidth=1.5, label=f"EMA 21 ({ema21[-1]:.2f})", zorder=4)

    # Mark BUY_NOW / SELL_NOW / EMA Cross events on the price chart
    price_span = max(np.nanmax(highs) - np.nanmin(lows), 1.0)
    for i, st in enumerate(sub_states):
        if st.action_today == "BUY_NOW":
            ax_price.scatter(
                x[i],
                lows[i] - price_span * 0.04,
                color="#00e676",
                marker="^",
                s=110,
                zorder=6,
            )
            ax_price.annotate(
                "BUY (6/6)",
                (x[i], lows[i] - price_span * 0.055),
                color="#00e676",
                fontsize=8,
                fontweight="bold",
                ha="center",
                va="top",
            )
        elif st.action_today == "SELL_NOW":
            ax_price.scatter(
                x[i],
                highs[i] + price_span * 0.04,
                color="#ff1744",
                marker="v",
                s=110,
                zorder=6,
            )
            ax_price.annotate(
                "SELL (6/6)",
                (x[i], highs[i] + price_span * 0.055),
                color="#ff1744",
                fontsize=8,
                fontweight="bold",
                ha="center",
                va="bottom",
            )

    last_st = sub_states[-1]
    title_str = (
        f"{ticker} • 1D (NASDAQ/NYSE)   Close: ${last_st.close:.2f} ({last_st.change_pct:+.2f}%)   "
        f"Status: {last_st.side} [{last_st.bar_count}/{last_st.max_bars}]"
    )
    ax_price.set_title(title_str, color="#ffffff", fontsize=11, fontweight="bold", loc="left", pad=8)
    ax_price.legend(loc="upper left", facecolor="#1e222d", edgecolor=grid_color, labelcolor=text_color, fontsize=8)
    plt.setp(ax_price.get_xticklabels(), visible=False)

    # ---------------------------------------------------------
    # PANE 2: ChrisMoody CM_Ult_MacD_MTF (12, 26, 9)
    # ---------------------------------------------------------
    macd_vals = sub_df["macd"].to_numpy(dtype=float)
    sig_vals = sub_df["macd_signal"].to_numpy(dtype=float)
    hist_vals = sub_df["macd_hist"].to_numpy(dtype=float)
    hist_colors_raw = sub_df["macd_hist_color"].to_numpy()

    color_map = {
        "aqua": "#00bcd4",
        "blue": "#2962ff",
        "red": "#ff5252",
        "maroon": "#880e4f",
    }
    bar_colors = [color_map.get(c, "#787b86") for c in hist_colors_raw]
    ax_macd.bar(x, hist_vals, width=0.6, color=bar_colors, alpha=0.85, zorder=2)
    ax_macd.axhline(0, color="#787b86", linewidth=0.8, zorder=1)

    # Color segments for MACD line (Green when >= Signal, Red when < Signal)
    for i in range(1, n):
        seg_color = "#00e676" if macd_vals[i] >= sig_vals[i] else "#ff5252"
        ax_macd.plot([x[i - 1], x[i]], [macd_vals[i - 1], macd_vals[i]], color=seg_color, linewidth=1.8, zorder=4)
    ax_macd.plot(x, sig_vals, color="#ffeb3b", linewidth=1.2, label="Signal SMA(9)", zorder=3)

    # Green & Red Crossover Dots
    green_dots = sub_df["macd_green_dot"].to_numpy(dtype=bool)
    red_dots = sub_df["macd_red_dot"].to_numpy(dtype=bool)
    for i in range(n):
        if green_dots[i]:
            ax_macd.scatter(x[i], macd_vals[i], color="#00e676", edgecolors="#131722", s=55, zorder=6)
        elif red_dots[i]:
            ax_macd.scatter(x[i], macd_vals[i], color="#ff1744", edgecolors="#131722", s=55, zorder=6)

    ax_macd.text(
        0.01,
        0.88,
        f"CM_Ult_MacD_MTF (12, 26, 9)   MACD: {macd_vals[-1]:.2f}   Signal: {sig_vals[-1]:.2f}",
        transform=ax_macd.transAxes,
        color=text_color,
        fontsize=8,
        fontweight="bold",
    )
    plt.setp(ax_macd.get_xticklabels(), visible=False)

    # ---------------------------------------------------------
    # PANE 3: KDJ (9, 3) by ll21LAMBO21 with Green/Red Background
    # ---------------------------------------------------------
    kdj_k = sub_df["kdj_k"].to_numpy(dtype=float)
    kdj_d = sub_df["kdj_d"].to_numpy(dtype=float)
    kdj_j = sub_df["kdj_j"].to_numpy(dtype=float)
    kdj_green = sub_df["kdj_green"].to_numpy(dtype=bool)

    for i in range(n):
        bg_band = "#1b5e20" if kdj_green[i] else "#b71c1c"
        ax_kdj.axvspan(x[i] - 0.5, x[i] + 0.5, color=bg_band, alpha=0.35, zorder=1)

    ax_kdj.axhline(80, color="#787b86", linestyle=":", linewidth=0.7, zorder=2)
    ax_kdj.axhline(20, color="#787b86", linestyle=":", linewidth=0.7, zorder=2)
    ax_kdj.plot(x, kdj_k, color="#2962ff", linewidth=1.2, label="%K", zorder=3)
    ax_kdj.plot(x, kdj_d, color="#ff9800", linewidth=1.2, label="%D", zorder=3)
    ax_kdj.plot(x, kdj_j, color="#e040fb", linewidth=1.1, alpha=0.9, label="%J", zorder=4)

    ax_kdj.text(
        0.01,
        0.88,
        f"KDJ (9, 3) ll21LAMBO21   K: {kdj_k[-1]:.2f}   D: {kdj_d[-1]:.2f}   J: {kdj_j[-1]:.2f}   "
        f"[{'GREEN' if kdj_green[-1] else 'RED'}]",
        transform=ax_kdj.transAxes,
        color=text_color,
        fontsize=8,
        fontweight="bold",
    )

    step = max(1, n // 10)
    tick_indices = list(range(0, n, step))
    ax_kdj.set_xticks(tick_indices)
    ax_kdj.set_xticklabels([dates[i] for i in tick_indices], color=text_color, fontsize=8)
    ax_kdj.set_xlim(-1, n)

    plt.savefig(output_path, dpi=140, bbox_inches="tight", facecolor=bg_color)
    plt.close(fig)
    return output_path
