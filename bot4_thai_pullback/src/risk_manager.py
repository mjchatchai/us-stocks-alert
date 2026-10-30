"""
Risk-Based Position Sizing for Thai Stocks (Step [3/4])
Adapted for 1,000,000 THB Portfolio & SET Rules:
- Enforces Board Lot: Multiples of 100 shares
- Official SET Tick Size buffer for Stop Loss
- Portfolio Equity: 1,000,000 THB (Risk 0.5% = 5,000 THB)
- Max Capital Cap: 20% (200,000 THB) per stock
- Targets: 1R, 2R, 3R, 5R
"""

from dataclasses import dataclass
from typing import Dict, Optional
from .indicators import get_thai_tick_size


@dataclass
class ThaiTradePlan:
    ticker: str
    entry_price: float
    stop_loss: float
    risk_per_share: float
    risk_pct: float
    portfolio_equity: float
    risk_budget_pct: float
    dollar_risk_budget: float
    shares: int
    capital_allocated: float
    allocation_pct: float
    target_1r: float
    target_2r: float
    target_3r: float
    target_5r: float
    is_capped: bool = False
    warning_note: str = ""


class ThaiRiskManager:
    def __init__(self, config: Dict):
        self.config = config
        self.portfolio_equity = float(config.get("portfolio_equity", 1000000.0))
        self.risk_pct = float(config.get("risk_per_trade_pct", 0.5))
        self.max_alloc_pct = float(config.get("max_allocation_per_trade_pct", 20.0))
        self.board_lot = int(config.get("board_lot_size", 100))

    def calculate_trade_plan(
        self,
        ticker: str,
        entry_price: float,
        curr_low: float,
        prior_low: float,
        equity: Optional[float] = None,
    ) -> ThaiTradePlan:
        """Calculate position sizing and risk management plan for Thai stock."""
        port_equity = equity if equity is not None else self.portfolio_equity

        # Stop loss: min low minus 1-2 ticks based on SET tick size
        raw_low = min(curr_low, prior_low)
        tick = get_thai_tick_size(raw_low)
        stop_loss = round(max(0.01, raw_low - tick), 2)

        risk_per_share = round(entry_price - stop_loss, 2)
        if risk_per_share <= 0:
            risk_per_share = round(entry_price * 0.02, 2)
            stop_loss = round(entry_price - risk_per_share, 2)

        risk_pct = round((risk_per_share / entry_price) * 100.0, 2)

        # Risk budget in Baht (e.g. 1,000,000 * 0.5% = 5,000 Baht)
        baht_risk_budget = round(port_equity * (self.risk_pct / 100.0), 2)

        # Raw shares count
        raw_shares = int(baht_risk_budget / risk_per_share) if risk_per_share > 0 else 0

        # Enforce Board Lot (multiples of 100 shares)
        board_lot_shares = (raw_shares // self.board_lot) * self.board_lot
        shares = max(self.board_lot, board_lot_shares) if entry_price * self.board_lot <= port_equity else 0

        # Capital allocated in Baht
        capital_allocated = round(shares * entry_price, 2)
        allocation_pct = round((capital_allocated / port_equity) * 100.0, 2) if port_equity > 0 else 0.0

        # Max Allocation Guard (e.g. max 20% = 200,000 Baht)
        max_capital = port_equity * (self.max_alloc_pct / 100.0)
        is_capped = False
        warning_note = ""

        if capital_allocated > max_capital and entry_price > 0:
            capped_raw = int(max_capital / entry_price)
            capped_shares = (capped_raw // self.board_lot) * self.board_lot
            if capped_shares < shares:
                shares = max(self.board_lot, capped_shares)
                capital_allocated = round(shares * entry_price, 2)
                allocation_pct = round((capital_allocated / port_equity) * 100.0, 2)
                is_capped = True
                actual_risk = round(shares * risk_per_share, 2)
                warning_note = (
                    f"จำกัดขนาดไม้ไม่เกิน {self.max_alloc_pct}% ({max_capital:,.0f} บาท) "
                    f"ความเสี่ยงจริงปรับเป็น {actual_risk:,.0f} บาท ({round(actual_risk/port_equity*100, 2)}%)"
                )

        target_1r = round(entry_price + (1.0 * risk_per_share), 2)
        target_2r = round(entry_price + (2.0 * risk_per_share), 2)
        target_3r = round(entry_price + (3.0 * risk_per_share), 2)
        target_5r = round(entry_price + (5.0 * risk_per_share), 2)

        return ThaiTradePlan(
            ticker=ticker,
            entry_price=round(entry_price, 2),
            stop_loss=stop_loss,
            risk_per_share=risk_per_share,
            risk_pct=risk_pct,
            portfolio_equity=round(port_equity, 2),
            risk_budget_pct=self.risk_pct,
            dollar_risk_budget=baht_risk_budget,
            shares=shares,
            capital_allocated=capital_allocated,
            allocation_pct=allocation_pct,
            target_1r=target_1r,
            target_2r=target_2r,
            target_3r=target_3r,
            target_5r=target_5r,
            is_capped=is_capped,
            warning_note=warning_note,
        )
