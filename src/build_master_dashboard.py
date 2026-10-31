# -*- coding: utf-8 -*-
"""
6-Bot Forward Test Master Dashboard Builder
Generates docs/index.html aggregating all active paper trades and forward test performance across Bots 1 to 6.
"""

import os
import json
import base64
import urllib.request
from datetime import datetime
import yfinance as yf

# Configuration Sources
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(BASE_DIR, "docs")
os.makedirs(DOCS_DIR, exist_ok=True)

BOT_CONFIGS = [
    {
        "id": "bot1",
        "name": "Bot 1: US 6-Button",
        "market": "US",
        "strategy": "6-Button Multi-Layer Momentum",
        "local_path": os.path.join(BASE_DIR, "config", "watchlist.json"),
        "raw_url": "https://raw.githubusercontent.com/mjchatchai/us-stocks-alert/main/config/watchlist.json",
        "is_thai": False,
        "sub_url": "bot1.html"
    },
    {
        "id": "bot2",
        "name": "Bot 2: TH 6-Button",
        "market": "TH",
        "strategy": "SET 6-Button Multi-Layer Momentum",
        "local_path": os.path.join(BASE_DIR, "thai_stocks", "config", "watchlist.json"),
        "raw_url": "https://raw.githubusercontent.com/mjchatchai/thai-stocks-alert/main/config/watchlist.json",
        "is_thai": True,
        "sub_url": "https://mjchatchai.github.io/thai-stocks-alert/"
    },
    {
        "id": "bot3",
        "name": "Bot 3: US Pullback",
        "market": "US",
        "strategy": "Trend Confluence Support & Retest",
        "local_path": os.path.join(BASE_DIR, "bot3_pullback", "config", "config.json"),
        "raw_url": "https://raw.githubusercontent.com/mjchatchai/us-stocks-alert/main/bot3_pullback/config/config.json",
        "is_thai": False,
        "sub_url": "bot3.html"
    },
    {
        "id": "bot4",
        "name": "Bot 4: TH Pullback",
        "market": "TH",
        "strategy": "SET Confluence Support & Retest",
        "local_path": os.path.join(BASE_DIR, "bot4_thai_pullback", "config", "config.json"),
        "raw_url": "https://raw.githubusercontent.com/mjchatchai/us-stocks-alert/main/bot4_thai_pullback/config/config.json",
        "is_thai": True,
        "sub_url": "bot4.html"
    },
    {
        "id": "bot5",
        "name": "Bot 5: US Hybrid",
        "market": "US",
        "strategy": "Multi-Factor Hybrid Master",
        "local_path": os.path.join(BASE_DIR, "bot5_us_hybrid", "config", "config.json"),
        "raw_url": "https://raw.githubusercontent.com/mjchatchai/us-stocks-alert/main/bot5_us_hybrid/config/config.json",
        "is_thai": False,
        "sub_url": "bot5.html"
    },
    {
        "id": "bot6",
        "name": "Bot 6: TH Hybrid",
        "market": "TH",
        "strategy": "SET Multi-Factor Hybrid Master",
        "local_path": os.path.join(BASE_DIR, "bot5_thai_hybrid", "config", "config.json"),
        "raw_url": "https://raw.githubusercontent.com/mjchatchai/us-stocks-alert/main/bot5_thai_hybrid/config/config.json",
        "is_thai": True,
        "sub_url": "bot6.html"
    }
]

