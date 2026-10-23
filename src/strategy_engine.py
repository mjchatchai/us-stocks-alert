"""
6-Button Sequential Strategy Engine (6 Distinct Stages + Progressive Color Takeover)

ความหมายของเม็ดกระดุมทั้ง 6 เม็ด (แยกแต่ละจังหวะออกจากกันชัดเจน):
  1 เม็ด (🟢🔴🔴🔴🔴🔴): KDJ เปลี่ยนเป็นสีเขียว (หรือแดง)
  2 เม็ด (🟢🟢🔴🔴🔴🔴): วันแรกที่เกิดจุดกลมบน MACD (แท่งที่ 1)
  3 เม็ด (🟢🟢🟢🔴🔴🔴): วันที่ 2–9 ของการนับแท่ง MACD (กำลังรอให้ EMA ตัดกัน)
  4 เม็ด (🟢🟢🟢🟢🔴🔴): วันแรกที่ EMA 9 ตัด EMA 21 (ภายใน 9 แท่ง รอแท่งพรุ่งนี้คอนเฟิร์ม)
  5 เม็ด (🟢🟢🟢🟢🟢🔴): วันคอนเฟิร์มวันแรก! (แท่งถัดมายืนยัน EMA 9 ยกตัว/กดลงจริง = จุดซื้อ/ขายวันนี้!)
  6 เม็ด (🟢🟢🟢🟢🟢🟢): วันถัดๆ ไปหลังผ่านจุดซื้อ/ขายแล้ว (กำลังถือรันเทรนด์เต็มตัว)
"""

from dataclasses import dataclass
from typing import List, Optional
import pandas as pd


@dataclass
class BarState:
    date: str
    close: float
    change_pct: float
    side: str  # "BUY" (🟢 active) or "SELL" (🔴 active)
    trend_locked: Optional[str]  # "BUY" (🟢 base), "SELL" (🔴 base), or None
    b1_kdj: bool
    b2_macd_dot: bool
    b3_counting: bool
    bar_count: int
    max_bars: int
    b4_ema_cross: bool
    b5_ema_confirm: bool
    b6_signal: bool
    dot_colors: List[str]  # List of 6 elements: "G", "R", or "W"
    action_today: str
    status_text: str
    buttons_visual: str
    buttons_compact: str
    macd_dot_date: Optional[str] = None
    ema_cross_date: Optional[str] = None
    signal_date: Optional[str] = None
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    macd: float = 0.0
    macd_signal: float = 0.0
    kdj_k: float = 0.0
    kdj_d: float = 0.0
    kdj_j: float = 0.0


def compute_dot_colors(
    side: str,
    trend_locked: Optional[str],
    b1: bool,
    b2: bool,
    b3: bool,
    b4: bool,
    b5: bool,
    b6: bool,
    action_today: str = "",
) -> List[str]:
    fg = "G" if side == "BUY" else "R"
    bg = "R" if side == "BUY" else "G"

    flags = [b1, b2, b3, b4, b5, b6]
    colors = [fg if flag else bg for flag in flags]
    if action_today == "BUY_NOW":
        colors[5] = "BUY_Rocket"
    elif action_today == "SELL_NOW":
        colors[5] = "SELL_Siren"
    elif action_today == "HOLD_BUY":
        colors[5] = "HOLD_ChartUp"
    elif action_today == "HOLD_SELL":
        colors[5] = "HOLD_ChartDown"
    return colors


def format_dots_compact(dot_colors: List[str]) -> str:
    m = {
        "G": "🟢",
        "R": "🔴",
        "W": "⚪",
        "BUY_Rocket": "🚀",
        "SELL_Siren": "🚨",
        "HOLD_ChartUp": "📈",
        "HOLD_ChartDown": "📉",
    }
    return "".join(m.get(c, "⚪") for c in dot_colors)


