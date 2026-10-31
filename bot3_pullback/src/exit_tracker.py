"""
Exit Tracker & Trade Management Engine (Step [4/4])
- Monitors Active Positions against:
  * Stop Loss Hit (Full Exit / Cut Loss)
  * Target 3R Hit (Partial TP 1 + Move SL to Breakeven, or Full Exit if 1 share)
  * Target 5R Hit (Partial TP 2)
  * Daily EMA 9 Trailing Stop for Runner (Full Exit on close < EMA9)
  * Overextended / Climax Alert (Distance from EMA 9 > threshold)
- Calculates true cumulative blended R-multiple
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd

from .indicators import compute_ema, compute_atr


class ExitTracker:
    def __init__(self, config: Dict):
        self.config = config
        self.tp1_ratio = float(config.get("tp1_sell_ratio", 0.5))
        self.tp2_ratio = float(config.get("tp2_sell_ratio", 0.5))
        self.trailing_ema_period = int(config.get("trailing_ema", 9))
        self.overextended_pct = float(config.get("overextended_ema_threshold_pct", 15.0))

    def _update_metrics(
        self,
        pos: Dict,
        entry: float,
        risk_per_share: float,
        initial_shares: int,
        curr_close: float,
    ):
        """Calculates true cumulative blended R-multiple and return metrics."""
        initial_dollar_risk = initial_shares * risk_per_share
        tot_realized = float(pos.get("total_realized_pnl", 0.0))
        rem_shares = int(pos.get("current_shares", 0))

        if rem_shares > 0:
            unrealized = round((curr_close - entry) * rem_shares, 2)
            pos["unrealized_pnl"] = unrealized
            pos["unrealized_pct"] = round(((curr_close - entry) / entry) * 100.0, 2) if entry > 0 else 0.0
            blended_pnl = tot_realized + unrealized
        else:
            pos["unrealized_pnl"] = 0.0
            pos["unrealized_pct"] = 0.0
            blended_pnl = tot_realized

        pos["current_r"] = round(blended_pnl / initial_dollar_risk, 2) if initial_dollar_risk > 0 else 0.0
        pos["total_pnl"] = round(blended_pnl, 2)
        pos["current_price"] = round(curr_close, 2)

    def evaluate_position(
        self, position: Dict, df: pd.DataFrame
    ) -> Tuple[Dict, List[Dict]]:
        """
        Evaluate an active position against latest price bar.
        Returns: (updated_position, list_of_actions)
        """
        actions = []
        pos = dict(position)

        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        curr_close = float(close.iloc[-1])
        curr_high = float(high.iloc[-1])
        curr_low = float(low.iloc[-1])
        date_str = str(df.index[-1])[:10]

        ema9 = float(compute_ema(close, self.trailing_ema_period).iloc[-1])
        atr14 = float(compute_atr(df, 14).iloc[-1]) if len(df) >= 15 else 1.0

        entry = float(pos["entry_price"])
        sl = float(pos["current_sl"])
        risk_per_share = float(pos["risk_per_share"])
        curr_shares = int(pos["current_shares"])
        initial_shares = int(pos.get("initial_shares", pos.get("shares", curr_shares)))
        target_3r = float(pos["target_3r"])
        target_5r = float(pos["target_5r"])
        tp1_hit = bool(pos.get("tp1_hit", False))
        tp2_hit = bool(pos.get("tp2_hit", False))

        # Initial metrics calculation
        self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)

        # 1. Check Stop Loss
        if curr_low <= sl or curr_close <= sl:
            exit_price = min(curr_close, sl)
            pnl = round((exit_price - entry) * curr_shares, 2)
            pos["status"] = "CLOSED_SL"
            pos["exit_price"] = exit_price
            pos["exit_date"] = date_str
            pos["exit_reason"] = "Stop Loss Hit"
            pos["current_shares"] = 0
            pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
            actions.append({
                "type": "STOP_LOSS",
                "ticker": pos["ticker"],
                "shares_sold": curr_shares,
                "price": exit_price,
                "pnl": pnl,
                "message": f"🛑 {pos['ticker']} แตะจุด Stop Loss ที่ ${exit_price:.2f} (ปิดออเดอร์ทั้งหมด)",
            })
            self._update_metrics(pos, entry, risk_per_share, initial_shares, exit_price)
            return pos, actions

        # 2. Check Target 3R (Take Profit 1)
        if not tp1_hit and curr_high >= target_3r and curr_shares > 0:
            pos["tp1_hit"] = True
            pos["current_sl"] = round(max(pos["current_sl"], entry), 2)  # Move SL to Breakeven

            if curr_shares <= 1:
                # Single-share liquidation: 100% exit at 3R (eliminate zombie 0-share position)
                sell_qty = curr_shares
                pnl = round((target_3r - entry) * sell_qty, 2)
                pos["status"] = "CLOSED_TP1"
                pos["exit_price"] = target_3r
                pos["exit_date"] = date_str
                pos["exit_reason"] = "Target 3R Hit (100% Exit for 1 Share)"
                pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
                pos["current_shares"] = 0
                curr_shares = 0

                actions.append({
                    "type": "TP1_3R_FULL",
                    "ticker": pos["ticker"],
                    "shares_sold": sell_qty,
                    "price": target_3r,
                    "pnl": pnl,
                    "message": (
                        f"🎯 <b>${pos['ticker']} บรรลุเป้าหมาย 3R ที่ ${target_3r:.2f}</b>\n"
                        f"• ปิดทำกำไร 100% (ถือ 1 หุ้น) จำนวน {sell_qty} หุ้น (+${pnl:.2f})"
                    ),
                })
                self._update_metrics(pos, entry, risk_per_share, initial_shares, target_3r)
                return pos, actions
            else:
                raw_sell = int(curr_shares * self.tp1_ratio)
                sell_qty = max(1, raw_sell)
                if sell_qty >= curr_shares:
                    sell_qty = curr_shares - 1  # Preserve at least 1 runner share

                pnl = round((target_3r - entry) * sell_qty, 2)
                pos["current_shares"] = curr_shares - sell_qty
                pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
                curr_shares = pos["current_shares"]

                actions.append({
                    "type": "TP1_3R",
                    "ticker": pos["ticker"],
                    "shares_sold": sell_qty,
                    "price": target_3r,
                    "pnl": pnl,
                    "new_sl": pos["current_sl"],
                    "remaining_shares": curr_shares,
                    "message": (
                        f"🎯 {pos['ticker']} บรรลุเป้าหมาย 3R ที่ ${target_3r:.2f}!\n"
                        f"• ขายทำกำไร 50% จำนวน {sell_qty} หุ้น (+${pnl:.2f})\n"
                        f"• เลื่อน Stop Loss บังทุนมาที่ ${pos['current_sl']:.2f} (พอร์ตไร้ความเสี่ยงแล้ว!)"
                    ),
                })

        # 3. Check Target 5R (Take Profit 2)
        if pos.get("tp1_hit", False) and not tp2_hit and curr_high >= target_5r and curr_shares > 0:
            if curr_shares <= 1:
                sell_qty = curr_shares
                pnl = round((target_5r - entry) * sell_qty, 2)
                pos["status"] = "CLOSED_TP2"
                pos["exit_price"] = target_5r
                pos["exit_date"] = date_str
                pos["exit_reason"] = "Target 5R Hit (100% Exit)"
                pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
                pos["current_shares"] = 0
                curr_shares = 0

                actions.append({
                    "type": "TP2_5R_FULL",
                    "ticker": pos["ticker"],
                    "shares_sold": sell_qty,
                    "price": target_5r,
                    "pnl": pnl,
                    "message": (
                        f"🎯🎯 <b>${pos['ticker']} บรรลุเป้าหมายใหญ่ 5R ที่ ${target_5r:.2f}</b>\n"
                        f"• ปิดทำกำไร 100% จำนวน {sell_qty} หุ้น (+${pnl:.2f})"
                    ),
                })
                self._update_metrics(pos, entry, risk_per_share, initial_shares, target_5r)
                return pos, actions
            else:
                raw_sell = int(curr_shares * self.tp2_ratio)
                sell_qty = max(1, raw_sell)
                if sell_qty >= curr_shares:
                    sell_qty = curr_shares - 1  # Preserve runner

                pnl = round((target_5r - entry) * sell_qty, 2)
                pos["tp2_hit"] = True
                pos["current_shares"] = curr_shares - sell_qty
                pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
                curr_shares = pos["current_shares"]

                actions.append({
                    "type": "TP2_5R",
                    "ticker": pos["ticker"],
                    "shares_sold": sell_qty,
                    "price": target_5r,
                    "pnl": pnl,
                    "remaining_shares": curr_shares,
                    "message": (
                        f"🎯🎯 {pos['ticker']} บรรลุเป้าหมายใหญ่ 5R ที่ ${target_5r:.2f}!\n"
                        f"• ขายทำกำไรก้อนที่สองจำนวน {sell_qty} หุ้น (+${pnl:.2f})\n"
                        f"• หุ้นที่เหลือ {curr_shares} หุ้น ปล่อยรันเทรนด์ต่อด้วย Daily EMA 9"
                    ),
                })

        # 4. Check Trailing EMA 9 Stop for Runner
        # Triggered when daily candle closes below EMA 9
        if curr_shares > 0 and pos.get("tp1_hit", False) and curr_close < ema9:
            pnl = round((curr_close - entry) * curr_shares, 2)
            pos["status"] = "CLOSED_RUNNER"
            pos["exit_price"] = curr_close
            pos["exit_date"] = date_str
            pos["exit_reason"] = f"Closed below EMA 9 (${ema9:.2f})"
            pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
            pos["current_shares"] = 0

            actions.append({
                "type": "TRAILING_EMA9_EXIT",
                "ticker": pos["ticker"],
                "shares_sold": curr_shares,
                "price": curr_close,
                "pnl": pnl,
                "message": (
                    f"📉 {pos['ticker']} แท่งเทียนปิดหลุด Daily EMA 9 ที่ ${curr_close:.2f}\n"
                    f"• ปิดทำกำไรหุ้นส่วนที่เหลือ {curr_shares} หุ้น (+${pnl:.2f})"
                ),
            })
            self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
            return pos, actions

        # 5. Check Climax / Overextension Warning
        dist_ema9_pct = ((curr_close - ema9) / ema9) * 100.0 if ema9 > 0 else 0.0
        pos["dist_ema9_pct"] = round(dist_ema9_pct, 1)

        if dist_ema9_pct >= self.overextended_pct and curr_shares > 0:
            actions.append({
                "type": "OVEREXTENDED_WARNING",
                "ticker": pos["ticker"],
                "dist_pct": round(dist_ema9_pct, 1),
                "message": (
                    f"⚡ {pos['ticker']} ราคาพุ่งแรงและอยู่ห่างจาก Daily EMA 9 ถึง +{dist_ema9_pct:.1f}%\n"
                    f"💡 แนะนำ: พิจารณาทยอยแบ่งขายล็อคกำไรเพิ่ม ป้องกันการย่อตัวแรง"
                ),
            })

        self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
        return pos, actions
