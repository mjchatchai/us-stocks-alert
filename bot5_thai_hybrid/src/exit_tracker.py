"""
Exit Tracker for Bot 6 (Thai SET Hybrid Trend Scanner):
1. Stop Loss Hit (with ATO Opening Gap-Down Execution) -> Full Exit (-1R or Breakeven)
2. Intermediate Breakeven Ratchet (+1.5R) -> Moves SL to Entry before TP1 to eliminate profit surrender
3. Target TP1 Hit -> Partial Exit (50% in 100-share lots) OR Configurable Single-Lot Policy
   ("trail_at_tp1" locks +1.5R SL and rides runner; "take_profit_tp1" exits 100%)
4. Target TP2 Hit -> Partial Exit 50% of remaining runner in 100-share board lots
5. Unconditional Structural Trend Failure Exit -> Close < EMA 50 and MACD < 0 (Pre- or Post-TP1)
6. Post-TP1 Trailing EMA Stop -> Trailing Stop on Daily EMA 9 with SET tick-snapped SL persistence
7. Time-Based Stagnation Exit -> Exits dead-money trades held >= max_holding_bars with < +0.5R
"""
from typing import Dict, List, Tuple
import pandas as pd
from .indicators import compute_ema, compute_macd, round_to_set_tick


class ThaiHybridExitTracker:
    def __init__(self, config: Dict):
        self.config = config
        tm = config.get("trade_management", {})
        self.tp1_ratio = float(tm.get("tp1_sell_ratio", tm.get("tp1_sell_fraction", config.get("tp1_sell_ratio", 0.5))))
        self.tp1_r = float(tm.get("tp1_r_multiple", config.get("tp1_r_multiple", 3.0)))
        self.tp2_r = float(tm.get("tp2_r_multiple", config.get("tp2_r_multiple", 5.0)))
        self.board_lot = int(config.get("board_lot_size", tm.get("board_lot_size", 100)))
        self.trailing_ema = int(tm.get("trailing_ema", config.get("trailing_ema", 9)))
        self.be_ratchet_r = float(tm.get("be_ratchet_r_multiple", config.get("be_ratchet_r_multiple", 1.5)))
        self.max_holding_bars = int(tm.get("max_holding_bars", config.get("max_holding_bars", 18)))
        self.stagnation_min_r = float(tm.get("stagnation_min_r", config.get("stagnation_min_r", 0.5)))
        self.single_lot_policy = str(
            config.get("single_lot_policy", tm.get("single_lot_policy", "take_profit_tp1"))
        )

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
        curr_open = float(df["Open"].iloc[-1]) if "Open" in df.columns else curr_close
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
        target_3r = float(pos.get("target_3r", round_to_set_tick(entry + self.tp1_r * risk_per_share, mode="nearest")))
        target_5r = float(pos.get("target_5r", round_to_set_tick(entry + self.tp2_r * risk_per_share, mode="nearest")))
        tp1_hit = bool(pos.get("tp1_hit", False))
        tp2_hit = bool(pos.get("tp2_hit", False))
        be_ratchet_hit = bool(pos.get("be_ratchet_hit", pos.get("be_ratcheted", False)))

        pos["current_price"] = round(curr_close, 2)
        pos["unrealized_pnl"] = round((curr_close - entry) * curr_shares, 2)
        pos["bars_held"] = int(pos.get("bars_held", 0)) + 1

        # -----------------------------------------------------------------
        # 1. Stop Loss Hit Check (with ATO Opening Gap-Down Execution)
        # -----------------------------------------------------------------
        if curr_low <= sl or curr_close <= sl:
            if curr_open <= sl:
                exit_price = round_to_set_tick(curr_open, mode="nearest")
            else:
                exit_price = round_to_set_tick(min(curr_close, sl), mode="nearest")

            pnl = round((exit_price - entry) * curr_shares, 2)
            pos["status"] = "CLOSED_SL"
            pos["exit_price"] = exit_price
            pos["exit_date"] = date_str
            pos["exit_reason"] = (
                "Breakeven Stop Loss Hit"
                if (tp1_hit or be_ratchet_hit or sl >= entry)
                else "Stop Loss Hit (-1R)"
            )
            pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
            pos["current_shares"] = 0

            actions.append({
                "type": "STOP_LOSS",
                "ticker": tk,
                "shares_sold": curr_shares,
                "price": exit_price,
                "pnl": pnl,
                "message": f"🛑 {tk} แตะจุด Stop Loss ที่ {exit_price:.2f} ฿ (ปิดสถานะ {curr_shares:,} หุ้น | PnL: {pnl:+,.0f} ฿)",
            })
            self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
            return pos, actions

        # -----------------------------------------------------------------
        # 1.5 Intermediate Breakeven Ratchet (+1.5R Pre-TP1 Protection)
        # -----------------------------------------------------------------
        ratchet_price = round_to_set_tick(entry + (self.be_ratchet_r * risk_per_share), mode="nearest")
        if not tp1_hit and not be_ratchet_hit and curr_high >= ratchet_price and curr_shares > 0:
            pos["be_ratchet_hit"] = True
            pos["be_ratcheted"] = True
            pos["current_sl"] = round_to_set_tick(max(float(pos["current_sl"]), entry), mode="down")
            sl = pos["current_sl"]

        # -----------------------------------------------------------------
        # 2. Target TP1 Hit
        # -----------------------------------------------------------------
        if not tp1_hit and curr_high >= target_3r and curr_shares > 0:
            pos["tp1_hit"] = True
            pos["be_ratchet_hit"] = True
            pos["current_sl"] = round_to_set_tick(max(float(pos["current_sl"]), entry), mode="down")

            if curr_shares <= self.board_lot:
                if self.single_lot_policy == "trail_at_tp1":
                    # Lock +1.5R profit on the 100-share lot and ride runner toward TP2 / trailing stop
                    lock_sl = round_to_set_tick(entry + (1.5 * risk_per_share), mode="down")
                    pos["current_sl"] = max(float(pos["current_sl"]), lock_sl, entry)
                    actions.append({
                        "type": "TP1_TRAIL_LOCK",
                        "ticker": tk,
                        "shares_sold": 0,
                        "price": target_3r,
                        "pnl": 0.0,
                        "message": (
                            f"🎯 {tk} ถึงเป้าหมาย TP1 ที่ {target_3r:.2f} ฿ (พอร์ต 1 Board Lot {curr_shares:,} หุ้น)\n"
                            f"• ยก Stop Loss ล็อคกำไรมาที่ {pos['current_sl']:.2f} ฿ และปล่อยรันเทรนด์ต่อ!"
                        ),
                    })
                else:
                    # 100 shares (1 Board Lot) -> Full exit at TP1 to avoid odd lots
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
                            f"• ปิดทำกำไร 100% ({sell_qty:,} หุ้น) ล็อคกำไร +{pnl:,.0f} ฿"
                        ),
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
                        f"🎯 {tk} ถึงเป้าหมาย TP1 ที่ {target_3r:.2f} ฿!\n"
                        f"• ขายทำกำไร 50% ({sell_qty:,} หุ้น) ล็อคกำไร +{pnl:,.0f} ฿\n"
                        f"• ยก Stop Loss บังทุนมาที่ {pos['current_sl']:.2f} ฿ (ไม้นี้ไร้ความเสี่ยงแล้ว 100%!)"
                    ),
                })

        # -----------------------------------------------------------------
        # 3. Target TP2 Hit
        # -----------------------------------------------------------------
        if pos.get("tp1_hit", False) and not tp2_hit and curr_high >= target_5r and curr_shares > 0:
            pos["tp2_hit"] = True

            if curr_shares <= self.board_lot:
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
                        f"🎯🎯 {tk} ถึงเป้าหมายใหญ่ TP2 ที่ {target_5r:.2f} ฿!\n"
                        f"• ปิดทำกำไรไม้สุดท้าย ({sell_qty:,} หุ้น) กำไร +{pnl:,.0f} ฿"
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
                    "message": (
                        f"🎯🎯 {tk} ถึงเป้าหมายใหญ่ TP2 ที่ {target_5r:.2f} ฿!\n"
                        f"• ขายทำกำไรก้อนสอง ({sell_qty:,} หุ้น) กำไร +{pnl:,.0f} ฿\n"
                        f"• หุ้นที่เหลือ {curr_shares:,} หุ้น ปล่อยรันต่อด้วย Daily EMA {self.trailing_ema}"
                    ),
                })

        # -----------------------------------------------------------------
        # 4. Unconditional Macro Structural Breakdown Exit (Pre- or Post-TP1)
        # -----------------------------------------------------------------
        if curr_shares > 0 and (curr_close < ema50 and m_val < 0):
            exit_px = round_to_set_tick(curr_close, mode="nearest")
            pnl = round((exit_px - entry) * curr_shares, 2)
            pos["status"] = "CLOSED_TRAILING" if pos.get("tp1_hit", False) else "CLOSED_STRUCTURAL_FAIL"
            pos["exit_price"] = exit_px
            pos["exit_date"] = date_str
            pos["exit_reason"] = "Macro Trend Breakdown (Close < EMA50 and MACD < 0)"
            pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
            pos["current_shares"] = 0
            curr_shares = 0

            actions.append({
                "type": "STRUCTURAL_BREAKDOWN_EXIT",
                "ticker": tk,
                "shares_sold": int(position["current_shares"]),
                "price": exit_px,
                "pnl": pnl,
                "message": (
                    f"🚨 {tk} โครงสร้างเทรนด์เสีย (หลุด EMA 50 & MACD < 0) ที่ {exit_px:.2f} ฿\n"
                    f"• ปิดสถานะปกป้องพอร์ต ({pnl:+,.0f} ฿)"
                ),
            })
            self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
            return pos, actions

        # -----------------------------------------------------------------
        # 5. Trailing EMA Stop for Remaining Runner (Post-TP1)
        # -----------------------------------------------------------------
        if pos.get("tp1_hit", False) and curr_shares > 0:
            if curr_close < ema_trail or curr_close < ema50 or m_val < 0:
                exit_px = round_to_set_tick(curr_close, mode="nearest")
                pnl = round((exit_px - entry) * curr_shares, 2)
                pos["status"] = "CLOSED_TRAILING"
                pos["exit_price"] = exit_px
                pos["exit_date"] = date_str
                pos["exit_reason"] = f"Trailing Stop Exit (Closed below EMA {self.trailing_ema})"
                pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
                pos["current_shares"] = 0
                curr_shares = 0

                actions.append({
                    "type": "TRAILING_EXIT",
                    "ticker": tk,
                    "shares_sold": curr_shares,
                    "price": exit_px,
                    "pnl": pnl,
                    "message": (
                        f"📉 {tk} แท่งวันปิดหลุด Daily EMA {self.trailing_ema} ที่ {exit_px:.2f} ฿\n"
                        f"• ปิดทำกำไรหุ้นส่วนรันเทรนด์ ({pnl:+,.0f} ฿)"
                    ),
                })
                self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
                return pos, actions
            else:
                snapped_trail = round_to_set_tick(ema_trail, mode="down")
                pos["current_sl"] = max(float(pos["current_sl"]), snapped_trail)

        # -----------------------------------------------------------------
        # 6. Time-Based Stagnation Exit
        # -----------------------------------------------------------------
        if not pos.get("tp1_hit", False) and curr_shares > 0 and pos["bars_held"] >= self.max_holding_bars:
            curr_r_gain = ((curr_close - entry) / risk_per_share) if risk_per_share > 0 else 0.0
            if curr_r_gain < self.stagnation_min_r:
                exit_px = round_to_set_tick(curr_close, mode="nearest")
                pnl = round((exit_px - entry) * curr_shares, 2)
                pos["status"] = "CLOSED_STAGNATION"
                pos["exit_price"] = exit_px
                pos["exit_date"] = date_str
                pos["exit_reason"] = f"Time Stagnation Exit ({pos['bars_held']} bars held, < {self.stagnation_min_r}R)"
                pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
                pos["current_shares"] = 0

                actions.append({
                    "type": "STAGNATION_EXIT",
                    "ticker": tk,
                    "shares_sold": curr_shares,
                    "price": exit_px,
                    "pnl": pnl,
                    "message": (
                        f"⏳ {tk} ถือครบ {pos['bars_held']} วัน ราคาไม่วิ่ง (< +{self.stagnation_min_r}R)\n"
                        f"• ปิดสถานะหมุนเวียนทุนที่ {exit_px:.2f} ฿ ({pnl:+,.0f} ฿)"
                    ),
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
