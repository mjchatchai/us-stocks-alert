"""
Risk Management & Position Sizing for Bot 5 (US Macro Trend Hybrid Scanner)
Portfolio: $10,000 | Risk: 0.5% ($50) | Max Cap: 20% ($2,000)
"""
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class USTradePlan:
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
    is_valid: bool = True
    is_capped: bool = False
    warning_note: str = ""


class USRiskManager:
    def __init__(self, config: Dict):
        self.config = config
        self.portfolio_equity = float(config.get("portfolio_equity", 10000.0))
        self.risk_pct = float(config.get("risk_per_trade_pct", 0.5))
        self.max_alloc_pct = float(config.get("max_allocation_per_trade_pct", 20.0))
        self.board_lot = int(config.get("board_lot_size", 1))

    def calculate_trade_plan(
        self,
        ticker: str,
        entry_price: float,
        curr_low: float,
        prior_low: float,
        equity: Optional[float] = None
    ) -> USTradePlan:
        port_equity = equity if equity is not None else self.portfolio_equity
        raw_low = min(curr_low, prior_low)

        # 1. Volatility-scaled buffer (at least $0.15 or 1.5% of price, giving room to high-dollar stocks)
        buffer = max(0.15, round(raw_low * 0.015, 2))
        stop_loss = round(max(0.01, raw_low - buffer), 2)

        risk_per_share = round(entry_price - stop_loss, 2)
        if risk_per_share <= 0:
            risk_per_share = round(max(0.01, entry_price * 0.025), 2)
            stop_loss = round(entry_price - risk_per_share, 2)

        risk_pct = round((risk_per_share / entry_price) * 100.0, 2) if entry_price > 0 else 0.0
        dollar_risk_budget = round(port_equity * (self.risk_pct / 100.0), 2)

        # 2. Risk Budget Sizing
        raw_shares = int(dollar_risk_budget / risk_per_share) if risk_per_share > 0 else 0
        is_valid = True
        is_capped = False
        warning_note = ""

        if raw_shares < 1:
            is_valid = False
            shares = 0
            capital_allocated = 0.0
            allocation_pct = 0.0
            warning_note = f"Risk budget ${dollar_risk_budget:.0f} insufficient for 1 share at SL ${stop_loss:.2f}"
        else:
            shares = raw_shares
            capital_allocated = round(shares * entry_price, 2)
            allocation_pct = round((capital_allocated / port_equity) * 100.0, 2)

            # 3. 20% Max Capital Allocation Cap
            max_capital = port_equity * (self.max_alloc_pct / 100.0)
            if capital_allocated > max_capital and entry_price > 0:
                capped_shares = int(max_capital / entry_price)
                if capped_shares < 1:
                    is_valid = False
                    shares = 0
                    capital_allocated = 0.0
                    allocation_pct = 0.0
                    warning_note = f"Stock price ${entry_price:.2f} exceeds {self.max_alloc_pct}% max capital cap (${max_capital:,.0f})"
                else:
                    shares = capped_shares
                    capital_allocated = round(shares * entry_price, 2)
                    allocation_pct = round((capital_allocated / port_equity) * 100.0, 2)
                    is_capped = True
                    actual_risk = round(shares * risk_per_share, 2)
                    warning_note = f"Cap at {self.max_alloc_pct}% (${max_capital:,.0f}). Actual risk: ${actual_risk:,.0f}"

        # 4. Profit Targets
        target_3r = round(entry_price + (3.0 * risk_per_share), 2)
        target_5r = round(entry_price + (5.0 * risk_per_share), 2)

        return USTradePlan(
            ticker=ticker,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_per_share=risk_per_share,
            risk_pct=risk_pct,
            portfolio_equity=port_equity,
            risk_budget_pct=self.risk_pct,
            dollar_risk_budget=dollar_risk_budget,
            shares=shares,
            capital_allocated=capital_allocated,
            allocation_pct=allocation_pct,
            target_3r=target_3r,
            target_5r=target_5r,
            is_valid=is_valid,
            is_capped=is_capped,
            warning_note=warning_note
        )
