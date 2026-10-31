"""
Risk-Based Position Sizing & Stop Loss Calculator (Step [3/4])
- Calculates Stop Loss = min(Intraday Low, Prior Bar Low) - Dynamic Buffer
- Calculates 1R Risk per share = Entry - SL
- Portfolio Risk Budget: Equity * Risk% (e.g. $10,000 * 0.5% = $50)
- Position Size (Shares) = Budget / 1R
- Calculates R-Multiple Targets: 1R, 2R, 3R, 5R
- Guardrail: Max Capital Allocation (e.g. 20% cap)
- Floor Inversion Elimination: rejects trades if raw_shares < 1 or capital cap exceeded
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
    is_valid: bool = True
    is_capped: bool = False
    warning_note: str = ""
    invalid_reason: str = ""


class RiskManager:
    def __init__(self, config: Dict):
        self.config = config
        self.portfolio_equity = float(config.get("portfolio_equity", 10000.0))
        self.risk_pct = float(config.get("risk_per_trade_pct", 0.5))
        self.max_alloc_pct = float(config.get("max_allocation_per_trade_pct", 20.0))

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

        # Stop loss is the minimum of current low and prior bar low with dynamic price-scaled buffer
        raw_sl = min(curr_low, prior_low)
        buffer = max(0.15, round(raw_sl * 0.015, 2))
        stop_loss = round(max(0.01, raw_sl - buffer), 2)

        # Risk per share (1R)
        risk_per_share = round(entry_price - stop_loss, 2)
        dollar_risk_budget = round(port_equity * (self.risk_pct / 100.0), 2)
        max_capital = port_equity * (self.max_alloc_pct / 100.0)

        is_valid = True
        is_capped = False
        warning_note = ""
        invalid_reason = ""

        # Sanity check: Ensure SL is below entry and risk_per_share > 0
        if risk_per_share <= 0:
            is_valid = False
            shares = 0
            capital_allocated = 0.0
            allocation_pct = 0.0
            risk_pct = 0.0
            invalid_reason = f"Invalid risk per share ${risk_per_share:.2f} <= 0 (Entry: ${entry_price:.2f}, SL: ${stop_loss:.2f})"
            warning_note = invalid_reason
        else:
            risk_pct = round((risk_per_share / entry_price) * 100.0, 2) if entry_price > 0 else 0.0
            raw_shares = int(dollar_risk_budget / risk_per_share)

            # Eliminate floor inversion: if budget cannot buy at least 1 share, trade is invalid
            if raw_shares < 1:
                is_valid = False
                shares = 0
                capital_allocated = 0.0
                allocation_pct = 0.0
                invalid_reason = f"Risk budget ${dollar_risk_budget:,.2f} insufficient for 1 share at SL ${stop_loss:.2f} (Risk/sh: ${risk_per_share:.2f})"
                warning_note = invalid_reason
            else:
                shares = raw_shares
                capital_allocated = round(shares * entry_price, 2)
                allocation_pct = round((capital_allocated / port_equity) * 100.0, 2) if port_equity > 0 else 0.0

                # Max Allocation Guard (20% cap)
                if entry_price > max_capital:
                    is_valid = False
                    shares = 0
                    capital_allocated = 0.0
                    allocation_pct = 0.0
                    invalid_reason = f"Stock price ${entry_price:.2f} exceeds {self.max_alloc_pct}% max capital cap (${max_capital:,.2f})"
                    warning_note = invalid_reason
                elif capital_allocated > max_capital and entry_price > 0:
                    capped_shares = int(max_capital / entry_price)
                    if capped_shares < 1:
                        is_valid = False
                        shares = 0
                        capital_allocated = 0.0
                        allocation_pct = 0.0
                        invalid_reason = f"Capped shares < 1 under {self.max_alloc_pct}% max capital cap (${max_capital:,.2f})"
                        warning_note = invalid_reason
                    else:
                        shares = capped_shares
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
            is_valid=is_valid,
            is_capped=is_capped,
            warning_note=warning_note,
            invalid_reason=invalid_reason,
        )
