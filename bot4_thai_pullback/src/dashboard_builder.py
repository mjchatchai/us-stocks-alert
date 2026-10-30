"""
Dashboard Builder for Bot 4 (Thai Stocks Pullback & R-Multiple Strategy)
Generates an interactive, dark-themed responsive HTML dashboard.
"""

import json
import os
from typing import Dict, List, Optional


def build_dashboard_html(
    config: Dict,
    buy_signals: List[Dict],
    pullback_candidates: List[Dict],
    all_screened: List[Dict],
    active_positions: Dict,
    trade_history: List[Dict],
    last_scan_date: str,
    output_path: str = "bot4_thai_pullback/docs/index.html",
) -> str:
    """Build and write the standalone HTML dashboard for Thai stocks."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    equity = float(config.get("portfolio_equity", 1000000.0))
    risk_pct = float(config.get("risk_per_trade_pct", 0.5))
    baht_risk = equity * (risk_pct / 100.0)

    total_realized_pnl = sum(t.get("realized_pnl", 0.0) for t in trade_history)
    wins = [t for t in trade_history if t.get("realized_pnl", 0.0) > 0]
    win_rate = round(len(wins) / len(trade_history) * 100.0, 1) if trade_history else 0.0

    active_list = list(active_positions.values())
    total_unrealized_pnl = sum(p.get("unrealized_pnl", 0.0) for p in active_list)

    html_content = f"""<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BOT 4: Thai Stocks Pullback & R-Multiple Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-dark: #0b0e14;
            --card-bg: #151922;
            --card-border: #232936;
            --accent-green: #00e676;
            --accent-blue: #00bcd4;
            --accent-red: #ff5252;
            --accent-gold: #ffd700;
            --text-main: #f0f3f8;
            --text-muted: #8b949e;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg-dark);
            color: var(--text-main);
            font-family: 'Inter', -apple-system, sans-serif;
            padding: 24px;
            min-height: 100vh;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--card-border);
            padding-bottom: 20px;
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .title-group h1 {{
            font-size: 24px;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .title-group p {{
            color: var(--text-muted);
            font-size: 14px;
            margin-top: 4px;
        }}
        .badge {{
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .badge-green {{ background: rgba(0, 230, 118, 0.15); color: var(--accent-green); border: 1px solid var(--accent-green); }}
        .badge-blue {{ background: rgba(0, 188, 212, 0.15); color: var(--accent-blue); border: 1px solid var(--accent-blue); }}
        .badge-gold {{ background: rgba(255, 215, 0, 0.15); color: var(--accent-gold); border: 1px solid var(--accent-gold); }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .metric-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 16px 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }}
        .metric-card .label {{
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 6px;
        }}
        .metric-card .value {{
            font-size: 22px;
            font-weight: 700;
            color: #fff;
        }}
        .text-green {{ color: var(--accent-green) !important; }}
        .text-red {{ color: var(--accent-red) !important; }}
        .text-gold {{ color: var(--accent-gold) !important; }}

        .tabs {{
            display: flex;
            gap: 8px;
            border-bottom: 1px solid var(--card-border);
            margin-bottom: 20px;
            overflow-x: auto;
        }}
        .tab-btn {{
            background: none;
            border: none;
            color: var(--text-muted);
            padding: 12px 18px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
            white-space: nowrap;
        }}
        .tab-btn:hover {{ color: #fff; }}
        .tab-btn.active {{
            color: var(--accent-green);
            border-bottom-color: var(--accent-green);
        }}

        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}

        .data-table-container {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            overflow-x: auto;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13.5px;
            text-align: left;
        }}
        th {{
            background: #1a202c;
            color: var(--text-muted);
            padding: 12px 16px;
            font-weight: 600;
            border-bottom: 1px solid var(--card-border);
            text-transform: uppercase;
            font-size: 11.5px;
            letter-spacing: 0.5px;
        }}
        td {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--card-border);
            color: var(--text-main);
        }}
        tr:hover td {{ background: rgba(255, 255, 255, 0.02); }}
        .ticker-link {{
            color: var(--accent-blue);
            font-weight: 700;
            text-decoration: none;
            cursor: pointer;
        }}
        .ticker-link:hover {{ text-decoration: underline; }}

        .btn-action {{
            background: #232936;
            color: #fff;
            border: 1px solid #384252;
            padding: 5px 10px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            transition: 0.2s;
        }}
        .btn-action:hover {{ background: var(--accent-green); color: #000; border-color: var(--accent-green); }}

        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0; top: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.85);
            align-items: center;
            justify-content: center;
        }}
        .modal-content {{
            max-width: 900px;
            width: 92%;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 20px;
            position: relative;
        }}
        .modal-close {{
            position: absolute;
            right: 16px; top: 12px;
            font-size: 24px;
            color: var(--text-muted);
            cursor: pointer;
        }}
        .modal img {{
            width: 100%;
            border-radius: 8px;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="title-group">
            <h1>🇹🇭 BOT 4: หุ้นไทย (SET) Pullback & R-Multiple <span class="badge badge-green">พอร์ต 1,000,000 ฿</span></h1>
            <p>ระบบคัดกรองหุ้นนำตลาด + ย่อทดสอบแนวรับรอบแรก (First Retest) + บริหารความเสี่ยง Board Lot (100 หุ้น) และเป้า 3R/5R</p>
        </div>
        <div>
            <span class="badge badge-blue">Last Scan: {last_scan_date}</span>
        </div>
    </div>

    <!-- Metrics Overview -->
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="label">💼 พอร์ตโฟลิโอเริ่มต้น</div>
            <div class="value">{equity:,.0f} ฿</div>
        </div>
        <div class="metric-card">
            <div class="label">🎯 งบเสี่ยงต่อไม้ (0.5%)</div>
            <div class="value text-gold">{baht_risk:,.0f} ฿</div>
        </div>
        <div class="metric-card">
            <div class="label">🚀 สัญญาณซื้อวันนี้</div>
            <div class="value text-green">{len(buy_signals)}</div>
        </div>
        <div class="metric-card">
            <div class="label">📦 ออเดอร์ที่ถืออยู่ (Active)</div>
            <div class="value">{len(active_list)}</div>
        </div>
        <div class="metric-card">
            <div class="label">💵 กำไรที่รับรู้แล้ว (Realized)</div>
            <div class="value {'text-green' if total_realized_pnl >= 0 else 'text-red'}">{total_realized_pnl:+,.0f} ฿</div>
        </div>
        <div class="metric-card">
            <div class="label">🏆 Win Rate</div>
            <div class="value">{win_rate}%</div>
        </div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('tab-signals')">🚀 สัญญาณซื้อวันนี้ ({len(buy_signals)})</button>
        <button class="tab-btn" onclick="switchTab('tab-active')">💼 ออเดอร์ที่ถืออยู่ ({len(active_list)})</button>
        <button class="tab-btn" onclick="switchTab('tab-pullback')">📍 หุ้นจ่อแนวรับ & Watchlist ({len(pullback_candidates)})</button>
        <button class="tab-btn" onclick="switchTab('tab-screener')">⭐ หุ้นแกร่ง VCP [1/4] ({len(all_screened)})</button>
        <button class="tab-btn" onclick="switchTab('tab-history')">📜 ประวัติการเทรด ({len(trade_history)})</button>
    </div>

    <!-- Tab 1: Buy Signals Today -->
    <div id="tab-signals" class="tab-content active">
        <div class="data-table-container">
            <table>
                <thead>
                    <tr>
                        <th>หุ้น (Ticker)</th>
                        <th>ราคาปัจจุบัน</th>
                        <th>🛑 Stop Loss (SL)</th>
                        <th>1R Risk</th>
                        <th>🎯 เป้า 3R</th>
                        <th>🎯 เป้า 5R</th>
                        <th>📦 จำนวนหุ้น (Lot 100)</th>
                        <th>💵 เงินลงทุน (บาท)</th>
                        <th>% พอร์ต</th>
                        <th>กราฟ</th>
                    </tr>
                </thead>
                <tbody>
"""

    if not buy_signals:
        html_content += """<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 30px;">วันนี้ยังไม่มีสัญญาณเข้าซื้อใหม่ที่ตรงเงื่อนไขครบทุกข้อ (รอแท่งยืนยันแนวรับ)</td></tr>"""
    else:
        for s in buy_signals:
            plan = s["plan"]
            setup = s["setup"]
            tk = plan.ticker
            html_content += f"""
                    <tr>
                        <td><a class="ticker-link" onclick="openChartModal('{tk}')"><b>{tk}</b></a></td>
                        <td><b>{plan.entry_price:.2f} ฿</b></td>
                        <td class="text-red"><b>{plan.stop_loss:.2f} ฿</b> (-{plan.risk_pct:.1f}%)</td>
                        <td>{plan.risk_per_share:.2f} ฿</td>
                        <td class="text-gold"><b>{plan.target_3r:.2f} ฿</b></td>
                        <td class="text-green"><b>{plan.target_5r:.2f} ฿</b></td>
                        <td><b class="text-green">{plan.shares:,} หุ้น</b></td>
                        <td>{plan.capital_allocated:,.0f} ฿</td>
                        <td>{plan.allocation_pct:.1f}%</td>
                        <td><button class="btn-action" onclick="openChartModal('{tk}')">📊 ดูกราฟ</button></td>
                    </tr>
            """

    html_content += f"""
                </tbody>
            </table>
        </div>
    </div>

    <!-- Tab 2: Active Positions -->
    <div id="tab-active" class="tab-content">
        <div class="data-table-container">
            <table>
                <thead>
                    <tr>
                        <th>หุ้น</th>
                        <th>ทุนเฉลี่ย</th>
                        <th>ราคาล่าสุด</th>
                        <th>หุ้นที่เหลือ</th>
                        <th>Stop Loss</th>
                        <th>เป้า 3R</th>
                        <th>เป้า 5R</th>
                        <th>R-Multiple</th>
                        <th>Unrealized P/L</th>
                        <th>สถานะ</th>
                        <th>กราฟ</th>
                    </tr>
                </thead>
                <tbody>
"""
    if not active_list:
        html_content += """<tr><td colspan="11" style="text-align: center; color: var(--text-muted); padding: 30px;">ยังไม่มีสถานะที่เปิดอยู่</td></tr>"""
    else:
        for p in active_list:
            tk = p["ticker"]
            r_val = p.get("current_r", 0.0)
            u_pnl = p.get("unrealized_pnl", 0.0)
            status_badge = '<span class="badge badge-blue">รันเทรนด์</span>'
            if p.get("tp2_hit"):
                status_badge = '<span class="badge badge-green">5R สำเร็จ (รัน EMA9)</span>'
            elif p.get("tp1_hit"):
                status_badge = '<span class="badge badge-gold">3R สำเร็จ (SL ทุน)</span>'

            html_content += f"""
                    <tr>
                        <td><a class="ticker-link" onclick="openChartModal('{tk}')"><b>{tk}</b></a></td>
                        <td>{p['entry_price']:.2f} ฿</td>
                        <td><b>{p.get('current_price', p['entry_price']):.2f} ฿</b></td>
                        <td><b>{p['current_shares']:,}</b> / {p.get('initial_shares', p['current_shares']):,}</td>
                        <td class="text-red">{p['current_sl']:.2f} ฿</td>
                        <td class="text-gold">{p['target_3r']:.2f} ฿</td>
                        <td class="text-green">{p['target_5r']:.2f} ฿</td>
                        <td><b class="{'text-green' if r_val >= 0 else 'text-red'}">{r_val:+.2f}R</b></td>
                        <td><b class="{'text-green' if u_pnl >= 0 else 'text-red'}">{u_pnl:+,.0f} ฿</b></td>
                        <td>{status_badge}</td>
                        <td><button class="btn-action" onclick="openChartModal('{tk}')">📊 กราฟ</button></td>
                    </tr>
            """

    html_content += f"""
                </tbody>
            </table>
        </div>
    </div>

    <!-- Tab 3: Pullback & Support Setups -->
    <div id="tab-pullback" class="tab-content">
        <div class="data-table-container">
            <table>
                <thead>
                    <tr>
                        <th>หุ้น</th>
                        <th>ราคาปิด</th>
                        <th>RS Rank</th>
                        <th>โซนแนวรับ Confluence</th>
                        <th>EMA 9</th>
                        <th>EMA 21</th>
                        <th>AVWAP</th>
                        <th>First Retest?</th>
                        <th>จุด Trigger เบรกซื้อ</th>
                        <th>กราฟ</th>
                    </tr>
                </thead>
                <tbody>
"""
    if not pullback_candidates:
        html_content += """<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 30px;">ไม่มีหุ้นในโซนแนวรับขณะนี้</td></tr>"""
    else:
        for pb in pullback_candidates:
            tk = pb["ticker"]
            setup = pb["setup"]
            retest_badge = '<span class="badge badge-green">รอบแรก (First)</span>' if setup["is_first_retest"] else '<span class="badge badge-blue">ทั่วไป</span>'
            html_content += f"""
                    <tr>
                        <td><a class="ticker-link" onclick="openChartModal('{tk}')"><b>{tk}</b></a></td>
                        <td><b>{setup['curr_close']:.2f} ฿</b></td>
                        <td><b>{pb.get('rs_percentile', 0)}%</b></td>
                        <td class="text-green">{setup['zone_bottom']:.2f} - {setup['zone_top']:.2f} ฿</td>
                        <td>{setup['ema9']:.2f}</td>
                        <td>{setup['ema21']:.2f}</td>
                        <td>{setup['avwap']:.2f}</td>
                        <td>{retest_badge}</td>
                        <td><b class="text-gold">{setup['prior_high']:.2f} ฿</b></td>
                        <td><button class="btn-action" onclick="openChartModal('{tk}')">📊 กราฟ</button></td>
                    </tr>
            """

    html_content += f"""
                </tbody>
            </table>
        </div>
    </div>

    <!-- Tab 4: VCP Screener [1/4] -->
    <div id="tab-screener" class="tab-content">
        <div class="data-table-container">
            <table>
                <thead>
                    <tr>
                        <th>หุ้น</th>
                        <th>ราคา</th>
                        <th>RS Percentile</th>
                        <th>ผลตอบแทน 1M</th>
                        <th>ผลตอบแทน 3M</th>
                        <th>ผลตอบแทน 6M</th>
                        <th>มูลค่าซื้อขายเฉลี่ย 20D</th>
                        <th>ยก Low?</th>
                        <th>VCP บีบแคบ?</th>
                        <th>EMA9/21 ชี้ขึ้น?</th>
                    </tr>
                </thead>
                <tbody>
"""
    for sc in all_screened[:30]:
        tk = sc["ticker"]
        hl_icon = "🟢 ยก Low" if sc.get("higher_low_ok") else "⚪"
        vcp_icon = f"🟢 บีบแคบ ({sc.get('vcp_ratio', 1.0)}x)" if sc.get("vcp_ok") else "⚪ ปกติ"
        slope_icon = "🟢 ชี้ขึ้น" if sc.get("ema_flattening_or_up") else "🔴 ชี้ลง"
        to_mb = sc.get('turnover_20', 0) / 1000000.0
        html_content += f"""
                    <tr>
                        <td><a class="ticker-link" onclick="openChartModal('{tk}')"><b>{tk}</b></a></td>
                        <td>{sc['close']:.2f} ฿</td>
                        <td><b>{sc.get('rs_percentile', 0)}%</b></td>
                        <td class="{'text-green' if sc['ret_1m'] >= 0 else 'text-red'}">{sc['ret_1m']:+.1f}%</td>
                        <td class="{'text-green' if sc['ret_3m'] >= 0 else 'text-red'}"><b>{sc['ret_3m']:+.1f}%</b></td>
                        <td class="{'text-green' if sc['ret_6m'] >= 0 else 'text-red'}"><b>{sc['ret_6m']:+.1f}%</b></td>
                        <td>{to_mb:.1f} ล้านบาท/วัน</td>
                        <td>{hl_icon}</td>
                        <td>{vcp_icon}</td>
                        <td>{slope_icon}</td>
                    </tr>
        """

    html_content += """
                </tbody>
            </table>
        </div>
    </div>

    <!-- Tab 5: Trade History -->
    <div id="tab-history" class="tab-content">
        <div class="data-table-container">
            <table>
                <thead>
                    <tr>
                        <th>หุ้น</th>
                        <th>วันที่เข้า</th>
                        <th>วันที่ออก</th>
                        <th>ราคาซื้อ</th>
                        <th>ราคาขาย</th>
                        <th>เหตุผลที่ปิด</th>
                        <th>กำไร/ขาดทุน (บาท)</th>
                        <th>R-Multiple</th>
                    </tr>
                </thead>
                <tbody>
"""
    if not trade_history:
        html_content += """<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 30px;">ยังไม่มีประวัติการปิดออเดอร์</td></tr>"""
    else:
        for th in trade_history:
            tk = th["ticker"]
            pnl = th.get("realized_pnl", 0.0)
            r_mult = th.get("r_multiple", 0.0)
            html_content += f"""
                    <tr>
                        <td><b>{tk}</b></td>
                        <td>{th.get('entry_date', '-')}</td>
                        <td>{th.get('exit_date', '-')}</td>
                        <td>{th.get('entry_price', 0):.2f} ฿</td>
                        <td>{th.get('exit_price', 0):.2f} ฿</td>
                        <td>{th.get('exit_reason', '-')}</td>
                        <td class="{'text-green' if pnl >= 0 else 'text-red'}"><b>{pnl:+,.0f} ฿</b></td>
                        <td class="{'text-green' if r_mult >= 0 else 'text-red'}"><b>{r_mult:+.2f}R</b></td>
                    </tr>
            """

    html_content += """
                </tbody>
            </table>
        </div>
    </div>

    <!-- Chart Modal -->
    <div id="chartModal" class="modal" onclick="closeChartModal()">
        <div class="modal-content" onclick="event.stopPropagation()">
            <span class="modal-close" onclick="closeChartModal()">&times;</span>
            <h2 id="modalTickerTitle" style="font-size: 18px; margin-bottom: 8px;">Chart Preview</h2>
            <img id="modalChartImg" src="" alt="Chart Preview">
        </div>
    </div>

    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.currentTarget.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        }

        function openChartModal(ticker) {
            document.getElementById('modalTickerTitle').innerText = 'Chart: ' + ticker + ' (Thai Stocks Pullback Setup)';
            document.getElementById('modalChartImg').src = 'charts/' + ticker + '.png?' + new Date().getTime();
            document.getElementById('chartModal').style.display = 'flex';
        }

        function closeChartModal() {
            document.getElementById('chartModal').style.display = 'none';
        }
    </script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path
