"""
Exit Tracker for US 6-Button Strategy (Bot 1):
1. Stop Loss Hit -> Full Exit (-1R or Breakeven)
2. Target 3R Hit -> Partial Exit 50% + Move SL to Breakeven
3. Target 5R Hit -> Partial Exit 50% of remaining runner
4. Trailing EMA 21 Stop / 6 Red Buttons -> Exit remaining runner
"""
from typing import Dict, List, Tuple
import pandas as pd


class US6ButtonExitTracker:
    def __init__(self, config: Dict):
        self.config = config
        self.tp1_ratio = float(config.get("tp1_sell_ratio", 0.5))
        self.trailing_ema = int(config.get("trailing_ema", 21))

    def evaluate_position(self, position: Dict, df: pd.DataFrame, action_today: str = "") -> Tuple[Dict, List[Dict]]:
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

        ema21 = float(df["Close"].ewm(span=self.trailing_ema, adjust=False).mean().iloc[-1])

        entry = float(pos.get("entry_price", pos.get("buy_price", curr_close)))
        sl = float(pos.get("current_sl", pos.get("stop_loss", round(entry * 0.95, 2))))
        risk_per_share = float(pos.get("risk_per_share", round(entry - sl, 2)))
        curr_shares = int(pos.get("current_shares", pos.get("shares", 1)))
        initial_shares = int(pos.get("initial_shares", pos.get("shares", curr_shares)))
        target_3r = float(pos.get("target_3r", round(entry + 3.0 * risk_per_share, 2)))
        target_5r = float(pos.get("target_5r", round(entry + 5.0 * risk_per_share, 2)))
        tp1_hit = bool(pos.get("tp1_hit", False))
        tp2_hit = bool(pos.get("tp2_hit", False))

        pos["current_price"] = round(curr_close, 2)
        pos["unrealized_pnl"] = round((curr_close - entry) * curr_shares, 2)

        # 1. Stop Loss Hit
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
                "message": f"🛑 <b>${tk} แตะจุด SL (<code>${exit_price:.2f}</code>)</b>\n└ ปิดสถานะ {curr_shares} sh ({pnl:+,.2f})"
            })
            self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
            return pos, actions

        # 2. Target 3R Hit (TP1)
        if not tp1_hit and curr_high >= target_3r and curr_shares > 0:
            pos["tp1_hit"] = True
            pos["current_sl"] = round(max(pos["current_sl"], entry), 2)  # Breakeven

            if curr_shares <= 1:
                sell_qty = 1
                pnl = round((target_3r - entry) * sell_qty, 2)
                pos["status"] = "CLOSED_TP1"
                pos["exit_price"] = target_3r
                pos["exit_date"] = date_str
                pos["exit_reason"] = "Target 3R Hit (100% Exit)"
                pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
                pos["current_shares"] = 0
                curr_shares = 0

                actions.append({
                    "type": "TP1_3R_FULL",
                    "ticker": tk,
                    "shares_sold": sell_qty,
                    "price": target_3r,
                    "pnl": pnl,
                    "message": f"🎯 <b>${tk} ถึงเป้า 3R @ <code>${target_3r:.2f}</code></b>\n└ ปิดทำกำไร 100% ({sell_qty} sh): <code>+${pnl:,.2f}</code> (+3.0R)"
                })
                self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
                return pos, actions
            else:
                sell_qty = max(1, int(curr_shares * self.tp1_ratio))
                if sell_qty >= curr_shares:
                    sell_qty = curr_shares - 1
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
                    "message": f"🎯 <b>${tk} ถึงเป้า 3R @ <code>${target_3r:.2f}</code></b>\n├ ขายล็อคกำไร 50% ({sell_qty} sh): <code>+${pnl:,.2f}</code>\n└ ยก SL บังทุน: <code>${pos['current_sl']:.2f}</code>"
                })

        # 3. Target 5R Hit (TP2)
        if pos.get("tp1_hit", False) and not tp2_hit and curr_high >= target_5r and curr_shares > 0:
            pos["tp2_hit"] = True
            if curr_shares <= 1:
                sell_qty = 1
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
                    "message": f"🎯🎯 <b>${tk} ถึงเป้าใหญ่ 5R @ <code>${target_5r:.2f}</code></b>\n└ ปิดทำกำไรไม้สุดท้าย ({sell_qty} sh): <code>+${pnl:,.2f}</code> (+5.0R)"
                })
                self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
                return pos, actions
            else:
                sell_qty = max(1, curr_shares // 2)
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
                    "message": f"🎯🎯 <b>${tk} ถึงเป้าใหญ่ 5R @ <code>${target_5r:.2f}</code></b>\n├ ขายทำกำไรก้อนสอง ({sell_qty} sh): <code>+${pnl:,.2f}</code>\n└ หุ้นที่เหลือ {curr_shares} sh ปล่อยรันต่อด้วย Daily EMA {self.trailing_ema}"
                })

        # 4. Trailing EMA 21 Stop / SELL_NOW for Runner
        if curr_shares > 0 and (action_today == "SELL_NOW" or (pos.get("tp1_hit", False) and curr_close < ema21)):
            exit_reason = "6 Red Buttons SELL_NOW Exit" if action_today == "SELL_NOW" else f"Trailing Stop Exit (Closed below EMA {self.trailing_ema})"
            pnl = round((curr_close - entry) * curr_shares, 2)
            pos["status"] = "CLOSED_TRAILING" if pos.get("tp1_hit", False) else "CLOSED_SELL_NOW"
            pos["exit_price"] = curr_close
            pos["exit_date"] = date_str
            pos["exit_reason"] = exit_reason
            pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
            pos["current_shares"] = 0

            actions.append({
                "type": "TRAILING_EXIT",
                "ticker": tk,
                "shares_sold": curr_shares,
                "price": curr_close,
                "pnl": pnl,
                "message": f"🚨 <b>${tk} {exit_reason} @ <code>${curr_close:.2f}</code></b>\n└ ปิดสถานะ {curr_shares} sh: <code>{pnl:+,.2f}</code>"
            })

        self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
        return pos, actions

    def _update_metrics(self, pos: Dict, entry: float, risk_per_share: float, initial_shares: int, curr_close: float):
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