def load_json_data(local_path, raw_url):
    """Load JSON from local path if present, otherwise fetch from raw GitHub URL."""
    # Priority: raw URL if in GitHub Actions or if local file is missing active positions
    data = {}
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
            
    # If local had no positions or was empty, attempt raw URL
    has_pos = bool(data.get("portfolio") or data.get("active_positions"))
    if not has_pos and raw_url:
        try:
            req = urllib.request.Request(raw_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass
    return data

def build_master_dashboard():
    print("=== Building 6-Bot Forward Test Master Dashboard ===")
    
    all_positions = []
    all_closed_trades = []
    bot_summaries = []
    
    # 1. Collect all positions and trade histories
    yf_tickers = set()
    
    for bot in BOT_CONFIGS:
        cfg = load_json_data(bot["local_path"], bot["raw_url"])
        is_th = bot["is_thai"]
        
        # Positions: Bot 1 & 2 use 'portfolio', Bots 3-6 use 'active_positions'
        raw_pos = cfg.get("active_positions") or cfg.get("portfolio") or {}
        trades = cfg.get("trade_history") or []
        
        open_count = len(raw_pos)
        closed_count = len(trades)
        
        # Calculate closed metrics
        wins = [t for t in trades if t.get("pnl_r", 0) > 0 or t.get("pnl_pct", 0) > 0]
        losses = [t for t in trades if t.get("pnl_r", 0) <= 0 or t.get("pnl_pct", 0) <= 0]
        win_rate = (len(wins) / closed_count * 100.0) if closed_count > 0 else 0.0
        total_r = sum(t.get("pnl_r", 0.0) for t in trades)
        
        bot_summaries.append({
            "id": bot["id"],
            "name": bot["name"],
            "market": bot["market"],
            "strategy": bot["strategy"],
            "open_count": open_count,
            "closed_count": closed_count,
            "win_rate": win_rate,
            "total_r": total_r,
            "sub_url": bot["sub_url"]
        })
        
        for tk, pdata in raw_pos.items():
            clean_tk = str(tk).strip()
            yf_sym = f"{clean_tk}.BK" if is_th else clean_tk
            yf_tickers.add(yf_sym)
            
            entry = float(pdata.get("entry_price") or pdata.get("buy_price") or 0.0)
            sl = float(pdata.get("current_sl") or pdata.get("stop_loss") or (entry * 0.95))
            r_per_sh = float(pdata.get("risk_per_share") or (entry - sl))
            if r_per_sh <= 0:
                r_per_sh = entry * 0.03
                
            t3r = float(pdata.get("target_3r") or (entry + 3.0 * r_per_sh))
            t5r = float(pdata.get("target_5r") or (entry + 5.0 * r_per_sh))
            shares = pdata.get("current_shares") or pdata.get("shares") or "-"
            entry_date = pdata.get("entry_date") or pdata.get("buy_date") or "-"
            
            all_positions.append({
                "bot_id": bot["id"],
                "bot_name": bot["name"],
                "market": bot["market"],
                "is_thai": is_th,
                "ticker": clean_tk,
                "yf_sym": yf_sym,
                "entry_price": entry,
                "current_sl": sl,
                "target_3r": t3r,
                "target_5r": t5r,
                "risk_per_share": r_per_sh,
                "shares": shares,
                "entry_date": entry_date,
                "tp1_hit": pdata.get("tp1_hit", False),
                "tp2_hit": pdata.get("tp2_hit", False)
            })
            
        for t in trades:
            all_closed_trades.append({
                "bot_id": bot["id"],
                "bot_name": bot["name"],
                "market": bot["market"],
                "is_thai": is_th,
                "ticker": t.get("ticker", "-"),
                "entry_date": t.get("entry_date", "-"),
                "exit_date": t.get("exit_date", "-"),
                "entry_price": float(t.get("entry_price") or t.get("buy_price") or 0.0),
                "exit_price": float(t.get("exit_price") or t.get("sell_price") or 0.0),
                "pnl_pct": float(t.get("pnl_pct") if t.get("pnl_pct") is not None else t.get("realized_pnl_pct", 0.0)),
                "pnl_r": float(t.get("pnl_r") if t.get("pnl_r") is not None else t.get("r_multiple", 0.0)),
                "exit_reason": t.get("exit_reason", "SELL Signal")
            })

    print(f"Total Active Positions across 6 Bots: {len(all_positions)}")
    print(f"Total Closed Trades across 6 Bots: {len(all_closed_trades)}")

    # 2. Batch download latest quotes
    price_map = {}
    if yf_tickers:
        try:
            print(f"Downloading live prices for {len(yf_tickers)} tickers...")
            batch = yf.download(list(yf_tickers), period="5d", interval="1d", progress=False)
            if "Close" in batch:
                c_df = batch["Close"]
                for sym in yf_tickers:
                    try:
                        if isinstance(c_df, yf.pandas.DataFrame) and sym in c_df.columns:
                            s = c_df[sym].dropna()
                            if not s.empty:
                                price_map[sym] = float(s.iloc[-1])
                        elif hasattr(c_df, "iloc") and not c_df.dropna().empty:
                            price_map[sym] = float(c_df.dropna().iloc[-1])
                    except Exception:
                        pass
        except Exception as e:
            print(f"Warning: Failed batch download: {e}")

    # 3. Calculate unrealized metrics for each position
    total_unrealized_r = 0.0
    for p in all_positions:
        cur_price = price_map.get(p["yf_sym"], p["entry_price"])
        p["current_price"] = cur_price
        
        if p["entry_price"] > 0:
            pnl_pct = ((cur_price - p["entry_price"]) / p["entry_price"]) * 100.0
        else:
            pnl_pct = 0.0
        p["pnl_pct"] = pnl_pct
        
        if p["risk_per_share"] > 0:
            u_r = (cur_price - p["entry_price"]) / p["risk_per_share"]
        else:
            u_r = 0.0
        p["unrealized_r"] = u_r
        total_unrealized_r += u_r
        
        # Distance to SL
        if cur_price > 0:
            dist_sl = ((cur_price - p["current_sl"]) / cur_price) * 100.0
        else:
            dist_sl = 0.0
        p["dist_sl"] = dist_sl

    # 4. Overall Master KPIs
    total_open = len(all_positions)
    total_closed = len(all_closed_trades)
    overall_wins = [t for t in all_closed_trades if t["pnl_r"] > 0 or t["pnl_pct"] > 0]
    overall_win_rate = (len(overall_wins) / total_closed * 100.0) if total_closed > 0 else 0.0
    overall_net_r = sum(t["pnl_r"] for t in all_closed_trades)
    
    th_open_count = len([p for p in all_positions if p["is_thai"]])
    us_open_count = len([p for p in all_positions if not p["is_thai"]])

    # 5. Build HTML Output
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Render Active Positions Rows
    active_rows_html = ""
    for p in sorted(all_positions, key=lambda x: x["unrealized_r"], reverse=True):
        flag = "🇹🇭" if p["is_thai"] else "🇺🇸"
        cur_sym = "฿" if p["is_thai"] else "$"
        pnl_class = "text-green" if p["pnl_pct"] >= 0 else "text-red"
        r_class = "text-green" if p["unrealized_r"] >= 0 else "text-red"
        
        status_badge = '<span class="badge badge-blue">รันเทรนด์</span>'
        if p["unrealized_r"] >= 5.0 or p["tp2_hit"]:
            status_badge = '<span class="badge badge-purple">5R ทะลุเป้า</span>'
        elif p["unrealized_r"] >= 3.0 or p["tp1_hit"]:
            status_badge = '<span class="badge badge-green">3R สำเร็จ</span>'
        elif p["dist_sl"] < 1.5:
            status_badge = '<span class="badge badge-red">⚠️ ใกล้จุด SL</span>'
            
        sh_str = f"{p['shares']:,}" if isinstance(p['shares'], int) else str(p['shares'])
        
        # TradingView symbol
        tv_sym = f"SET:{p['ticker']}" if p["is_thai"] else p["ticker"]
        
        active_rows_html += f"""
        <tr class="bot-row {p['bot_id']} {'mkt-th' if p['is_thai'] else 'mkt-us'}">
            <td>
                <div class="ticker-badge" onclick="openTradingViewModal('{tv_sym}')">
                    <span>{flag}</span>
                    <b>{p['ticker']}</b>
                </div>
            </td>
            <td><span class="bot-pill">{p['bot_name']}</span></td>
            <td><code>{p['entry_date']}</code></td>
            <td>{p['entry_price']:.2f} {cur_sym}</td>
            <td><b>{p['current_price']:.2f} {cur_sym}</b></td>
            <td><b class="{pnl_class}">{p['pnl_pct']:+.2f}%</b></td>
            <td><b class="{r_class}">{p['unrealized_r']:+.2f}R</b></td>
            <td class="text-red">{p['current_sl']:.2f} {cur_sym}</td>
            <td class="text-gold">{p['target_3r']:.2f} {cur_sym}</td>
            <td class="text-green">{p['target_5r']:.2f} {cur_sym}</td>
            <td>{sh_str}</td>
            <td>{status_badge}</td>
            <td>
                <button class="btn-action" onclick="openTradingViewModal('{tv_sym}')">📈 กราฟ</button>
            </td>
        </tr>
        """
        
    # Render Leaderboard Rows
    leaderboard_html = ""
    for rank, b in enumerate(sorted(bot_summaries, key=lambda x: (x["total_r"], x["win_rate"]), reverse=True), 1):
        flag = "🇹🇭" if b["market"] == "TH" else "🇺🇸"
        r_cls = "text-green" if b["total_r"] >= 0 else "text-red"
        leaderboard_html += f"""
        <tr>
            <td><b>#{rank}</b></td>
            <td>
                <b>{flag} {b['name']}</b>
                <div style="font-size: 11px; color: var(--text-muted);">{b['strategy']}</div>
            </td>
            <td><span class="badge badge-blue">{b['market']}</span></td>
            <td><b>{b['open_count']} ไม้</b></td>
            <td>{b['closed_count']} ไม้</td>
            <td><b>{b['win_rate']:.1f}%</b></td>
            <td><b class="{r_cls}">{b['total_r']:+.2f}R</b></td>
            <td>
                <a href="{b['sub_url']}" class="btn-action" target="_blank">เปิดหน้ารายละเอียด ↗</a>
            </td>
        </tr>
        """

    # Render Closed Trades Rows
    closed_rows_html = ""
    if not all_closed_trades:
        closed_rows_html = '<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 25px;">ยังไม่มีรายการปิดออเดอร์ (ระบบกำลังรัน Forward Test ทุกออเดอร์)</td></tr>'
    else:
        for t in all_closed_trades:
            flag = "🇹🇭" if t["is_thai"] else "🇺🇸"
            cur_sym = "฿" if t["is_thai"] else "$"
            r_cls = "text-green" if t["pnl_r"] >= 0 else "text-red"
            closed_rows_html += f"""
            <tr>
                <td><b>{flag} {t['ticker']}</b></td>
                <td><span class="bot-pill">{t['bot_name']}</span></td>
                <td><code>{t['entry_date']}</code></td>
                <td><code>{t['exit_date']}</code></td>
                <td>{t['entry_price']:.2f} {cur_sym}</td>
                <td>{t['exit_price']:.2f} {cur_sym}</td>
                <td><b class="{r_cls}">{t['pnl_pct']:+.2f}%</b></td>
                <td><b class="{r_cls}">{t['pnl_r']:+.2f}R</b></td>
                <td><span class="badge badge-blue">{t['exit_reason']}</span></td>
            </tr>
            """

    # Assemble Full Page HTML
    html_template = f"""<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>6-BOT FORWARD TEST MASTER DASHBOARD (2026)</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #0a0d14;
            --bg-card: #131722;
            --bg-hover: #1c2233;
            --border: #22293a;
            --border-light: #2d3748;
            --text-main: #f0f3fa;
            --text-muted: #848e9c;
            --green: #00e676;
            --green-dim: rgba(0, 230, 118, 0.12);
            --red: #ff5252;
            --red-dim: rgba(255, 82, 82, 0.12);
            --gold: #ffb300;
            --gold-dim: rgba(255, 179, 0, 0.12);
            --blue: #29b6f6;
            --blue-dim: rgba(41, 182, 246, 0.12);
            --purple: #b388ff;
            --purple-dim: rgba(179, 136, 255, 0.12);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 14px;
            line-height: 1.5;
            padding: 24px 20px;
        }}

        .container {{
            max-width: 1440px;
            margin: 0 auto;
        }}

        /* Header */
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 24px;
        }}

        .header-title h1 {{
            font-size: 24px;
            font-weight: 800;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .header-title p {{
            color: var(--text-muted);
            font-size: 13px;
            margin-top: 4px;
        }}

        .header-actions {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .live-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: var(--green-dim);
            color: var(--green);
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            border: 1px solid rgba(0, 230, 118, 0.3);
        }}

        .pulse-dot {{
            width: 8px;
            height: 8px;
            background: var(--green);
            border-radius: 50%;
            animation: pulse 1.8s infinite;
        }}

        @keyframes pulse {{
            0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 230, 118, 0.7); }}
            70% {{ transform: scale(1); box-shadow: 0 0 0 8px rgba(0, 230, 118, 0); }}
            100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 230, 118, 0); }}
        }}

        /* KPI Cards */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}

        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            position: relative;
            overflow: hidden;
            transition: transform 0.2s, border-color 0.2s;
        }}

        .kpi-card:hover {{
            transform: translateY(-2px);
            border-color: var(--border-light);
        }}

        .kpi-title {{
            font-size: 12px;
            text-transform: uppercase;
            font-weight: 600;
            color: var(--text-muted);
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}

        .kpi-value {{
            font-size: 28px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            display: flex;
            align-items: baseline;
            gap: 8px;
        }}

        .kpi-sub {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 6px;
        }}

        /* Navigation Tabs */
        .tab-nav {{
            display: flex;
            gap: 8px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 20px;
            overflow-x: auto;
            padding-bottom: 4px;
        }}

        .tab-btn {{
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 10px 18px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
            white-space: nowrap;
        }}

        .tab-btn.active {{
            background: var(--bg-card);
            color: var(--text-main);
            border: 1px solid var(--border);
        }}

        .tab-btn:hover:not(.active) {{
            color: var(--text-main);
            background: var(--bg-hover);
        }}

        /* Filter Controls */
        .filter-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 18px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: 12px 16px;
            border-radius: 10px;
        }}

        .filter-pills {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}

        .pill-btn {{
            background: var(--bg-base);
            border: 1px solid var(--border);
            color: var(--text-muted);
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s;
        }}

        .pill-btn.active, .pill-btn:hover {{
            background: var(--blue-dim);
            color: var(--blue);
            border-color: rgba(41, 182, 246, 0.4);
        }}

        .search-box {{
            background: var(--bg-base);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 7px 14px;
            border-radius: 8px;
            font-size: 13px;
            width: 220px;
            outline: none;
        }}

        .search-box:focus {{
            border-color: var(--blue);
        }}

        /* Table Card */
        .table-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 28px;
        }}

        .table-container {{
            width: 100%;
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}

        th {{
            background: #10141e;
            color: var(--text-muted);
            font-size: 11px;
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.5px;
            padding: 14px 16px;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }}

        td {{
            padding: 14px 16px;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
            white-space: nowrap;
        }}

        tr:hover td {{
            background: var(--bg-hover);
        }}

        /* Badges & Pills */
        .ticker-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 14px;
            cursor: pointer;
            color: var(--blue);
        }}

        .ticker-badge:hover {{
            text-decoration: underline;
        }}

        .bot-pill {{
            background: var(--bg-base);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
        }}

        .badge-green {{ background: var(--green-dim); color: var(--green); border: 1px solid rgba(0, 230, 118, 0.2); }}
        .badge-red {{ background: var(--red-dim); color: var(--red); border: 1px solid rgba(255, 82, 82, 0.2); }}
        .badge-gold {{ background: var(--gold-dim); color: var(--gold); border: 1px solid rgba(255, 179, 0, 0.2); }}
        .badge-blue {{ background: var(--blue-dim); color: var(--blue); border: 1px solid rgba(41, 182, 246, 0.2); }}
        .badge-purple {{ background: var(--purple-dim); color: var(--purple); border: 1px solid rgba(179, 136, 255, 0.2); }}

        .text-green {{ color: var(--green); }}
        .text-red {{ color: var(--red); }}
        .text-gold {{ color: var(--gold); }}

        .btn-action {{
            background: var(--bg-base);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.15s;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }}

        .btn-action:hover {{
            background: var(--blue-dim);
            color: var(--blue);
            border-color: rgba(41, 182, 246, 0.4);
        }}

        /* Sub-Dashboards Links Grid */
        .launcher-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}

        .launcher-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: all 0.2s;
            text-decoration: none;
            color: var(--text-main);
        }}

        .launcher-card:hover {{
            transform: translateY(-2px);
            border-color: var(--blue);
            background: var(--bg-hover);
        }}

        .launcher-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}

        .launcher-title {{
            font-size: 16px;
            font-weight: 700;
        }}

        .launcher-sub {{
            font-size: 12px;
            color: var(--text-muted);
            margin-bottom: 16px;
        }}

        /* Modal */
        .modal {{
            display: none;
            position: fixed;
            z-index: 999;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.85);
            backdrop-filter: blur(4px);
            align-items: center;
            justify-content: center;
        }}

        .modal-content {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            width: 90%;
            max-width: 1000px;
            height: 650px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            box-shadow: 0 20px 40px rgba(0,0,0,0.6);
        }}

        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
        }}

        .modal-title {{
            font-size: 16px;
            font-weight: 700;
        }}

        .close-btn {{
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-size: 20px;
            cursor: pointer;
        }}

        .close-btn:hover {{
            color: var(--text-main);
        }}

        .modal-body {{
            flex: 1;
            padding: 0;
            background: #10141e;
        }}

        /* Footer */
        .footer {{
            text-align: center;
            padding-top: 24px;
            border-top: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="header">
            <div class="header-title">
                <h1>🚀 6-BOT FORWARD TEST MASTER DASHBOARD</h1>
                <p>ระบบติดตามและประเมินผลการเทรดแบบ Forward Test รวม 6 บอท (ตลาดสหรัฐฯ & ตลาดหุ้นไทย) ตลอดปี 2026</p>
            </div>
            <div class="header-actions">
                <div class="live-badge">
                    <div class="pulse-dot"></div>
                    LIVE FORWARD TEST
                </div>
                <button class="btn-action" onclick="location.reload()">🔄 รีเฟรช</button>
            </div>
        </header>

        <!-- KPI Grid -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-title">💼 หุ้นที่ถืออยู่ในพอร์ตทั้งหมด</div>
                <div class="kpi-value text-green">{total_open} <span style="font-size: 14px; color: var(--text-muted);">ตัว</span></div>
                <div class="kpi-sub">🇹🇭 หุ้นไทย: <b>{th_open_count}</b> | 🇺🇸 หุ้น US: <b>{us_open_count}</b></div>
            </div>

            <div class="kpi-card">
                <div class="kpi-title">📈 UNREALIZED R รวม (กำไรลอยตัว)</div>
                <div class="kpi-value {'text-green' if total_unrealized_r >= 0 else 'text-red'}">
                    {total_unrealized_r:+.2f}R
                </div>
                <div class="kpi-sub">คำนวณจากทุกไม้ที่กำลังถืออยู่เทียบความเสี่ยงต่อไม้ (R)</div>
            </div>

            <div class="kpi-card">
                <div class="kpi-title">🏆 WIN RATE (ไม้ที่ปิดออเดอร์แล้ว)</div>
                <div class="kpi-value">{overall_win_rate:.1f}%</div>
                <div class="kpi-sub">ปิดแล้ว: <b>{total_closed}</b> ไม้ (ชนะ {len(overall_wins)} / แพ้ {total_closed - len(overall_wins)})</div>
            </div>

            <div class="kpi-card">
                <div class="kpi-title">🛡️ REALIZED NET PROFIT</div>
                <div class="kpi-value {'text-green' if overall_net_r >= 0 else 'text-red'}">
                    {overall_net_r:+.2f}R
                </div>
                <div class="kpi-sub">ผลกำไรสุทธิสะสมจากออเดอร์ที่ปิดจริง (R-Multiples)</div>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <div class="tab-nav">
            <button class="tab-btn active" onclick="switchTab('tab-portfolio')">💼 พอร์ตหุ้นรวม ({total_open})</button>
            <button class="tab-btn" onclick="switchTab('tab-leaderboard')">📊 ตารางเปรียบเทียบ 6 บอท</button>
            <button class="tab-btn" onclick="switchTab('tab-history')">📜 ประวัติการปิดออเดอร์ ({total_closed})</button>
            <button class="tab-btn" onclick="switchTab('tab-launchers')">🔗 เข้าหน้ารายละเอียดแยกบอท</button>
        </div>

        <!-- TAB 1: Master Active Portfolio -->
        <div id="tab-portfolio" class="tab-section">
            <div class="filter-bar">
                <div class="filter-pills">
                    <button class="pill-btn active" onclick="filterPositions('all', this)">ทั้งหมด ({total_open})</button>
                    <button class="pill-btn" onclick="filterPositions('th', this)">🇹🇭 หุ้นไทย ({th_open_count})</button>
                    <button class="pill-btn" onclick="filterPositions('us', this)">🇺🇸 สหรัฐฯ ({us_open_count})</button>
                    <button class="pill-btn" onclick="filterPositions('bot1', this)">Bot 1 (US 6-Btn)</button>
                    <button class="pill-btn" onclick="filterPositions('bot2', this)">Bot 2 (TH 6-Btn)</button>
                    <button class="pill-btn" onclick="filterPositions('bot3', this)">Bot 3 (US Pullback)</button>
                    <button class="pill-btn" onclick="filterPositions('bot4', this)">Bot 4 (TH Pullback)</button>
                    <button class="pill-btn" onclick="filterPositions('bot5', this)">Bot 5 (US Hybrid)</button>
                    <button class="pill-btn" onclick="filterPositions('bot6', this)">Bot 6 (TH Hybrid)</button>
                </div>
                <input type="text" class="search-box" id="search-input" placeholder="🔍 ค้นหาชื่อหุ้น..." onkeyup="searchPositions()">
            </div>

            <div class="table-card">
                <div class="table-container">
                    <table id="positions-table">
                        <thead>
                            <tr>
                                <th>หุ้น</th>
                                <th>บอทที่เปิดออเดอร์</th>
                                <th>วันที่เข้า</th>
                                <th>ราคาเข้า</th>
                                <th>ราคาล่าสุด</th>
                                <th>PnL (%)</th>
                                <th>PnL (R)</th>
                                <th>Stop Loss</th>
                                <th>เป้า 3R</th>
                                <th>เป้า 5R</th>
                                <th>จำนวนหุ้น</th>
                                <th>สถานะ</th>
                                <th>ชาร์ต</th>
                            </tr>
                        </thead>
                        <tbody>
                            {active_rows_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- TAB 2: Leaderboard -->
        <div id="tab-leaderboard" class="tab-section" style="display: none;">
            <div class="table-card">
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>อันดับ</th>
                                <th>ชื่อบอท & กลยุทธ์</th>
                                <th>ตลาด</th>
                                <th>ถืออยู่</th>
                                <th>ปิดแล้ว</th>
                                <th>Win Rate</th>
                                <th>Net Realized R</th>
                                <th>หน้าจอแยก</th>
                            </tr>
                        </thead>
                        <tbody>
                            {leaderboard_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- TAB 3: Closed Trades History -->
        <div id="tab-history" class="tab-section" style="display: none;">
            <div class="table-card">
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>หุ้น</th>
                                <th>บอท</th>
                                <th>วันที่เข้า</th>
                                <th>วันที่ออก</th>
                                <th>ราคาเข้า</th>
                                <th>ราคาออก</th>
                                <th>PnL (%)</th>
                                <th>PnL (R)</th>
                                <th>เหตุผลที่ปิด</th>
                            </tr>
                        </thead>
                        <tbody>
                            {closed_rows_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- TAB 4: Launchers -->
        <div id="tab-launchers" class="tab-section" style="display: none;">
            <div class="launcher-grid">
                <a href="bot1.html" class="launcher-card" target="_blank">
                    <div>
                        <div class="launcher-header">
                            <span class="launcher-title">🇺🇸 Bot 1: US 6-Button</span>
                            <span class="badge badge-blue">Momentum</span>
                        </div>
                        <div class="launcher-sub">กลยุทธ์กระดุม 6 เม็ด ตลาดหุ้นสหรัฐฯ พร้อมระบบสแกน 3 โซน</div>
                    </div>
                    <span class="btn-action">เปิดแดชบอร์ด Bot 1 ↗</span>
                </a>

                <a href="https://mjchatchai.github.io/thai-stocks-alert/" class="launcher-card" target="_blank">
                    <div>
                        <div class="launcher-header">
                            <span class="launcher-title">🇹🇭 Bot 2: TH 6-Button</span>
                            <span class="badge badge-blue">Momentum</span>
                        </div>
                        <div class="launcher-sub">กลยุทธ์กระดุม 6 เม็ด ตลาดหุ้นไทย SET Leaders</div>
                    </div>
                    <span class="btn-action">เปิดแดชบอร์ด Bot 2 ↗</span>
                </a>

                <a href="bot3.html" class="launcher-card" target="_blank">
                    <div>
                        <div class="launcher-header">
                            <span class="launcher-title">🇺🇸 Bot 3: US Pullback</span>
                            <span class="badge badge-green">Trend Retest</span>
                        </div>
                        <div class="launcher-sub">สแกนหุ้นย่อตัวในแนวรับ Confluence (EMA21 / AVWAP) หุ้น US</div>
                    </div>
                    <span class="btn-action">เปิดแดชบอร์ด Bot 3 ↗</span>
                </a>

                <a href="bot4.html" class="launcher-card" target="_blank">
                    <div>
                        <div class="launcher-header">
                            <span class="launcher-title">🇹🇭 Bot 4: TH Pullback</span>
                            <span class="badge badge-green">Trend Retest</span>
                        </div>
                        <div class="launcher-sub">สแกนหุ้นย่อตัวในแนวรับ Confluence ตลาดหุ้นไทย</div>
                    </div>
                    <span class="btn-action">เปิดแดชบอร์ด Bot 4 ↗</span>
                </a>

                <a href="bot5.html" class="launcher-card" target="_blank">
                    <div>
                        <div class="launcher-header">
                            <span class="launcher-title">🇺🇸 Bot 5: US Hybrid</span>
                            <span class="badge badge-purple">Multi-Factor</span>
                        </div>
                        <div class="launcher-sub">ระบบผสมผสาน โมเมนตัม + ย่อตัว + Macro Trend หุ้น US</div>
                    </div>
                    <span class="btn-action">เปิดแดชบอร์ด Bot 5 ↗</span>
                </a>

                <a href="bot6.html" class="launcher-card" target="_blank">
                    <div>
                        <div class="launcher-header">
                            <span class="launcher-title">🇹🇭 Bot 6: TH Hybrid</span>
                            <span class="badge badge-purple">Multi-Factor</span>
                        </div>
                        <div class="launcher-sub">ระบบผสมผสาน โมเมนตัม + ย่อตัว + SET Trend หุ้นไทย</div>
                    </div>
                    <span class="btn-action">เปิดแดชบอร์ด Bot 6 ↗</span>
                </a>
            </div>
        </div>

        <!-- TradingView Modal -->
        <div id="chart-modal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <span class="modal-title" id="modal-ticker-title">TradingView Chart</span>
                    <button class="close-btn" onclick="closeModal()">&times;</button>
                </div>
                <div class="modal-body" id="modal-body">
                    <!-- Embedded iframe will load here -->
                </div>
            </div>
        </div>

        <!-- Footer -->
        <footer class="footer">
            <p>6-Bot Forward Testing Engine • Data as of <code>{now_str}</code> • Auto-refreshes on GitHub Actions schedule</p>
        </footer>
    </div>

    <script>
        function switchTab(tabId) {{
            document.querySelectorAll('.tab-section').forEach(el => el.style.display = 'none');
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById(tabId).style.display = 'block';
            event.currentTarget.classList.add('active');
        }}

        function filterPositions(filter, btn) {{
            document.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const rows = document.querySelectorAll('#positions-table tbody tr');
            rows.forEach(r => {{
                if (filter === 'all') {{
                    r.style.display = '';
                }} else if (filter === 'th') {{
                    r.style.display = r.classList.contains('mkt-th') ? '' : 'none';
                }} else if (filter === 'us') {{
                    r.style.display = r.classList.contains('mkt-us') ? '' : 'none';
                }} else {{
                    r.style.display = r.classList.contains(filter) ? '' : 'none';
                }}
            }});
        }}

        function searchPositions() {{
            const val = document.getElementById('search-input').value.toUpperCase();
            const rows = document.querySelectorAll('#positions-table tbody tr');
            rows.forEach(r => {{
                const text = r.innerText.toUpperCase();
                r.style.display = text.indexOf(val) > -1 ? '' : 'none';
            }});
        }}

        function openTradingViewModal(symbol) {{
            document.getElementById('modal-ticker-title').innerText = '📊 กราฟหุ้น: ' + symbol;
            const container = document.getElementById('modal-body');
            container.innerHTML = '<iframe src="https://s.tradingview.com/widgetembed/?symbol=' + encodeURIComponent(symbol) + '&interval=D&hidesidetoolbar=0&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=[]&theme=dark&style=1&timezone=Asia%2FBangkok" style="width: 100%; height: 100%; border: none;"></iframe>';
            document.getElementById('chart-modal').style.display = 'flex';
        }}

        function closeModal() {{
            document.getElementById('chart-modal').style.display = 'none';
            document.getElementById('modal-body').innerHTML = '';
        }}

        window.onclick = function(event) {{
            const modal = document.getElementById('chart-modal');
            if (event.target == modal) {{
                closeModal();
            }}
        }}
    </script>
</body>
</html>
"""

    out_path = os.path.join(DOCS_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_template)
        
    print(f"Master Dashboard saved successfully to {out_path} ({len(html_template)} bytes)")

if __name__ == "__main__":
    build_master_dashboard()
