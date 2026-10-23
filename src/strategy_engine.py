"""
6-Button Sequential Strategy Engine (แบบ ก. + กฎเหล็กแบบที่ 1 Strict Reset)

ลำดับเม็ดกระดุม 6 ขั้นตอน:
ฝั่งซื้อ (BUY - 🟢):
  เม็ดที่ 1: KDJ พื้นหลังสีเขียว (%J > %D)
  เม็ดที่ 2: MACD (ChrisMoody) เกิดจุดเขียว (MACD ตัดขึ้นเหนือ Signal)
  เม็ดที่ 3: นับแท่งเทียนจากจุดเขียว MACD เป็นแท่งที่ 1 (รอไม่เกิน 9 แท่ง)
  เม็ดที่ 4: EMA 9 ตัดขึ้นเหนือ EMA 21 ภายในกรอบ 9 แท่ง
  เม็ดที่ 5: แท่งถัดมา คอนเฟิร์ม EMA 9 ยกตัวอยู่เหนือ EMA 21 จริงๆ
  เม็ดที่ 6: แจ้งเตือนจุดเข้าซื้อ (BUY SIGNAL)

ฝั่งขาย (SELL - 🔴):
  เม็ดที่ 1: KDJ พื้นหลังสีแดง (%J <= %D)
  เม็ดที่ 2: MACD (ChrisMoody) เกิดจุดแดง (MACD ตัดลงใต้ Signal)
  เม็ดที่ 3: นับแท่งเทียนจากจุดแดง MACD เป็นแท่งที่ 1 (รอไม่เกิน 9 แท่ง)
  เม็ดที่ 4: EMA 9 ตัดลงใต้ EMA 21 ภายในกรอบ 9 แท่ง
  เม็ดที่ 5: แท่งถัดมา คอนเฟิร์ม EMA 9 กดต่ำกว่า EMA 21 จริงๆ
  เม็ดที่ 6: แจ้งเตือนจุดขายออก (SELL SIGNAL)

กฎเหล็กแบบที่ 1 (Strict Reset):
  - หากรอบฝั่งซื้อกำลังนับอยู่ แล้ว KDJ พลิกกลับเป็นสีแดงแม้แต่แท่งเดียว -> ล้างกระดุมเขียวทั้งหมดทันที
    และสลับเป็นเม็ดที่ 1 สีแดง (🔴 ⚪ ⚪ ⚪ ⚪ ⚪)
  - หากรอบฝั่งขายกำลังนับอยู่ แล้ว KDJ พลิกกลับเป็นสีเขียวแม้แต่แท่งเดียว -> ล้างกระดุมแดงทั้งหมดทันที
    และสลับเป็นเม็ดที่ 1 สีเขียว (🟢 ⚪ ⚪ ⚪ ⚪ ⚪)
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import pandas as pd


@dataclass
class BarState:
    date: str
    close: float
    change_pct: float
    side: str  # "BUY" (🟢) or "SELL" (🔴)
    b1_kdj: bool
    b2_macd_dot: bool
    b3_counting: bool
    bar_count: int  # 0 if not counting, 1..9 during window
    max_bars: int
    b4_ema_cross: bool
    b5_ema_confirm: bool
    b6_signal: bool
    action_today: str  # "BUY_NOW", "SELL_NOW", "WAIT_CONFIRM_BUY", "WAIT_CONFIRM_SELL", "COUNTING_BUY", "COUNTING_SELL", "HOLD_BUY", "HOLD_SELL", "RESET_TO_RED", "RESET_TO_GREEN", "WATCH_KDJ_GREEN", "WATCH_KDJ_RED"
    status_text: str
    buttons_visual: str
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


def format_buttons_visual(
    side: str,
    b1: bool,
    b2: bool,
    b3: bool,
    bar_count: int,
    max_bars: int,
    b4: bool,
    b5: bool,
    b6: bool,
) -> str:
    dot = "🟢" if side == "BUY" else "🔴"
    s1 = dot if b1 else "⚪"
    s2 = dot if b2 else "⚪"
    s3 = f"{dot}({bar_count}/{max_bars})" if b3 and bar_count > 0 else "⚪"
    s4 = dot if b4 else "⚪"
    s5 = dot if b5 else "⚪"
    s6 = dot if b6 else "⚪"
    return f"{s1} {s2} {s3} {s4} {s5} {s6}"


def evaluate_strategy_timeline(df: pd.DataFrame, max_wait_bars: int = 9) -> List[BarState]:
    """
    Runs the 6-button sequential state machine across all rows of an indicator-enriched DataFrame.
    Returns the chronological list of BarState objects.
    """
    states: List[BarState] = []

    side: Optional[str] = None
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

        prev_side = side
        prev_had_progress = b2 or b3 or b4 or b5 or b6
        action_today = ""

        # =====================================================================
        # CASE 1: KDJ is GREEN (ฝั่งซื้อ 🟢)
        # =====================================================================
        if kdj_green:
            if prev_side != "BUY":
                # Flipped from SELL (Red) to BUY (Green) -> Strict Reset of Red buttons!
                was_counting_red = (prev_side == "SELL") and prev_had_progress
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
                signal_date = None
                just_crossed_on_prev_bar = False
                action_today = "RESET_TO_GREEN" if was_counting_red else "WATCH_KDJ_GREEN"

            # Check if a new MACD Green Dot occurs today while KDJ is Green
            if macd_green_dot:
                b2 = True
                b3 = True
                bar_count = 1
                macd_dot_date = date_str
                b4 = False
                b5 = False
                b6 = False
                ema_cross_date = None
                signal_date = None
                just_crossed_on_prev_bar = False

                if ema_cross_up:
                    b4 = True
                    ema_cross_date = date_str
                    just_crossed_on_prev_bar = True
                    action_today = "WAIT_CONFIRM_BUY"
                else:
                    action_today = "COUNTING_BUY"

            elif b2:
                # Currently in an active BUY sequence after MACD green dot
                if not macd_bullish:
                    # MACD turned bearish while KDJ was still green -> Reset MACD/EMA steps
                    b2 = False
                    b3 = False
                    bar_count = 0
                    b4 = False
                    b5 = False
                    b6 = False
                    macd_dot_date = None
                    ema_cross_date = None
                    signal_date = None
                    just_crossed_on_prev_bar = False
                    action_today = "WATCH_KDJ_GREEN"
                elif b6:
                    # Already triggered BUY in this cycle -> keep holding as long as EMA9 > EMA21 & KDJ green
                    if ema_bullish:
                        action_today = "HOLD_BUY"
                    else:
                        # EMA 9 dropped below EMA 21
                        b4 = False
                        b5 = False
                        b6 = False
                        action_today = "WATCH_KDJ_GREEN"
                else:
                    # Increment bar counter from MACD green dot
                    bar_count += 1

                    if just_crossed_on_prev_bar and b4:
                        # Today is the confirmation bar right after EMA 9 crossed above EMA 21!
                        ema_lifting = (prev_ema_fast is not None) and (ema_fast_val >= prev_ema_fast)
                        if bar_count <= max_wait_bars and ema_bullish and ema_lifting:
                            b5 = True
                            b6 = True
                            signal_date = date_str
                            just_crossed_on_prev_bar = False
                            action_today = "BUY_NOW"
                        else:
                            # Failed next-bar confirmation or exceeded 9 bars -> reset
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
                        # Waiting for EMA 9 to cross above EMA 21 within 9 bars
                        if bar_count <= max_wait_bars:
                            if ema_cross_up:
                                b4 = True
                                ema_cross_date = date_str
                                just_crossed_on_prev_bar = True
                                action_today = "WAIT_CONFIRM_BUY"
                            else:
                                action_today = "COUNTING_BUY"
                        else:
                            # Exceeded 9 bars without EMA crossover -> Reset 9-bar count
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
                # Flipped from BUY (Green) to SELL (Red) -> Strict Reset of Green buttons!
                was_counting_green = (prev_side == "BUY") and prev_had_progress
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
                signal_date = None
                just_crossed_on_prev_bar = False
                action_today = "RESET_TO_RED" if was_counting_green else "WATCH_KDJ_RED"

            # Check if a new MACD Red Dot occurs today while KDJ is Red
            if macd_red_dot:
                b2 = True
                b3 = True
                bar_count = 1
                macd_dot_date = date_str
                b4 = False
                b5 = False
                b6 = False
                ema_cross_date = None
                signal_date = None
                just_crossed_on_prev_bar = False

                if ema_cross_down:
                    b4 = True
                    ema_cross_date = date_str
                    just_crossed_on_prev_bar = True
                    action_today = "WAIT_CONFIRM_SELL"
                else:
                    action_today = "COUNTING_SELL"

            elif b2:
                # Currently in an active SELL sequence after MACD red dot
                if not macd_bearish:
                    b2 = False
                    b3 = False
                    bar_count = 0
                    b4 = False
                    b5 = False
                    b6 = False
                    macd_dot_date = None
                    ema_cross_date = None
                    signal_date = None
                    just_crossed_on_prev_bar = False
                    action_today = "WATCH_KDJ_RED"
                elif b6:
                    if ema_bearish:
                        action_today = "HOLD_SELL"
                    else:
                        b4 = False
                        b5 = False
                        b6 = False
                        action_today = "WATCH_KDJ_RED"
                else:
                    bar_count += 1

                    if just_crossed_on_prev_bar and b4:
                        ema_dropping = (prev_ema_fast is not None) and (ema_fast_val <= prev_ema_fast)
                        if bar_count <= max_wait_bars and ema_bearish and ema_dropping:
                            b5 = True
                            b6 = True
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

        # Status description in Thai
        status_map = {
            "BUY_NOW": f"🚀 สัญญาณเข้าซื้อวันนี้! (ครบ 6 เม็ด แท่งที่ {bar_count}/{max_wait_bars})",
            "SELL_NOW": f"🚨 สัญญาณขายออกวันนี้! (ครบ 6 เม็ดแดง แท่งที่ {bar_count}/{max_wait_bars})",
            "WAIT_CONFIRM_BUY": f"👀 เตรียมซื้อ! EMA9 ตัดขึ้น EMA21 แล้ว (แท่งที่ {bar_count}/{max_wait_bars}) รอแท่งถัดไปคอนเฟิร์ม",
            "WAIT_CONFIRM_SELL": f"⚠️ เตรียมขาย! EMA9 ตัดลง EMA21 แล้ว (แท่งที่ {bar_count}/{max_wait_bars}) รอแท่งถัดไปคอนเฟิร์ม",
            "COUNTING_BUY": f"⏳ นับแท่งที่ {bar_count}/{max_wait_bars} จากจุดเขียว MACD (รอ EMA9 ตัดขึ้น EMA21)",
            "COUNTING_SELL": f"⏳ นับแท่งที่ {bar_count}/{max_wait_bars} จากจุดแดง MACD (รอ EMA9 ตัดลง EMA21)",
            "HOLD_BUY": "✅ ครบ 6 เม็ดเขียวแล้ว (กำลังรันเทรนด์ขาขึ้น)",
            "HOLD_SELL": "🔻 ครบ 6 เม็ดแดงแล้ว (อยู่ในเทรนด์ขาลง)",
            "RESET_TO_RED": "🔄 KDJ พลิกเป็นสีแดง -> Reset เม็ดเขียว เริ่มนับเม็ด 1 ฝั่งขาย",
            "RESET_TO_GREEN": "🔄 KDJ พลิกเป็นสีเขียว -> Reset เม็ดแดง เริ่มนับเม็ด 1 ฝั่งซื้อ",
            "WATCH_KDJ_GREEN": "🟢 KDJ เขียว (เม็ด 1) รอจุดเขียว MACD",
            "WATCH_KDJ_RED": "🔴 KDJ แดง (เม็ด 1) รอจุดแดง MACD",
        }
        status_text = status_map.get(action_today, "")

        buttons_visual = format_buttons_visual(
            side=side,
            b1=b1,
            b2=b2,
            b3=b3,
            bar_count=bar_count,
            max_bars=max_wait_bars,
            b4=b4,
            b5=b5,
            b6=b6,
        )

        states.append(
            BarState(
                date=date_str,
                close=round(close, 2),
                change_pct=round(change_pct, 2),
                side=side,
                b1_kdj=b1,
                b2_macd_dot=b2,
                b3_counting=b3,
                bar_count=bar_count,
                max_bars=max_wait_bars,
                b4_ema_cross=b4,
                b5_ema_confirm=b5,
                b6_signal=b6,
                action_today=action_today,
                status_text=status_text,
                buttons_visual=buttons_visual,
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
