"""
Exit Tracker for Bot 6 (Thai SET Hybrid Trend Scanner):
1. Stop Loss Hit -> Full Exit (-1R or Breakeven)
2. Target 3R Hit -> Partial Exit (50% or 100% for 1 Board Lot) + Move SL to Breakeven
3. Target 5R Hit -> Partial Exit 50% of remaining runner
4. Trailing EMA Stop -> Trailing Stop on Daily EMA 9/21 for final runner shares
"""
from typing import Dict, List, Tuple
import pandas as pd
from .indicators import compute_ema, compute_macd


class ThaiHybridExitTracker:
    def __init__(self, config: Dict):
        self.config = config
        self.tp1_ratio = float(config.get("tp1_sell_ratio", 0.5))
        self.board_lot = int(config.get("board_lot_size", 100))
        self.trailing_ema = int(config.get("trailing_ema", 9))

    def evaluate_position(self, position: Dict, df: pd.DataFrame) -> Tuple[Dict, List[Dict]]:
        actions = []
        pos = dict(position)
        tk = pos.get("ticker", "")

        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        curr_close = float(close.iloc[-1])
        curr_high = float(high.iloc[-1])
        curr_low = float(low.iloc[-1])
        date_str = str(df.index[-1])[:10]

        ema_trail = float(compute_ema(close, self.trailing_ema).iloc[-1])
        ema50 = float(compute_ema(close, 50).iloc[-1])
        macd, _, _ = compute_macd(close)
        m_val = float(macd.iloc[-1])

        entry = float(pos["entry_price"])
        sl = float(pos["current_sl"])
        risk_per_share = float(pos["risk_per_share"])
        curr_shares = int(pos["current_shares"])
        initial_shares = int(pos.get("initial_shares", pos.get("shares", curr_shares)))
        target_3r = float(pos["target_3r"])
        target_5r = float(pos.get("target_5r", round(entry + 5.0 * risk_per_share, 2)))
        tp1_hit = bool(pos.get("tp1_hit", False))
        tp2_hit = bool(pos.get("tp2_hit", False))

        pos["current_price"] = round(curr_close, 2)
        pos["unrealized_pnl"] = round((curr_close - entry) * curr_shares, 2)

        # -----------------------------------------------------------------
        # 1. Stop Loss Hit Check
        # -----------------------------------------------------------------
        if curr_low <= sl or curr_close <= sl:
            exit_price = min(curr_close, sl)
            pnl = round((exit_price - entry) * curr_shares, 2)
            pos["status"] = "CLOSED_SL"
            pos["exit_price"] = exit_price
            pos["exit_date"] = date_str
            pos["exit_reason"] = "Stop Loss Hit (-1R)" if not tp1_hit else "Breakeven Stop Loss Hit"
            pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
            pos["current_shares"] = 0

            actions.append({
                "type": "STOP_LOSS",
                "ticker": tk,
                "shares_sold": curr_shares,
                "price": exit_price,
                "pnl": pnl,
                "message": f"🛑 {tk} แตะจุด Stop Loss ที่ {exit_price:.2f} ฿ (ปิดสถานะ {curr_shares:,} หุ้น | PnL: {pnl:+,.0f} ฿)"
            })
            self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
            return pos, actions

        # -----------------------------------------------------------------
        # 2. Target 3R Hit (TP1)
        # -----------------------------------------------------------------
        if not tp1_hit and curr_high >= target_3r and curr_shares > 0:
            pos["tp1_hit"] = True
            pos["current_sl"] = round(max(pos["current_sl"], entry), 2)  # Breakeven

            if curr_shares <= self.board_lot:
                # 100 shares (1 Board Lot) -> Full exit at 3R to avoid odd lots
                sell_qty = curr_shares
                pnl = round((target_3r - entry) * sell_qty, 2)
                pos["status"] = "CLOSED_TP1"
                pos["exit_price"] = target_3r
                pos["exit_date"] = date_str
                pos["exit_reason"] = "Target 3R Hit (100% Exit for 1 Board Lot)"
                pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
                pos["current_shares"] = 0
                curr_shares = 0

                actions.append({
                    "type": "TP1_3R_FULL",
                    "ticker": tk,
                    "shares_sold": sell_qty,
                    "price": target_3r,
                    "pnl": pnl,
                    "message": (
                        f"🎯 {tk} ถึงเป้าหมาย 3R ที่ {target_3r:.2f} ฿!\n"
                        f"• ปิดทำกำไร 100% ({sell_qty:,} หุ้น) ล็อคกำไร +{pnl:,.0f} ฿ (+3.0R)"
                    )
                })
                self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
                return pos, actions
            else:
                # >= 200 shares -> Sell 50% in multiples of 100 shares, keep runner
                raw_sell = int(curr_shares * self.tp1_ratio)
                sell_qty = (raw_sell // self.board_lot) * self.board_lot
                if sell_qty == 0:
                    sell_qty = self.board_lot
                if sell_qty >= curr_shares:
                    sell_qty = curr_shares - self.board_lot

                pnl = round((target_3r - entry) * sell_qty, 2)
                pos["current_shares"] = curr_shares - sell_qty
                pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
                curr_shares = pos["current_shares"]

                actions.append({
                    "type": "TP1_3R",
                    "ticker": tk,
                    "shares_sold": sell_qty,
                    "price": target_3r,
                    "pnl": pnl,
                    "message": (
                        f"🎯 {tk} ถึงเป้าหมาย 3R ที่ {target_3r:.2f} ฿!\n"
                        f"• ขายทำกำไร 50% ({sell_qty:,} หุ้น) ล็อคกำไร +{pnl:,.0f} ฿\n"
                        f"• ยก Stop Loss บังทุนมาที่ {pos['current_sl']:.2f} ฿ (ไม้นี้ไร้ความเสี่ยงแล้ว 100%!)"
                    )
                })

        # -----------------------------------------------------------------
        # 3. Target 5R Hit (TP2)
        # -----------------------------------------------------------------
        if pos.get("tp1_hit", False) and not tp2_hit and curr_high >= target_5r and curr_shares > 0:
            pos["tp2_hit"] = True

            if curr_shares <= self.board_lot:
                # Final 100 shares closed at 5R
                sell_qty = curr_shares
                pnl = round((target_5r - entry) * sell_qty, 2)
                pos["status"] = "CLOSED_TP2"
                pos["exit_price"] = target_5r
                pos["exit_date"] = date_str
                pos["exit_reason"] = "Target 5R Hit (Final Exit)"
                pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
                pos["current_shares"] = 0
                curr_shares = 0

                actions.append({
                    "type": "TP2_5R_FULL",
                    "ticker": tk,
                    "shares_sold": sell_qty,
                    "price": target_5r,
                    "pnl": pnl,
                    "message": (
                        f"🎯🎯 {tk} ถึงเป้าหมายใหญ่ 5R ที่ {target_5r:.2f} ฿!\n"
                        f"• ปิดทำกำไรไม้สุดท้าย ({sell_qty:,} หุ้น) กำไร +{pnl:,.0f} ฿ (+5.0R)"
                    )
                })
                self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
                return pos, actions
            else:
                # Sell 50% of remaining runner
                raw_sell = (curr_shares // 2 // self.board_lot) * self.board_lot
                sell_qty = max(self.board_lot, raw_sell)
                if sell_qty >= curr_shares:
                    sell_qty = curr_shares - self.board_lot

                pnl = round((target_5r - entry) * sell_qty, 2)
                pos["current_shares"] = curr_shares - sell_qty
                pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
                curr_shares = pos["current_shares"]

                actions.append({
                    "type": "TP2_5R",
                    "ticker": tk,
                    "shares_sold": sell_qty,
                    "price": target_5r,
                    "pnl": pnl,
                    "message": (
                        f"🎯🎯 {tk} ถึงเป้าหมายใหญ่ 5R ที่ {target_5r:.2f} ฿!\n"
                        f"• ขายทำกำไรก้อนสอง ({sell_qty:,} หุ้น) กำไร +{pnl:,.0f} ฿\n"
                        f"• หุ้นที่เหลือ {curr_shares:,} หุ้น ปล่อยรันต่อด้วย Daily EMA {self.trailing_ema}"
                    )
                })

        # -----------------------------------------------------------------
        # 4. Trailing EMA Stop for Remaining Runner
        # -----------------------------------------------------------------
        if pos.get("tp1_hit", False) and curr_shares > 0 and (curr_close < ema_trail or curr_close < ema50 or m_val < 0):
            pnl = round((curr_close - entry) * curr_shares, 2)
            pos["status"] = "CLOSED_TRAILING"
            pos["exit_price"] = curr_close
            pos["exit_date"] = date_str
            pos["exit_reason"] = f"Trailing Stop Exit (Closed below EMA {self.trailing_ema})"
            pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
            pos["current_shares"] = 0

            actions.append({
                "type": "TRAILING_EXIT",
                "ticker": tk,
                "shares_sold": curr_shares,
                "price": curr_close,
                "pnl": pnl,
                "message": (
                    f"📉 {tk} แท่งวันปิดหลุด Daily EMA {self.trailing_ema} ที่ {curr_close:.2f} ฿\n"
                    f"• ปิดทำกำไรหุ้นส่วนรันเทรนด์ {curr_shares:,} หุ้น (+{pnl:,.0f} ฿)"
                )
            })

        self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
        return pos, actions

    def _update_metrics(self, pos: Dict, entry: float, risk_per_share: float, initial_shares: int, curr_close: float):
        """Calculates true blended R-multiple and percentage returns."""
        initial_dollar_risk = initial_shares * risk_per_share
        tot_realized = float(pos.get("total_realized_pnl", 0.0))
        rem_shares = int(pos.get("current_shares", 0))

        if rem_shares > 0:
            unrealized = round((curr_close - entry) * rem_shares, 2)
            pos["unrealized_pnl"] = unrealized
            blended_pnl = tot_realized + unrealized
        else:
            pos["unrealized_pnl"] = 0.0
            blended_pnl = tot_realized

        pos["current_r"] = round(blended_pnl / initial_dollar_risk, 2) if initial_dollar_risk > 0 else 0.0
        pos["total_pnl"] = round(blended_pnl, 2)
        pos["current_price"] = round(curr_close, 2)
