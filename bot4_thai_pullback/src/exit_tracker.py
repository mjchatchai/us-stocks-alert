"""
Exit Tracker & Trade Management for Thai Stocks (Step [4/4])
- Monitors Active Positions against:
  * Stop Loss Hit (Full Exit)
  * Target 3R Hit (Partial TP 1 + Move SL to Breakeven)
  * Target 5R Hit (Partial TP 2)
  * Daily EMA 9 Trailing Stop for Runner
  * Overextended / Climax Warning
- Enforces Board Lot (100 shares multiples) on sales
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd

try:
    from .indicators import compute_ema, compute_atr, get_thai_tick_size
except ImportError:
    from indicators import compute_ema, compute_atr, get_thai_tick_size


class ThaiExitTracker:
    def __init__(self, config: Dict):
        self.config = config
        self.tp1_ratio = float(config.get("tp1_sell_ratio", 0.5))
        self.tp2_ratio = float(config.get("tp2_sell_ratio", 0.5))
        self.trailing_ema_period = int(config.get("trailing_ema", 9))
        self.overextended_pct = float(config.get("overextended_ema_threshold_pct", 12.0))
        self.board_lot = int(config.get("board_lot_size", 100))

    def evaluate_position(
        self, position: Dict, df: pd.DataFrame
    ) -> Tuple[Dict, List[Dict]]:
        """Evaluate an active Thai stock position."""
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

        ema9 = float(compute_ema(close, self.trailing_ema_period).iloc[-1])

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
        pos["unrealized_pct"] = round(((curr_close - entry) / entry) * 100.0, 2) if entry > 0 else 0.0

        # 1. Stop Loss Hit
        if curr_low <= sl or curr_close <= sl:
            exit_price = min(curr_close, sl)
            pnl = round((exit_price - entry) * curr_shares, 2)
            pos["status"] = "CLOSED_SL"
            pos["exit_price"] = exit_price
            pos["exit_date"] = date_str
            pos["exit_reason"] = "Stop Loss Hit (-1R)" if not tp1_hit else "Breakeven Stop Loss Hit"
            pos["current_shares"] = 0
            pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
            actions.append({
                "type": "STOP_LOSS",
                "ticker": tk,
                "shares_sold": curr_shares,
                "price": exit_price,
                "pnl": pnl,
                "message": f"🛑 {tk} แตะจุด Stop Loss ที่ {exit_price:.2f} บาท (ปิดสถานะ {curr_shares:,} หุ้น | PnL: {pnl:+,.0f} บาท)",
            })
            self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
            return pos, actions

        # 2. Target 3R Hit
        if not tp1_hit and curr_high >= target_3r and curr_shares > 0:
            pos["tp1_hit"] = True
            pos["current_sl"] = round(max(pos["current_sl"], entry), 2)  # Move SL to Breakeven

            if curr_shares <= self.board_lot:
                # 100 shares (1 Board Lot) -> 100% liquidation at 3R to avoid odd lots / zombie 0-shares
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
                        f"🎯 {tk} ถึงเป้าหมาย 3R ที่ {target_3r:.2f} บาท!\n"
                        f"• ปิดทำกำไร 100% ({sell_qty:,} หุ้น) ล็อคกำไร +{pnl:,.0f} บาท (+3.0R)"
                    ),
                })
                self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
                return pos, actions
            else:
                raw_sell = int(curr_shares * self.tp1_ratio)
                sell_qty = (raw_sell // self.board_lot) * self.board_lot
                if sell_qty == 0:
                    sell_qty = self.board_lot
                if sell_qty >= curr_shares:
                    sell_qty = curr_shares - self.board_lot  # Guarantee at least 1 runner board lot

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
                    "new_sl": pos["current_sl"],
                    "remaining_shares": curr_shares,
                    "message": (
                        f"🎯 {tk} ถึงเป้าหมาย 3R ที่ {target_3r:.2f} บาท!\n"
                        f"• ขายทำกำไร 50% ({sell_qty:,} หุ้น) กำไร +{pnl:,.0f} บาท\n"
                        f"• เลื่อน Stop Loss บังทุนมาที่ {pos['current_sl']:.2f} บาท (พอร์ตไร้ความเสี่ยงแล้ว!)"
                    ),
                })

        # 3. Target 5R Hit
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
                        f"🎯🎯 {tk} ถึงเป้าหมายใหญ่ 5R ที่ {target_5r:.2f} บาท!\n"
                        f"• ปิดทำกำไรไม้สุดท้าย ({sell_qty:,} หุ้น) กำไร +{pnl:,.0f} บาท (+5.0R)"
                    ),
                })
                self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
                return pos, actions
            else:
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
                    "remaining_shares": curr_shares,
                    "message": (
                        f"🎯🎯 {tk} ถึงเป้าหมายใหญ่ 5R ที่ {target_5r:.2f} บาท!\n"
                        f"• ขายทำกำไรก้อนสอง ({sell_qty:,} หุ้น) กำไร +{pnl:,.0f} บาท\n"
                        f"• หุ้นที่เหลือ {curr_shares:,} หุ้น ปล่อยรันต่อด้วย Daily EMA {self.trailing_ema_period}"
                    ),
                })

        # 4. Trailing EMA Stop for Runner
        if curr_shares > 0 and pos.get("tp1_hit", False) and curr_close < ema9:
            pnl = round((curr_close - entry) * curr_shares, 2)
            pos["status"] = "CLOSED_RUNNER"
            pos["exit_price"] = curr_close
            pos["exit_date"] = date_str
            pos["exit_reason"] = f"Closed below EMA {self.trailing_ema_period} ({ema9:.2f})"
            pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
            pos["current_shares"] = 0

            actions.append({
                "type": "TRAILING_EMA9_EXIT",
                "ticker": tk,
                "shares_sold": curr_shares,
                "price": curr_close,
                "pnl": pnl,
                "message": (
                    f"📉 {tk} แท่งวันปิดหลุด Daily EMA {self.trailing_ema_period} ที่ {curr_close:.2f} บาท\n"
                    f"• ปิดทำกำไรหุ้นส่วนที่เหลือ {curr_shares:,} หุ้น (+{pnl:,.0f} บาท)"
                ),
            })
            self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
            return pos, actions

        # 5. Overextension Warning
        dist_ema9_pct = ((curr_close - ema9) / ema9) * 100.0 if ema9 > 0 else 0.0
        pos["dist_ema9_pct"] = round(dist_ema9_pct, 1)

        if dist_ema9_pct >= self.overextended_pct and curr_shares > 0:
            actions.append({
                "type": "OVEREXTENDED_WARNING",
                "ticker": tk,
                "dist_pct": round(dist_ema9_pct, 1),
                "message": (
                    f"⚡ {tk} ราคาพุ่งแรงและอยู่ห่าง Daily EMA {self.trailing_ema_period} ถึง +{dist_ema9_pct:.1f}%\n"
                    f"💡 แนะนำ: ทยอยแบ่งขายล็อคกำไรเพิ่ม ป้องกันการย่อตัวแรง"
                ),
            })

        self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
        return pos, actions

    def _update_metrics(
        self,
        pos: Dict,
        entry: float,
        risk_per_share: float,
        initial_shares: int,
        curr_close: float,
    ):
        """Calculates true cumulative blended R-multiple and percentage returns."""
        initial_dollar_risk = initial_shares * risk_per_share
        tot_realized = float(pos.get("total_realized_pnl", 0.0))
        rem_shares = int(pos.get("current_shares", 0))

        if rem_shares > 0:
            unrealized = round((curr_close - entry) * rem_shares, 2)
            pos["unrealized_pnl"] = unrealized
            pos["unrealized_pct"] = (
                round(((curr_close - entry) / entry) * 100.0, 2) if entry > 0 else 0.0
            )
            blended_pnl = tot_realized + unrealized
        else:
            pos["unrealized_pnl"] = 0.0
            pos["unrealized_pct"] = 0.0
            blended_pnl = tot_realized

        pos["current_r"] = (
            round(blended_pnl / initial_dollar_risk, 2)
            if initial_dollar_risk > 0
            else 0.0
        )
        pos["total_pnl"] = round(blended_pnl, 2)
        pos["current_price"] = round(curr_close, 2)

