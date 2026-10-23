"""
6-Button Sequential Strategy Engine (Progressive Color Takeover + Strict Reset)

หลักการทำงานของเม็ดกระดุม 6 เม็ด:
1. โครงสร้างหลัก (trend_locked):
   - เมื่อหุ้นเคยทำครบ 6 เม็ดเขียวสำเร็จ -> โครงสร้างหลักจะเป็นสีเขียว (🟢🟢🟢🟢🟢🟢)
   - เมื่อหุ้นเคยทำครบ 6 เม็ดแดงสำเร็จ -> โครงสร้างหลักจะเป็นสีแดง (🔴🔴🔴🔴🔴🔴)

2. การกลืนสีทีละเม็ดเมื่อเริ่มกลับตัว (Progressive Takeover):
   - สมมติโครงสร้างหลักเป็นขาขึ้นครบ 6 เม็ดเขียว (🟢🟢🟢🟢🟢🟢):
     * ถ้า KDJ เริ่มย่อเป็นสีแดง (เม็ด 1) -> เม็ดที่ 1 เปลี่ยนเป็นสีแดง ส่วนเม็ด 2-6 ยังคงเป็นสีเขียว: 🔴🟢🟢🟢🟢🟢
     * ถ้าเกิดจุดแดง MACD (เม็ด 2-3) -> เม็ดที่ 1-3 เปลี่ยนเป็นสีแดง ส่วนเม็ด 4-6 ยังคงเป็นสีเขียว: 🔴🔴🔴🟢🟢🟢
     * ถ้าภายใน 9 แท่ง EMA9 ตัดลง EMA21 (เม็ด 4) -> เม็ดที่ 1-4 เป็นสีแดง เม็ด 5-6 ยังเป็นสีเขียว: 🔴🔴🔴🔴🟢🟢
     * ถ้าแท่งถัดมาคอนเฟิร์ม EMA9 กดต่ำกว่า EMA21 (เม็ด 5-6) -> สีแดงกลืนครบทั้ง 6 เม็ด: 🔴🔴🔴🔴🔴🔴 (เปลี่ยนโครงสร้างหลักเป็นขาลง!)
     * แต่ถ้าเป็น "สัญญาณหลอก" (ยังไม่ทันครบ 6 เม็ดแดง แล้ว KDJ พลิกกลับมาเป็นสีเขียว หรือเกิน 9 แท่งแล้วยังไม่ตัดลง):
       เม็ดสีแดงที่กินเข้ามาจะถูกรีเซ็ต และดีดกลับเป็นเขียวครบ 6 เม็ด (🟢🟢🟢🟢🟢🟢) ทันที (ตราบใดที่ EMA9 ยังอยู่เหนือ EMA21)!

   - ในทางกลับกัน ถ้าโครงสร้างหลักเป็นขาลงครบ 6 เม็ดแดง (🔴🔴🔴🔴🔴🔴):
     * เมื่อเริ่มฟื้นตัว เม็ดสีเขียวจะค่อยๆ กลืนจากซ้ายไปขวา:
       🟢🔴🔴🔴🔴🔴 ➔ 🟢🟢🟢🔴🔴🔴 ➔ 🟢🟢🟢🟢🔴🔴 ➔ 🟢🟢🟢🟢🟢🟢
     * หากเป็นสัญญาณเด้งหลอก (KDJ พลิกกลับเป็นแดงก่อนครบ 6 เม็ดเขียว) ก็จะดีดกลับเป็น 🔴🔴🔴🔴🔴🔴 ทันที!
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
) -> List[str]:
    """
    Returns a 6-element list of ["G" | "R" | "W"] representing the color of each button 1..6.
    - Active challenger/current side colors buttons that are True with its color ("G" for BUY, "R" for SELL).
    - Remaining False buttons retain the `trend_locked` base color ("G" if locked BUY, "R" if locked SELL, else "W").
    """
    fg = "G" if side == "BUY" else "R"
    if trend_locked == "BUY":
        bg = "G"
    elif trend_locked == "SELL":
        bg = "R"
    else:
        bg = "W"

    flags = [b1, b2, b3, b4, b5, b6]
    return [fg if flag else bg for flag in flags]


def format_dots_compact(dot_colors: List[str]) -> str:
    m = {"G": "🟢", "R": "🔴", "W": "⚪"}
    return "".join(m.get(c, "⚪") for c in dot_colors)


def format_dots_visual(dot_colors: List[str], b3: bool, bar_count: int, max_bars: int) -> str:
    m = {"G": "🟢", "R": "🔴", "W": "⚪"}
    parts = [m.get(c, "⚪") for c in dot_colors]
    if b3 and bar_count > 0:
        parts[2] = f"{parts[2]}({bar_count}/{max_bars})"
    return " ".join(parts)


def evaluate_strategy_timeline(df: pd.DataFrame, max_wait_bars: int = 9) -> List[BarState]:
    """
    Runs the 6-button sequential state machine with Progressive Color Takeover across all rows.
    """
    states: List[BarState] = []

    side: Optional[str] = None
    trend_locked: Optional[str] = None  # "BUY" once 6 green completed, "SELL" once 6 red completed
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

        # Initialize trend_locked on early bars if not set yet based on EMA alignment
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

                # If main trend was already locked as BUY (🟢🟢🟢🟢🟢🟢) and the Red pullback failed
                # while EMA9 is still above EMA21 -> False pullback! Snap back to full 6 Green!
                if trend_locked == "BUY" and ema_bullish:
                    b2 = True
                    b3 = True
                    b4 = True
                    b5 = True
                    b6 = True
                    action_today = "HOLD_BUY"
                else:
                    action_today = "WATCH_KDJ_GREEN"

            # Check if a new MACD Green Dot occurs today while KDJ is Green
            if macd_green_dot and not (trend_locked == "BUY" and b6 and ema_bullish):
                b2 = True
                b3 = True
                bar_count = 1
                macd_dot_date = date_str
                b4 = False
                b5 = False
                b6 = False
                ema_cross_date = None
                just_crossed_on_prev_bar = False

                if ema_cross_up:
                    b4 = True
                    ema_cross_date = date_str
                    just_crossed_on_prev_bar = True
                    action_today = "WAIT_CONFIRM_BUY"
                else:
                    action_today = "COUNTING_BUY"

            elif b6 and trend_locked == "BUY":
                # Already in full 6-green uptrend
                if ema_bullish:
                    action_today = "HOLD_BUY"
                else:
                    # EMA9 dipped below EMA21 while KDJ is green -> wait for new cross
                    b2 = macd_bullish
                    b3 = False
                    bar_count = 0
                    b4 = False
                    b5 = False
                    b6 = False
                    action_today = "WATCH_KDJ_GREEN"

            elif b2:
                # Active BUY sequence counting 1..9 toward EMA crossover
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

                    if just_crossed_on_prev_bar and b4:
                        ema_lifting = (prev_ema_fast is not None) and (ema_fast_val >= prev_ema_fast)
                        if bar_count <= max_wait_bars and ema_bullish and ema_lifting:
                            b5 = True
                            b6 = True
                            trend_locked = "BUY"
                            signal_date = date_str
                            just_crossed_on_prev_bar = False
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
                            # Exceeded 9 bars without EMA crossover -> Reset challenger progress
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
                # KDJ just flipped from GREEN to RED!
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

                # If main trend was already locked as SELL (🔴🔴🔴🔴🔴🔴) and the Green bounce failed
                # while EMA9 is still below EMA21 -> False bounce! Snap back to full 6 Red!
                if trend_locked == "SELL" and ema_bearish:
                    b2 = True
                    b3 = True
                    b4 = True
                    b5 = True
                    b6 = True
                    action_today = "HOLD_SELL"
                else:
                    action_today = "WATCH_KDJ_RED"

            # Check if a new MACD Red Dot occurs today while KDJ is Red
            if macd_red_dot and not (trend_locked == "SELL" and b6 and ema_bearish):
                b2 = True
                b3 = True
                bar_count = 1
                macd_dot_date = date_str
                b4 = False
                b5 = False
                b6 = False
                ema_cross_date = None
                just_crossed_on_prev_bar = False

                if ema_cross_down:
                    b4 = True
                    ema_cross_date = date_str
                    just_crossed_on_prev_bar = True
                    action_today = "WAIT_CONFIRM_SELL"
                else:
                    action_today = "COUNTING_SELL"

            elif b6 and trend_locked == "SELL":
                # Already in full 6-red downtrend
                if ema_bearish:
                    action_today = "HOLD_SELL"
                else:
                    b2 = macd_bearish
                    b3 = False
                    bar_count = 0
                    b4 = False
                    b5 = False
                    b6 = False
                    action_today = "WATCH_KDJ_RED"

            elif b2:
                # Active SELL sequence counting 1..9 toward EMA crossunder
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

                    if just_crossed_on_prev_bar and b4:
                        ema_dropping = (prev_ema_fast is not None) and (ema_fast_val <= prev_ema_fast)
                        if bar_count <= max_wait_bars and ema_bearish and ema_dropping:
                            b5 = True
                            b6 = True
                            trend_locked = "SELL"
                            signal_date = date_str
                            just_crossed_on_prev_bar = False
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
        )
        buttons_compact = format_dots_compact(dot_colors)
        buttons_visual = format_dots_visual(dot_colors, b3, bar_count, max_wait_bars)

        status_map = {
            "BUY_NOW": f"🚀 สัญญาณเข้าซื้อวันนี้! (กลืนครบ 6 เม็ดเขียว แท่งที่ {bar_count}/{max_wait_bars})",
            "SELL_NOW": f"🚨 สัญญาณขายออกวันนี้! (กลืนครบ 6 เม็ดแดง แท่งที่ {bar_count}/{max_wait_bars})",
            "WAIT_CONFIRM_BUY": f"👀 เตรียมซื้อ! เม็ดเขียวกลืนถึงเม็ดที่ 4 (แท่ง {bar_count}/{max_wait_bars}) รอพรุ่งนี้คอนเฟิร์ม",
            "WAIT_CONFIRM_SELL": f"⚠️ เตรียมขาย! เม็ดแดงกลืนถึงเม็ดที่ 4 (แท่ง {bar_count}/{max_wait_bars}) รอพรุ่งนี้คอนเฟิร์ม",
            "COUNTING_BUY": f"⏳ เม็ดเขียวกลืนถึงเม็ดที่ 3 (นับแท่ง {bar_count}/{max_wait_bars} รอ EMA9 ตัดขึ้น EMA21)",
            "COUNTING_SELL": f"⏳ เม็ดแดงกลืนถึงเม็ดที่ 3 (นับแท่ง {bar_count}/{max_wait_bars} รอ EMA9 ตัดลง EMA21)",
            "HOLD_BUY": "✅ ขาขึ้นเต็มตัว 6 เม็ดเขียว (ถือรันเทรนด์ขาขึ้น)",
            "HOLD_SELL": "🔻 ขาลงเต็มตัว 6 เม็ดแดง (อยู่ในเทรนด์ขาลง)",
            "WATCH_KDJ_GREEN": "🟢 KDJ เขียวเม็ดที่ 1 (รอจุดเขียว MACD)",
            "WATCH_KDJ_RED": "🔴 KDJ แดงเม็ดที่ 1 (รอจุดแดง MACD)",
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