def format_dots_visual(dot_colors: List[str], b3: bool, bar_count: int, max_bars: int) -> str:
    m = {
        "G": "🟢",
        "R": "🔴",
        "W": "⚪",
        "BUY_Rocket": "🚀",
        "SELL_Siren": "🚨",
        "HOLD_ChartUp": "📈",
        "HOLD_ChartDown": "📉",
    }
    parts = [m.get(c, "⚪") for c in dot_colors]
    if b3 and bar_count > 0:
        parts[2] = f"{parts[2]}({bar_count}/{max_bars})"
    return " ".join(parts)


def evaluate_strategy_timeline(df: pd.DataFrame, max_wait_bars: int = 9) -> List[BarState]:
    """
    Runs the 6-button sequential state machine with 6 distinct stages and Progressive Color Takeover.
    """
    states: List[BarState] = []

    side: Optional[str] = None
    trend_locked: Optional[str] = None  # "BUY" once confirmed buy, "SELL" once confirmed sell
    b1 = False
    b2 = False
    b3 = False
    bar_count = 0
    b4 = False
    b5 = False
    b6 = False
    macd_dot_date: Optional[str] = None
    ema_cross_date: Optional[str] = None
    signal_date: Optional[str] = None
    just_crossed_on_prev_bar = False
    just_confirmed_on_prev_bar = False

    prev_close = None
    prev_ema_fast = None

    for idx, row in df.iterrows():
        date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
        close = float(row["Close"])
        change_pct = ((close - prev_close) / prev_close * 100.0) if prev_close else 0.0

        kdj_green = bool(row["kdj_green"])
        macd_green_dot = bool(row["macd_green_dot"])
        macd_red_dot = bool(row["macd_red_dot"])
        macd_bullish = bool(row["macd_bullish"])
        macd_bearish = bool(row["macd_bearish"])
        ema_cross_up = bool(row["ema_cross_up"])
        ema_cross_down = bool(row["ema_cross_down"])
        ema_bullish = bool(row["ema_bullish"])
        ema_bearish = bool(row["ema_bearish"])
        ema_fast_val = float(row["ema_fast"]) if pd.notna(row["ema_fast"]) else 0.0
        ema_slow_val = float(row["ema_slow"]) if pd.notna(row["ema_slow"]) else 0.0

        if trend_locked is None and pd.notna(row["ema_slow"]):
            if ema_bullish and macd_bullish and kdj_green:
                trend_locked = "BUY"
            elif ema_bearish and macd_bearish and (not kdj_green):
                trend_locked = "SELL"

        prev_side = side
        action_today = ""

        # =====================================================================
        # CASE 1: KDJ is GREEN (ฝั่งซื้อ 🟢)
        # =====================================================================
        if kdj_green:
            if prev_side != "BUY":
                # KDJ just flipped from RED to GREEN!
                side = "BUY"
                b1 = True
                b2 = False
                b3 = False
                bar_count = 0
                b4 = False
                b5 = False
                b6 = False
                macd_dot_date = None
                ema_cross_date = None
                just_crossed_on_prev_bar = False
                just_confirmed_on_prev_bar = False

                # If main trend was already locked as BUY and the Red pullback failed while EMA9 > EMA21:
                # Snap back to full 6 Green (HOLD_BUY)
                if trend_locked == "BUY" and ema_bullish:
                    b2 = True
                    b3 = True
                    b4 = True
                    b5 = True
                    b6 = True
                    action_today = "HOLD_BUY"
                else:
                    action_today = "WATCH_KDJ_GREEN"

            # Check if a new MACD Green Dot occurs today (Bar 1 -> Button 2 lights up!)
            if macd_green_dot and not (trend_locked == "BUY" and (b5 or b6) and ema_bullish):
                b2 = True
                b3 = False  # Button 3 waits until Bar 2! (Unless EMA crosses today on Bar 1)
                bar_count = 1
                macd_dot_date = date_str
                b4 = False
                b5 = False
                b6 = False
                ema_cross_date = None
                just_crossed_on_prev_bar = False
                just_confirmed_on_prev_bar = False

                if ema_cross_up or ema_bullish:
                    b3 = True
                    b4 = True
                    ema_cross_date = date_str
                    just_crossed_on_prev_bar = True
                    action_today = "WAIT_CONFIRM_BUY"
                else:
                    action_today = "MACD_DOT_BUY"  # 2 Green dots today!

            elif (b5 or b6) and trend_locked == "BUY":
                # Yesterday was either 5 dots (BUY_NOW) or already 6 dots (HOLD_BUY)
                if ema_bullish:
                    b2 = True
                    b3 = True
                    b4 = True
                    b5 = True
                    b6 = True  # Today advances from 5 dots to 6 dots (or stays 6 dots)
                    just_confirmed_on_prev_bar = False
                    action_today = "HOLD_BUY"
                else:
                    b2 = macd_bullish
                    b3 = False
                    bar_count = 0
                    b4 = False
                    b5 = False
                    b6 = False
                    just_confirmed_on_prev_bar = False
                    action_today = "WATCH_KDJ_GREEN"

            elif b2:
                # Active BUY sequence after MACD green dot (Bar 2..9)
                if not macd_bullish:
                    b2 = False
                    b3 = False
                    bar_count = 0
                    b4 = False
                    b5 = False
                    b6 = False
                    macd_dot_date = None
                    ema_cross_date = None
                    just_crossed_on_prev_bar = False
                    action_today = "WATCH_KDJ_GREEN"
                else:
                    bar_count += 1
                    b3 = True  # From Bar 2 onward, Button 3 (counting) is lit!

                    if just_crossed_on_prev_bar and b4:
                        # Confirmation bar right after EMA 9 crossed above EMA 21 -> 5 Dots (BUY_NOW)!
                        ema_lifting = (prev_ema_fast is not None) and (ema_fast_val >= prev_ema_fast)
                        if bar_count <= max_wait_bars + 1 and ema_bullish and ema_lifting:
                            b5 = True
                            b6 = False  # Button 5 = BUY_NOW today! Button 6 lights up tomorrow (HOLD_BUY)
                            trend_locked = "BUY"
                            signal_date = date_str
                            just_crossed_on_prev_bar = False
                            just_confirmed_on_prev_bar = True
                            action_today = "BUY_NOW"
                        else:
                            b4 = False
                            ema_cross_date = None
                            just_crossed_on_prev_bar = False
                            if bar_count > max_wait_bars:
                                b2 = False
                                b3 = False
                                bar_count = 0
                                macd_dot_date = None
                                action_today = "WATCH_KDJ_GREEN"
                            else:
                                action_today = "COUNTING_BUY"
                    else:
                        if bar_count <= max_wait_bars:
                            if ema_cross_up:
                                b4 = True
                                ema_cross_date = date_str
                                just_crossed_on_prev_bar = True
                                action_today = "WAIT_CONFIRM_BUY"
                            else:
                                action_today = "COUNTING_BUY"
                        else:
                            b2 = False
                            b3 = False
                            bar_count = 0
                            b4 = False
                            b5 = False
                            b6 = False
                            macd_dot_date = None
                            ema_cross_date = None
                            just_crossed_on_prev_bar = False
                            action_today = "WATCH_KDJ_GREEN"
            else:
                if not action_today:
                    action_today = "WATCH_KDJ_GREEN"

        # =====================================================================
        # CASE 2: KDJ is RED (ฝั่งขาย 🔴)
        # =====================================================================
        else:
            if prev_side != "SELL":
                side = "SELL"
                b1 = True
                b2 = False
                b3 = False
                bar_count = 0
                b4 = False
                b5 = False
                b6 = False
                macd_dot_date = None
                ema_cross_date = None
                just_crossed_on_prev_bar = False
                just_confirmed_on_prev_bar = False

                if trend_locked == "SELL" and ema_bearish:
                    b2 = True
                    b3 = True
                    b4 = True
                    b5 = True
                    b6 = True
                    action_today = "HOLD_SELL"
                else:
                    action_today = "WATCH_KDJ_RED"

            # Check if a new MACD Red Dot occurs today (Bar 1 -> Button 2 lights up!)
            if macd_red_dot and not (trend_locked == "SELL" and (b5 or b6) and ema_bearish):
                b2 = True
                b3 = False  # Button 3 waits until Bar 2!
                bar_count = 1
                macd_dot_date = date_str
                b4 = False
                b5 = False
                b6 = False
                ema_cross_date = None
                just_crossed_on_prev_bar = False
                just_confirmed_on_prev_bar = False

                if ema_cross_down or ema_bearish:
                    b3 = True
                    b4 = True
                    ema_cross_date = date_str
                    just_crossed_on_prev_bar = True
                    action_today = "WAIT_CONFIRM_SELL"
                else:
                    action_today = "MACD_DOT_SELL"  # 2 Red dots today!

            elif (b5 or b6) and trend_locked == "SELL":
                if ema_bearish:
                    b2 = True
                    b3 = True
                    b4 = True
                    b5 = True
                    b6 = True  # Today advances from 5 dots to 6 dots (or stays 6 dots)
                    just_confirmed_on_prev_bar = False
                    action_today = "HOLD_SELL"
                else:
                    b2 = macd_bearish
                    b3 = False
                    bar_count = 0
                    b4 = False
                    b5 = False
                    b6 = False
                    just_confirmed_on_prev_bar = False
                    action_today = "WATCH_KDJ_RED"

            elif b2:
                if not macd_bearish:
                    b2 = False
                    b3 = False
                    bar_count = 0
                    b4 = False
                    b5 = False
                    b6 = False
                    macd_dot_date = None
                    ema_cross_date = None
                    just_crossed_on_prev_bar = False
                    action_today = "WATCH_KDJ_RED"
                else:
                    bar_count += 1
                    b3 = True  # From Bar 2 onward, Button 3 (counting) is lit!

                    if just_crossed_on_prev_bar and b4:
                        ema_dropping = (prev_ema_fast is not None) and (ema_fast_val <= prev_ema_fast)
                        if bar_count <= max_wait_bars + 1 and ema_bearish and ema_dropping:
                            b5 = True
                            b6 = False  # Button 5 = SELL_NOW today! Button 6 lights up tomorrow (HOLD_SELL)
                            trend_locked = "SELL"
                            signal_date = date_str
                            just_crossed_on_prev_bar = False
                            just_confirmed_on_prev_bar = True
                            action_today = "SELL_NOW"
                        else:
                            b4 = False
                            ema_cross_date = None
                            just_crossed_on_prev_bar = False
                            if bar_count > max_wait_bars:
                                b2 = False
                                b3 = False
                                bar_count = 0
                                macd_dot_date = None
                                action_today = "WATCH_KDJ_RED"
                            else:
                                action_today = "COUNTING_SELL"
                    else:
                        if bar_count <= max_wait_bars:
                            if ema_cross_down:
                                b4 = True
                                ema_cross_date = date_str
                                just_crossed_on_prev_bar = True
                                action_today = "WAIT_CONFIRM_SELL"
                            else:
                                action_today = "COUNTING_SELL"
                        else:
                            b2 = False
                            b3 = False
                            bar_count = 0
                            b4 = False
                            b5 = False
                            b6 = False
                            macd_dot_date = None
                            ema_cross_date = None
                            just_crossed_on_prev_bar = False
                            action_today = "WATCH_KDJ_RED"
            else:
                if not action_today:
                    action_today = "WATCH_KDJ_RED"

        dot_colors = compute_dot_colors(
            side=side,
            trend_locked=trend_locked,
            b1=b1,
            b2=b2,
            b3=b3,
            b4=b4,
            b5=b5,
            b6=b6,
            action_today=action_today,
        )
        buttons_compact = format_dots_compact(dot_colors)
        buttons_visual = format_dots_visual(dot_colors, b3, bar_count, max_bars=max_wait_bars)

        status_map = {
            "BUY_NOW": f"🚀 เม็ดที่ 5 คอนเฟิร์มเข้าซื้อวันนี้! (แท่งที่ {bar_count}/{max_wait_bars})",
            "SELL_NOW": f"🚨 เม็ดที่ 5 คอนเฟิร์มขายออกวันนี้! (แท่งที่ {bar_count}/{max_wait_bars})",
            "WAIT_CONFIRM_BUY": f"👀 เม็ดที่ 4: EMA9 ตัดขึ้น EMA21 วันแรก (แท่ง {bar_count}/{max_wait_bars}) รอพรุ่งนี้ขึ้นเม็ด 5",
            "WAIT_CONFIRM_SELL": f"⚠️ เม็ดที่ 4: EMA9 ตัดลง EMA21 วันแรก (แท่ง {bar_count}/{max_wait_bars}) รอพรุ่งนี้ขึ้นเม็ด 5",
            "COUNTING_BUY": f"⏳ เม็ดที่ 3: นับแท่งที่ {bar_count}/{max_wait_bars} รอ EMA9 ตัดขึ้น EMA21",
            "COUNTING_SELL": f"⏳ เม็ดที่ 3: นับแท่งที่ {bar_count}/{max_wait_bars} รอ EMA9 ตัดลง EMA21",
            "MACD_DOT_BUY": "🟢 เม็ดที่ 2: เพิ่งเกิดจุดเขียว MACD วันแรก (แท่งที่ 1/9)",
            "MACD_DOT_SELL": "🔴 เม็ดที่ 2: เพิ่งเกิดจุดแดง MACD วันแรก (แท่งที่ 1/9)",
            "HOLD_BUY": "✅ เม็ดที่ 6: ขาขึ้นเต็มตัว 6 เม็ดเขียว (ถือรันเทรนด์)",
            "HOLD_SELL": "🔻 เม็ดที่ 6: ขาลงเต็มตัว 6 เม็ดแดง (อยู่ในเทรนด์ขาลง)",
            "WATCH_KDJ_GREEN": "🟢 เม็ดที่ 1: KDJ เขียว รอจุดเขียว MACD",
            "WATCH_KDJ_RED": "🔴 เม็ดที่ 1: KDJ แดง รอจุดแดง MACD",
        }
        status_text = status_map.get(action_today, "")

        states.append(
            BarState(
                date=date_str,
                close=round(close, 2),
                change_pct=round(change_pct, 2),
                side=side,
                trend_locked=trend_locked,
                b1_kdj=b1,
                b2_macd_dot=b2,
                b3_counting=b3,
                bar_count=bar_count,
                max_bars=max_wait_bars,
                b4_ema_cross=b4,
                b5_ema_confirm=b5,
                b6_signal=b6,
                dot_colors=dot_colors,
                action_today=action_today,
                status_text=status_text,
                buttons_visual=buttons_visual,
                buttons_compact=buttons_compact,
                macd_dot_date=macd_dot_date,
                ema_cross_date=ema_cross_date,
                signal_date=signal_date,
                ema_fast=round(ema_fast_val, 2),
                ema_slow=round(ema_slow_val, 2),
                macd=round(float(row["macd"]) if pd.notna(row["macd"]) else 0.0, 3),
                macd_signal=round(float(row["macd_signal"]) if pd.notna(row["macd_signal"]) else 0.0, 3),
                kdj_k=round(float(row["kdj_k"]) if pd.notna(row["kdj_k"]) else 0.0, 2),
                kdj_d=round(float(row["kdj_d"]) if pd.notna(row["kdj_d"]) else 0.0, 2),
                kdj_j=round(float(row["kdj_j"]) if pd.notna(row["kdj_j"]) else 0.0, 2),
            )
        )

        prev_close = close
        prev_ema_fast = ema_fast_val

    return states
