"""
Calendar & Liquidity Filters for US Stock Market (Bot 1)
"""
from datetime import datetime, date
import pandas as pd


US_FIXED_HOLIDAYS_2026_2027 = {
    # 2026
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # MLK Day
    date(2026, 2, 16),  # Presidents' Day
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth
    date(2026, 7, 3),   # Independence Day (Observed)
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
    # 2027
    date(2027, 1, 1),
    date(2027, 1, 18),
    date(2027, 2, 15),
    date(2027, 3, 26),
    date(2027, 5, 31),
    date(2027, 6, 18),
    date(2027, 7, 5),
    date(2027, 9, 6),
    date(2027, 11, 25),
    date(2027, 12, 24),
}


def is_us_market_holiday(dt: datetime = None) -> bool:
    """Checks if the given date is a NYSE market holiday or weekend."""
    d = (dt or datetime.now()).date()
    # Weekends (Saturday=5, Sunday=6)
    if d.weekday() >= 5:
        return True
    return d in US_FIXED_HOLIDAYS_2026_2027


def passes_us_liquidity_filter(df: pd.DataFrame, min_volume: float = 500000, min_price: float = 5.0) -> bool:
    """Checks if a stock meets 20-day liquidity and penny stock threshold."""
    if len(df) < 20:
        return False
    curr_close = float(df["Close"].iloc[-1])
    if curr_close < min_price:
        return False
    avg_vol_20 = float(df["Volume"].iloc[-20:].mean())
    return avg_vol_20 >= min_volume
