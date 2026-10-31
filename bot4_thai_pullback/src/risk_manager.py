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

try:
    from .indicators import get_thai_tick_size, step_tick_down, round_to_set_tick
except ImportError:
    from indicators import get_thai_tick_size, step_tick_down, round_to_set_tick


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
    board_lots: int = 0
    capital_allocated: float = 0.0
    allocation_pct: float = 0.0
    target_1r: float = 0.0
    target_2r: float = 0.0
    target_3r: float = 0.0
    target_5r: float = 0.0
    is_valid: bool = True
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

        # Stop loss: boundary-safe SET tick stepping
        raw_low_raw = min(curr_low, prior_low)
        raw_low = round_to_set_tick(raw_low_raw, mode="down")
        stop_loss = step_tick_down(raw_low)

        risk_per_share = round(entry_price - stop_loss, 2)
        if risk_per_share <= 0:
            tick = get_thai_tick_size(entry_price)
            stop_loss = step_tick_down(round_to_set_tick(entry_price - tick * 2, mode="down"))
            risk_per_share = round(entry_price - stop_loss, 2)

        risk_pct = round((risk_per_share / entry_price) * 100.0, 2) if entry_price > 0 else 0.0

        # Risk budget in Baht (e.g. 1,000,000 * 0.5% = 5,000 Baht)
        baht_risk_budget = round(port_equity * (self.risk_pct / 100.0), 2)

        # Raw shares count
        raw_shares = int(baht_risk_budget / risk_per_share) if risk_per_share > 0 else 0

        # Enforce Board Lot (multiples of 100 shares)
        board_lot_shares = (raw_shares // self.board_lot) * self.board_lot

        is_valid = True
        is_capped = False
        warning_note = ""

        # Guard: Invalidate if risk budget cannot afford 1 Board Lot
        if board_lot_shares < self.board_lot or risk_per_share <= 0:
            is_valid = False
            shares = 0
            board_lots = 0
            capital_allocated = 0.0
            allocation_pct = 0.0
            warning_note = (
                f"งบเสี่ยง {baht_risk_budget:,.0f} ฿ ไม่พอซื้อ 1 Board Lot ({self.board_lot} หุ้น) "
                f"ที่ SL {stop_loss:.2f} ฿ (ต้องใช้งบเสี่ยง {risk_per_share * self.board_lot:,.0f} ฿)"
            )
        else:
            shares = board_lot_shares
            board_lots = shares // self.board_lot
            capital_allocated = round(shares * entry_price, 2)
            allocation_pct = round((capital_allocated / port_equity) * 100.0, 2) if port_equity > 0 else 0.0

            # Guard: 20% Max Capital Allocation Cap
            max_capital = port_equity * (self.max_alloc_pct / 100.0)
            if capital_allocated > max_capital and entry_price > 0:
                capped_raw = int(max_capital / entry_price)
                capped_shares = (capped_raw // self.board_lot) * self.board_lot
                if capped_shares < self.board_lot:
                    is_valid = False
                    shares = 0
                    board_lots = 0
                    capital_allocated = 0.0
                    allocation_pct = 0.0
                    warning_note = (
                        f"ราคาหุ้น {entry_price:.2f} ฿ ซื้อ 1 Board Lot ต้องใช้ {entry_price * self.board_lot:,.0f} ฿ "
                        f"เกินเพดาน {self.max_alloc_pct}% ({max_capital:,.0f} ฿)"
                    )
                else:
                    shares = capped_shares
                    board_lots = shares // self.board_lot
                    capital_allocated = round(shares * entry_price, 2)
                    allocation_pct = round((capital_allocated / port_equity) * 100.0, 2)
                    is_capped = True
                    actual_risk = round(shares * risk_per_share, 2)
                    warning_note = (
                        f"จำกัดขนาดไม้ไม่เกิน {self.max_alloc_pct}% ({max_capital:,.0f} ฿) "
                        f"ความเสี่ยงจริง: {actual_risk:,.0f} ฿ ({round(actual_risk / port_equity * 100, 2) if port_equity > 0 else 0.0}%)"
                    )

        # Snap all targets to legal SET ticks
        target_1r = round_to_set_tick(entry_price + (1.0 * risk_per_share), mode="nearest")
        target_2r = round_to_set_tick(entry_price + (2.0 * risk_per_share), mode="nearest")
        target_3r = round_to_set_tick(entry_price + (3.0 * risk_per_share), mode="nearest")
        target_5r = round_to_set_tick(entry_price + (5.0 * risk_per_share), mode="nearest")

        if target_5r <= target_3r:
            tick_size = get_thai_tick_size(target_3r)
            target_5r = round_to_set_tick(target_3r + tick_size * 2, mode="up")

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
            board_lots=board_lots,
            capital_allocated=capital_allocated,
            allocation_pct=allocation_pct,
            target_1r=target_1r,
            target_2r=target_2r,
            target_3r=target_3r,
            target_5r=target_5r,
            is_valid=is_valid,
            is_capped=is_capped,
            warning_note=warning_note,
        )

