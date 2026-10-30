"""
Exit Tracker for Bot 5 US Hybrid:
1. Stop Loss Hit -> Full Exit (-1R)
2. Target 3R Hit -> Partial Exit 50% + Move Stop Loss to Breakeven
3. Macro Exit -> Close remaining 50% when Daily Close < EMA 50 or MACD turns Red
"""
from typing import Dict, List, Tuple
import pandas as pd
from .indicators import compute_ema, compute_macd

class USHybridExitTracker:
    def __init__(self, config: Dict):
        self.config = config
        self.tp1_ratio = float(config.get("tp1_sell_ratio", 0.5))

    def evaluate_position(self, position: Dict, df: pd.DataFrame) -> Tuple[Dict, List[Dict]]:
        actions = []
        pos = dict(position)
        tk = pos["ticker"]

        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        curr_close = float(close.iloc[-1])
        curr_high = float(high.iloc[-1])
        curr_low = float(low.iloc[-1])
        date_str = str(df.index[-1])[:10]

        ema50 = float(compute_ema(close, 50).iloc[-1])
        macd, macd_sig, _ = compute_macd(close)
        m_val = float(macd.iloc[-1])

        entry = float(pos["entry_price"])
        sl = float(pos["current_sl"])
        risk_per_share = float(pos["risk_per_share"])
        curr_shares = int(pos["current_shares"])
        target_3r = float(pos["target_3r"])
        tp1_hit = bool(pos.get("tp1_hit", False))

        curr_r = round((curr_close - entry) / risk_per_share, 2) if risk_per_share > 0 else 0.0
        pos["current_price"] = round(curr_close, 2)
        pos["current_r"] = curr_r
        pos["unrealized_pnl"] = round((curr_close - entry) * curr_shares, 2)

        # 1. Stop Loss Hit
        if curr_low <= sl or curr_close <= sl:
            exit_price = min(curr_close, sl)
            pnl = round((exit_price - entry) * curr_shares, 2)
            pos["status"] = "CLOSED_SL"
            pos["exit_price"] = exit_price
            pos["exit_date"] = date_str
            pos["exit_reason"] = "Stop Loss Hit" if not tp1_hit else "Breakeven SL Hit"
            pos["current_shares"] = 0
            pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
            actions.append({
                "type": "STOP_LOSS",
                "ticker": tk,
                "shares_sold": curr_shares,
                "price": exit_price,
                "pnl": pnl,
                "message": (
                    f"🛑 <b>${tk} แตะ SL (<code>${exit_price:.2f}</code>)</b>\n"
                    f"└ ปิดสถานะ {curr_shares} sh ({pnl:+,.2f})"
                )
            })
            return pos, actions

        # 2. Target 3R Hit (Lock 50% + SL to Breakeven)
        if not tp1_hit and curr_high >= target_3r and curr_shares > 0:
            sell_qty = max(1, int(curr_shares * self.tp1_ratio))
            pnl = round((target_3r - entry) * sell_qty, 2)
            pos["tp1_hit"] = True
            pos["current_shares"] = curr_shares - sell_qty
            pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
            pos["current_sl"] = round(max(pos["current_sl"], entry), 2)
            curr_shares = pos["current_shares"]

            actions.append({
                "type": "TP1_3R",
                "ticker": tk,
                "shares_sold": sell_qty,
                "price": target_3r,
                "pnl": pnl,
                "message": (
                    f"🎯 <b>${tk} ถึงเป้า 3R @ <code>${target_3r:.2f}</code></b>\n"
                    f"├ ขายล็อคกำไร 50% ({sell_qty} sh): <code>+${pnl:,.2f}</code>\n"
                    f"└ ยก SL บังทุน: <code>${pos['current_sl']:.2f}</code>"
                )
            })

        # 3. Macro Trend Exit for Runner (Daily Close < EMA 50 or MACD < 0)
        if pos.get("tp1_hit", False) and curr_shares > 0 and (curr_close < ema50 or m_val < 0):
            pnl = round((curr_close - entry) * curr_shares, 2)
            pos["status"] = "CLOSED_MACRO_TREND"
            pos["exit_price"] = curr_close
            pos["exit_date"] = date_str
            pos["exit_reason"] = "Macro Trend Exit (EMA 50 / MACD breakdown)"
            pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
            pos["current_shares"] = 0

            actions.append({
                "type": "MACRO_EXIT",
                "ticker": tk,
                "shares_sold": curr_shares,
                "price": curr_close,
                "pnl": pnl,
                "message": (
                    f"🚨 <b>${tk} หลุดเทรนด์ EMA 50 @ <code>${curr_close:.2f}</code></b>\n"
                    f"└ ปิดรอบไม้ที่เหลือ {curr_shares} sh: <code>{pnl:+,.2f}</code>"
                )
            })

        return pos, actions
