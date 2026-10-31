"""
Risk Management & Board Lot Enforcement for Bot 6 (Thai SET Hybrid Trend Scanner)
Portfolio: 1,000,000 THB | Risk: 0.5% (5,000 THB) | Max Cap: 20% (200,000 THB) | Board Lot: 100 shares
"""
from dataclasses import dataclass
from typing import Dict, Optional
from .indicators import get_thai_tick_size, step_tick_down, round_to_set_tick


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
        equity: Optional[float] = None
    ) -> ThaiTradePlan:
        port_equity = equity if equity is not None else self.portfolio_equity
        raw_low = min(curr_low, prior_low)

        # 1. Swing-low Stop Loss with boundary-aware SET tick stepping
        stop_loss = step_tick_down(raw_low)
        risk_per_share = round(entry_price - stop_loss, 2)

        if risk_per_share <= 0:
            risk_per_share = round(max(0.01, entry_price * 0.024), 2)
            stop_loss = step_tick_down(round_to_set_tick(entry_price - risk_per_share, mode="down"))
            risk_per_share = round(entry_price - stop_loss, 2)

        risk_pct = round((risk_per_share / entry_price) * 100.0, 2) if entry_price > 0 else 0.0
        baht_risk_budget = round(port_equity * (self.risk_pct / 100.0), 2)

        # 2. Risk Budget Sizing quantized to 100-share Board Lot
        raw_shares = int(baht_risk_budget / risk_per_share) if risk_per_share > 0 else 0
        board_lot_shares = (raw_shares // self.board_lot) * self.board_lot

        is_valid = True
        is_capped = False
        warning_note = ""

        # Strict guard: If risk budget cannot afford even 1 board lot (100 shares), reject setup
        if board_lot_shares < self.board_lot:
            is_valid = False
            shares = 0
            capital_allocated = 0.0
            allocation_pct = 0.0
            warning_note = f"งบความเสี่ยง {self.risk_pct}% ({baht_risk_budget:,.0f} ฿) ไม่พอซื้อ 1 Board Lot ({self.board_lot} หุ้น)"
        else:
            shares = board_lot_shares
            capital_allocated = round(shares * entry_price, 2)
            allocation_pct = round((capital_allocated / port_equity) * 100.0, 2)

            # 3. 20% Max Capital Allocation Cap
            max_capital = port_equity * (self.max_alloc_pct / 100.0)
            if capital_allocated > max_capital and entry_price > 0:
                capped_raw = int(max_capital / entry_price)
                capped_shares = (capped_raw // self.board_lot) * self.board_lot

                if capped_shares < self.board_lot:
                    is_valid = False
                    shares = 0
                    capital_allocated = 0.0
                    allocation_pct = 0.0
                    warning_note = f"ราคาหุ้นเกินวงเงิน {self.max_alloc_pct}% ({max_capital:,.0f} ฿) สำหรับ 1 Board Lot"
                else:
                    shares = capped_shares
                    capital_allocated = round(shares * entry_price, 2)
                    allocation_pct = round((capital_allocated / port_equity) * 100.0, 2)
                    is_capped = True
                    actual_risk = round(shares * risk_per_share, 2)
                    warning_note = f"จำกัดขนาดไม้ไม่เกิน {self.max_alloc_pct}% ({max_capital:,.0f} ฿) ความเสี่ยงจริง: {actual_risk:,.0f} ฿"

        # 4. Profit Targets snapped to legal SET ticks
        target_3r = round_to_set_tick(entry_price + (3.0 * risk_per_share), mode="nearest")
        target_5r = round_to_set_tick(entry_price + (5.0 * risk_per_share), mode="nearest")

        if target_5r <= target_3r:
            tick_size = get_thai_tick_size(target_3r)
            target_5r = round_to_set_tick(target_3r + tick_size * 2, mode="up")

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
            is_valid=is_valid,
            is_capped=is_capped,
            warning_note=warning_note
        )
