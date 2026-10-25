"""
6-Button Sequential Strategy Engine (New 6-Button Specification - แบบ ก)

ความหมายของเม็ดกระดุมทั้ง 6 เม็ด:
  เม็ดที่ 1 (🟢🔴🔴🔴🔴🔴): KDJ เปลี่ยนสี (%J > %D เขียว / %J <= %D แดง)
  เม็ดที่ 2 (🟢🟢🔴🔴🔴🔴): เกิดจุดตัด MACD เริ่มนับเป็นแท่งที่ 0 (และนับแท่งที่ 1–9 รอ EMA9 ตัด EMA21)
  เม็ดที่ 3 (🟢🟢🟢🔴🔴🔴): ภายในแท่งที่ 1–9 เปลี่ยนสีเมื่อ EMA9 ตัด EMA21 (รอแท่งถัดไปคอนเฟิร์ม)
  เม็ดที่ 4 (🟢🟢🟢🟢🔴🔴): แท่งถัดมา EMA9 อยู่เหนือกว่า EMA21 (ขาขึ้น) หรือ EMA9 อยู่ต่ำกว่า EMA21 (ขาลง)
  เม็ดที่ 5 (🟢🟢🟢🟢🟢🚀): แท่งเทียนวันนั้นปิดเหนือ EMA9 และ EMA21 (ขาขึ้น) หรือปิดต่ำกว่า EMA9 และ EMA21 (ขาลง)
  เม็ดที่ 6 (🚀/🚨/📈/📉/🟢/🔴): แสดงผลการเข้าซื้อ (🚀) การขาย (🚨) การรันเทรนด์ (📈/📉) หรือการพักตัว (🟢/🔴)
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


def format_dots_visual(dot_colors: List[str], b2: bool, bar_count: int, max_bars: int) -> str:
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
    if b2:
        parts[1] = f"{parts[1]}({bar_count}/{max_bars})"
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

    # Persistent MACD window memory (prevents 1-day KDJ flicker from wiping active MACD 0..9 bar count)
    bull_macd_active = False
    bull_macd_bars = 0
    bull_macd_date: Optional[str] = None
    bull_ema_crossed = False
    bull_ema_date: Optional[str] = None

    bear_macd_active = False
    bear_macd_bars = 0
    bear_macd_date: Optional[str] = None
    bear_ema_crossed = False
    bear_ema_date: Optional[str] = None

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
        close_above_emas = (close > ema_fast_val) and (close > ema_slow_val)
        close_below_emas = (close < ema_fast_val) and (close < ema_slow_val)

        # Update persistent Bullish MACD window (0..max_wait_bars)
        if macd_green_dot:
            bull_macd_active = True
            bull_macd_bars = 0
            bull_macd_date = date_str
            bull_ema_crossed = bool(ema_cross_up or ema_bullish)
            bull_ema_date = date_str if bull_ema_crossed else None
        elif bull_macd_active:
            if not macd_bullish:
                bull_macd_active = False
            else:
                bull_macd_bars += 1
                if bull_macd_bars > max_wait_bars:
                    bull_macd_active = False
                elif ema_cross_up and not bull_ema_crossed:
                    bull_ema_crossed = True
                    bull_ema_date = date_str

        # Update persistent Bearish MACD window (0..max_wait_bars)
        if macd_red_dot:
            bear_macd_active = True
            bear_macd_bars = 0
            bear_macd_date = date_str
            bear_ema_crossed = bool(ema_cross_down or ema_bearish)
            bear_ema_date = date_str if bear_ema_crossed else None
        elif bear_macd_active:
            if not macd_bearish:
                bear_macd_active = False
            else:
                bear_macd_bars += 1
                if bear_macd_bars > max_wait_bars:
                    bear_macd_active = False
                elif ema_cross_down and not bear_ema_crossed:
                    bear_ema_crossed = True
                    bear_ema_date = date_str

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
                # KDJ just flipped from RED to GREEN! (เม็ดที่ 1)
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
                # Snap back to full 6 Green (HOLD_BUY -> 📈)
                if trend_locked == "BUY" and ema_bullish:
                    b2 = True
                    b3 = True
                    b4 = True
                    b5 = True
                    b6 = True
                    action_today = "HOLD_BUY"
                elif bull_macd_active and not macd_green_dot:
                    # Restore active MACD window if KDJ flickered or lagged MACD
                    b2 = True
                    bar_count = bull_macd_bars - 1
                    macd_dot_date = bull_macd_date
                    if bull_ema_crossed and bull_ema_date != date_str:
                        b3 = True
                        ema_cross_date = bull_ema_date
                        just_crossed_on_prev_bar = True
                else:
                    action_today = "WATCH_KDJ_GREEN"

            # เม็ดที่ 2: เกิดจุดตัด MACD เริ่มนับเป็นแท่งที่ 0
            if macd_green_dot and not (trend_locked == "BUY" and (b5 or b6) and ema_bullish):
                b2 = True
                b3 = False
                bar_count = 0  # เริ่มนับเป็นแท่งที่ 0!
                macd_dot_date = date_str
                b4 = False
                b5 = False
                b6 = False
                ema_cross_date = None
                just_crossed_on_prev_bar = False
                just_confirmed_on_prev_bar = False

                if ema_cross_up or ema_bullish:
                    b3 = True  # เม็ดที่ 3: EMA9 ตัด EMA21
                    ema_cross_date = date_str
                    just_crossed_on_prev_bar = True
                    action_today = "WAIT_CONFIRM_BUY"
                else:
                    action_today = "MACD_DOT_BUY"  # 2 Green dots today (Bar 0)

            elif (b5 or b6) and trend_locked == "BUY":
                # Yesterday was BUY_NOW (🚀) or already HOLD_BUY (📈)
                if ema_bullish:
                    b2 = True
                    b3 = True
                    b4 = True
                    b5 = True
                    b6 = True
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
                # Active BUY sequence after MACD green dot (แท่งที่ 1..9)
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
                    bar_count += 1  # นับแท่งที่ 1..9

                    if just_crossed_on_prev_bar and b3:
                        # แท่งถัดมาหลังเม็ดที่ 3: เช็คเม็ดที่ 4 (EMA9 > EMA21) และเม็ดที่ 5 (Close > EMA9 & EMA21)
                        if bar_count <= max_wait_bars and ema_bullish and close_above_emas:
                            b4 = True
                            b5 = True
                            b6 = True
                            trend_locked = "BUY"
                            signal_date = date_str
                            just_crossed_on_prev_bar = False
                            just_confirmed_on_prev_bar = True
                            action_today = "BUY_NOW"
                        elif bar_count <= max_wait_bars and ema_bullish and (not close_above_emas):
                            # เม็ดที่ 4 ติดแล้ว (EMA9 > EMA21) รอเม็ดที่ 5 (แท่งเทียนปิดเหนือ EMA9 & EMA21)
                            b4 = True
                            b5 = False
                            b6 = False
                            action_today = "WAIT_CONFIRM_BUY"
                        else:
                            b3 = False
                            b4 = False
                            ema_cross_date = None
                            just_crossed_on_prev_bar = False
                            if bar_count > max_wait_bars:
                                b2 = False
                                bar_count = 0
                                macd_dot_date = None
                                action_today = "WATCH_KDJ_GREEN"
                            else:
                                action_today = "COUNTING_BUY"
                    else:
                        if bar_count <= max_wait_bars:
                            if ema_cross_up:
                                b3 = True  # เม็ดที่ 3: ภายในแท่งที่ 1–9 EMA9 ตัด EMA21
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
                elif bear_macd_active and not macd_red_dot:
                    # Restore active MACD window if KDJ flickered or lagged MACD
                    b2 = True
                    bar_count = bear_macd_bars - 1
                    macd_dot_date = bear_macd_date
                    if bear_ema_crossed and bear_ema_date != date_str:
                        b3 = True
                        ema_cross_date = bear_ema_date
                        just_crossed_on_prev_bar = True
                else:
                    action_today = "WATCH_KDJ_RED"

            # เม็ดที่ 2: เกิดจุดตัด MACD เริ่มนับเป็นแท่งที่ 0
            if macd_red_dot and not (trend_locked == "SELL" and (b5 or b6) and ema_bearish):
                b2 = True
                b3 = False
                bar_count = 0  # เริ่มนับเป็นแท่งที่ 0!
                macd_dot_date = date_str
                b4 = False
                b5 = False
                b6 = False
                ema_cross_date = None
                just_crossed_on_prev_bar = False
                just_confirmed_on_prev_bar = False

                if ema_cross_down or ema_bearish:
                    b3 = True  # เม็ดที่ 3: EMA9 ตัดลง EMA21
                    ema_cross_date = date_str
                    just_crossed_on_prev_bar = True
                    action_today = "WAIT_CONFIRM_SELL"
                else:
                    action_today = "MACD_DOT_SELL"  # 2 Red dots today (Bar 0)

            elif (b5 or b6) and trend_locked == "SELL":
                if ema_bearish:
                    b2 = True
                    b3 = True
                    b4 = True
                    b5 = True
                    b6 = True
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
                    bar_count += 1  # นับแท่งที่ 1..9

                    if just_crossed_on_prev_bar and b3:
                        # แท่งถัดมาหลังเม็ดที่ 3: เช็คเม็ดที่ 4 (EMA9 < EMA21) และเม็ดที่ 5 (Close < EMA9 & EMA21)
                        if bar_count <= max_wait_bars and ema_bearish and close_below_emas:
                            b4 = True
                            b5 = True
                            b6 = True
                            trend_locked = "SELL"
                            signal_date = date_str
                            just_crossed_on_prev_bar = False
                            just_confirmed_on_prev_bar = True
                            action_today = "SELL_NOW"
                        elif bar_count <= max_wait_bars and ema_bearish and (not close_below_emas):
                            b4 = True
                            b5 = False
                            b6 = False
                            action_today = "WAIT_CONFIRM_SELL"
                        else:
                            b3 = False
                            b4 = False
                            ema_cross_date = None
                            just_crossed_on_prev_bar = False
                            if bar_count > max_wait_bars:
                                b2 = False
                                bar_count = 0
                                macd_dot_date = None
                                action_today = "WATCH_KDJ_RED"
                            else:
                                action_today = "COUNTING_SELL"
                    else:
                        if bar_count <= max_wait_bars:
                            if ema_cross_down:
                                b3 = True  # เม็ดที่ 3: ภายในแท่งที่ 1–9 EMA9 ตัดลง EMA21
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
        buttons_visual = format_dots_visual(dot_colors, b2, bar_count, max_bars=max_wait_bars)

        status_map = {
            "BUY_NOW": f"🚀 ครบเงื่อนไขเข้าซื้อวันนี้! (EMA9>21 + แท่งเทียนปิดเหนือ EMA แท่งที่ {bar_count}/{max_wait_bars})",
            "SELL_NOW": f"🚨 ครบเงื่อนไขขายออกวันนี้! (EMA9<21 + แท่งเทียนปิดต่ำกว่า EMA แท่งที่ {bar_count}/{max_wait_bars})",
            "WAIT_CONFIRM_BUY": f"👀 เม็ดที่ 3–4: EMA9 ตัดขึ้น EMA21 แล้ว (แท่งที่ {bar_count}/{max_wait_bars}) รอแท่งถัดไปคอนเฟิร์มปิดเหนือ EMA",
            "WAIT_CONFIRM_SELL": f"⚠️ เม็ดที่ 3–4: EMA9 ตัดลง EMA21 แล้ว (แท่งที่ {bar_count}/{max_wait_bars}) รอแท่งถัดไปคอนเฟิร์มปิดต่ำกว่า EMA",
            "COUNTING_BUY": f"⏳ เม็ดที่ 2: จุดตัด MACD นับแท่งที่ {bar_count}/{max_wait_bars} รอ EMA9 ตัดขึ้น EMA21",
            "COUNTING_SELL": f"⏳ เม็ดที่ 2: จุดตัด MACD นับแท่งที่ {bar_count}/{max_wait_bars} รอ EMA9 ตัดลง EMA21",
            "MACD_DOT_BUY": "🟢 เม็ดที่ 2: เกิดจุดตัดเขียว MACD วันแรก (เริ่มนับแท่งที่ 0/9)",
            "MACD_DOT_SELL": "🔴 เม็ดที่ 2: เกิดจุดตัดแดง MACD วันแรก (เริ่มนับแท่งที่ 0/9)",
            "HOLD_BUY": "📈 เม็ดที่ 6: รันเทรนด์ขาขึ้นเต็มตัว",
            "HOLD_SELL": "📉 เม็ดที่ 6: รันเทรนด์ขาลงเต็มตัว",
            "WATCH_KDJ_GREEN": "🟢 เม็ดที่ 1: KDJ เปลี่ยนเป็นสีเขียว รอจุดตัด MACD",
            "WATCH_KDJ_RED": "🔴 เม็ดที่ 1: KDJ เปลี่ยนเป็นสีแดง รอจุดตัด MACD",
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
