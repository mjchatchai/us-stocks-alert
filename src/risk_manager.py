"""
Risk Management Engine for US 6-Button Strategy (Bot 1):
1. Stop Loss: Swing Low (10 bars) with ATR buffer, bounded between 2% and 8%.
2. Position Sizing: Risk 0.5% of $10,000 portfolio = $50 risk budget.
3. Max Position Cap: 20% of portfolio ($2,000 max capital per stock).
4. Targets: Target 3R (+3.0R) and Target 5R (+5.0R).
"""
from typing import Dict, Optional
import pandas as pd


class US6ButtonRiskManager:
    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.total_capital = float(cfg.get("total_capital", 10000.0))
        self.risk_pct = float(cfg.get("risk_per_trade_pct", 0.005))  # 0.5%
        self.max_cap_pct = float(cfg.get("max_position_capital_pct", 0.20))  # 20%
        self.trailing_ema = int(cfg.get("trailing_ema", 21))

    def calculate_position(self, ticker: str, df: pd.DataFrame, entry_price: float) -> Optional[Dict]:
        if entry_price <= 0 or len(df) < 15:
            return None

        # 1. Calculate Initial Stop Loss (1R)
        low_10 = float(df["Low"].iloc[-10:].min())
        high = df["High"]
        low = df["Low"]
        close = df["Close"]
        prev_close = close.shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr = float(tr.ewm(span=14, adjust=False).mean().iloc[-1])
        vol_buffer = max(0.15, 0.5 * atr)

        raw_sl = low_10 - vol_buffer
        min_sl = entry_price * 0.92  # max 8% stop
        max_sl = entry_price * 0.98  # min 2% stop
        sl = round(max(min_sl, min(max_sl, raw_sl)), 2)

        risk_per_share = round(entry_price - sl, 2)
        if risk_per_share <= 0:
            sl = round(entry_price * 0.95, 2)
            risk_per_share = round(entry_price - sl, 2)

        # 2. Position Sizing
        risk_budget = self.total_capital * self.risk_pct  # $50
        max_capital = self.total_capital * self.max_cap_pct  # $2,000

        shares_by_risk = int(risk_budget / risk_per_share) if risk_per_share > 0 else 1
        shares_by_cap = int(max_capital / entry_price) if entry_price > 0 else 1

        shares = max(1, min(shares_by_risk, shares_by_cap))
        pos_capital = round(shares * entry_price, 2)

        target_3r = round(entry_price + 3.0 * risk_per_share, 2)
        target_5r = round(entry_price + 5.0 * risk_per_share, 2)

        return {
            "ticker": ticker,
            "entry_price": entry_price,
            "current_sl": sl,
            "stop_loss": sl,
            "risk_per_share": risk_per_share,
            "shares": shares,
            "current_shares": shares,
            "initial_shares": shares,
            "target_3r": target_3r,
            "target_5r": target_5r,
            "position_capital": pos_capital,
            "tp1_hit": False,
            "tp2_hit": False
        }
