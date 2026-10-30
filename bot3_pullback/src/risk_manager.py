"""
Risk-Based Position Sizing & Stop Loss Calculator (Step [3/4])
- Calculates Stop Loss = min(Intraday Low, Prior Bar Low)
- Calculates 1R Risk per share = Entry - SL
- Portfolio Risk Budget: Equity * Risk% (e.g. $10,000 * 0.5% = $50)
- Position Size (Shares) = Budget / 1R
- Calculates R-Multiple Targets: 1R, 2R, 3R, 5R
- Guardrail: Max Capital Allocation (e.g. 25% cap)
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class TradePlan:
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


class RiskManager:
    def __init__(self, config: Dict):
        self.config = config
        self.portfolio_equity = float(config.get("portfolio_equity", 10000.0))
        self.risk_pct = float(config.get("risk_per_trade_pct", 0.5))
        self.max_alloc_pct = float(config.get("max_allocation_per_trade_pct", 25.0))

    def calculate_trade_plan(
        self,
        ticker: str,
        entry_price: float,
        curr_low: float,
        prior_low: float,
        equity: Optional[float] = None,
    ) -> TradePlan:
        """
        Calculate complete risk plan and position sizing based on Step [3/4].
        """
        port_equity = equity if equity is not None else self.portfolio_equity

        # Stop loss is the minimum of current low and prior bar low (minus $0.02 buffer)
        raw_sl = min(curr_low, prior_low)
        # Apply tiny buffer so we don't get stopped out by exact double-bottom
        stop_loss = round(max(0.01, raw_sl - 0.02), 2)

        # Risk per share (1R)
        risk_per_share = round(entry_price - stop_loss, 2)

        # Sanity check: Ensure SL is below entry and at least 0.8% of price
        if risk_per_share <= 0:
            risk_per_share = round(entry_price * 0.02, 2)
            stop_loss = round(entry_price - risk_per_share, 2)

        risk_pct = round((risk_per_share / entry_price) * 100.0, 2)

        # Dollar Risk Budget (e.g. $10,000 * 0.5% = $50.00)
        dollar_risk_budget = round(port_equity * (self.risk_pct / 100.0), 2)

        # Exact shares = Dollar Risk / Risk per share
        raw_shares = int(dollar_risk_budget / risk_per_share) if risk_per_share > 0 else 0
        shares = max(1, raw_shares) if entry_price <= port_equity else 0

        # Capital allocated
        capital_allocated = round(shares * entry_price, 2)
        allocation_pct = round((capital_allocated / port_equity) * 100.0, 2) if port_equity > 0 else 0.0

        # Max Allocation Guard (e.g. max 25% of portfolio in one stock)
        max_capital = port_equity * (self.max_alloc_pct / 100.0)
        is_capped = False
        warning_note = ""

        if capital_allocated > max_capital and entry_price > 0:
            capped_shares = int(max_capital / entry_price)
            if capped_shares < shares:
                shares = max(1, capped_shares)
                capital_allocated = round(shares * entry_price, 2)
                allocation_pct = round((capital_allocated / port_equity) * 100.0, 2)
                is_capped = True
                actual_risk = round(shares * risk_per_share, 2)
                warning_note = (
                    f"จำกัดขนาดไม้ไม่เกิน {self.max_alloc_pct}% ของพอร์ต "
                    f"(ความเสี่ยงจริงลดลงเหลือ ${actual_risk} หรือ {round(actual_risk/port_equity*100, 2)}%)"
                )

        # R-Multiple targets
        target_1r = round(entry_price + (1.0 * risk_per_share), 2)
        target_2r = round(entry_price + (2.0 * risk_per_share), 2)
        target_3r = round(entry_price + (3.0 * risk_per_share), 2)
        target_5r = round(entry_price + (5.0 * risk_per_share), 2)

        return TradePlan(
            ticker=ticker,
            entry_price=round(entry_price, 2),
            stop_loss=stop_loss,
            risk_per_share=risk_per_share,
            risk_pct=risk_pct,
            portfolio_equity=round(port_equity, 2),
            risk_budget_pct=self.risk_pct,
            dollar_risk_budget=dollar_risk_budget,
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
