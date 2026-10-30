"""
Risk Management & Board Lot Enforcement for Bot 5 Thai Hybrid
Portfolio: 1,000,000 THB | Risk: 0.5% (5,000 THB) | Max Cap: 20% (200,000 THB) | Board Lot: 100
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
        equity: Optional[float] = None
    ) -> ThaiTradePlan:
        port_equity = equity if equity is not None else self.portfolio_equity
        raw_low = min(curr_low, prior_low)
        tick = get_thai_tick_size(raw_low)
        stop_loss = round(max(0.01, raw_low - tick), 2)

        risk_per_share = round(entry_price - stop_loss, 2)
        if risk_per_share <= 0:
            risk_per_share = round(entry_price * 0.024, 2)
            stop_loss = round(entry_price - risk_per_share, 2)

        risk_pct = round((risk_per_share / entry_price) * 100.0, 2)
        baht_risk_budget = round(port_equity * (self.risk_pct / 100.0), 2)
        raw_shares = int(baht_risk_budget / risk_per_share) if risk_per_share > 0 else 0
        board_lot_shares = (raw_shares // self.board_lot) * self.board_lot
        shares = max(self.board_lot, board_lot_shares)

        capital_allocated = round(shares * entry_price, 2)
        allocation_pct = round((capital_allocated / port_equity) * 100.0, 2)

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
                warning_note = f"จำกัดขนาดไม้ไม่เกิน {self.max_alloc_pct}% ({max_capital:,.0f} ฿) ความเสี่ยงจริง: {actual_risk:,.0f} ฿"

        target_3r = round(entry_price + (3.0 * risk_per_share), 2)
        target_5r = round(entry_price + (5.0 * risk_per_share), 2)

        return ThaiTradePlan(
            ticker=ticker,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_per_share=risk_per_share,
            risk_pct=risk_pct,
            portfolio_equity=port_equity,
            risk_budget_pct=self.risk_pct,
            dollar_risk_budget=baht_risk_budget,
            shares=shares,
            capital_allocated=capital_allocated,
            allocation_pct=allocation_pct,
            target_3r=target_3r,
            target_5r=target_5r,
            is_capped=is_capped,
            warning_note=warning_note
        )
