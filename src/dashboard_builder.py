"""
Builds the interactive Web Dashboard (docs/index.html) for the 6-Button US Stock Strategy.
Separates stocks into 3 distinct sections:
1. 💼 โซนที่ 1: หุ้นในพอร์ต (สั่งซื้อแล้ว — รอจังหวะขายออกเมื่อครบ 6 เม็ดแดง)
2. 🟢 โซนที่ 2: Watchlist ขาขึ้น (KDJ เขียว — รอจังหวะเข้าซื้อเมื่อครบ 6 เม็ดเขียว)
3. 🔴 โซนที่ 3: Watchlist ขาลง (KDJ แดง — พักตัว/ขาลง)
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any


def build_dashboard_html(
    scan_results: List[Dict[str, Any]],
    portfolio: Dict[str, Dict[str, Any]],
    output_html_path: str,
) -> str:
    os.makedirs(os.path.dirname(output_html_path), exist_ok=True)
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data_json = json.dumps(scan_results, ensure_ascii=False)
    portfolio_json = json.dumps(portfolio, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>US Stocks 6-Button Monitor | กระดานเม็ดกระดุม 3 โซน</title>
  <style>
    :root {{
      --bg: #0b0e14;
      --card: #131722;
      --card-hover: #1c2230;
      --border: #2a2e39;
      --text: #e0e3eb;
      --muted: #868993;
      --green: #00e676;
      --green-glow: rgba(0, 230, 118, 0.35);
      --red: #ff1744;
      --red-glow: rgba(255, 23, 68, 0.35);
      --amber: #ffab00;
      --blue: #2962ff;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans Thai", sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 20px;
      line-height: 1.5;
    }}
    .container {{ max-width: 1280px; margin: 0 auto; }}
    header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 20px 24px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      margin-bottom: 16px;
    }}
    .title-group h1 {{
      font-size: 1.45rem;
      font-weight: 700;
      color: #fff;
    }}
    .title-group p {{ color: var(--muted); font-size: 0.9rem; margin-top: 4px; }}
    .legend-box {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      background: #181d2a;
      padding: 12px 16px;
      border-radius: 10px;
      border: 1px solid var(--border);
      margin-bottom: 16px;
      font-size: 0.84rem;
    }}
    .legend-step {{
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      background: #11151f;
      border-radius: 6px;
      border: 1px solid #252a37;
    }}
    .legend-num {{
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: var(--blue);
      color: #fff;
      font-weight: 700;
      font-size: 0.75rem;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }}
    .tg-cmd-bar {{
      background: #141a29;
      border: 1px solid #28334aff;
      border-radius: 10px;
      padding: 10px 16px;
      margin-bottom: 18px;
      font-size: 0.84rem;
      color: #b0bec5;
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      align-items: center;
    }}
    .tg-cmd-bar code {{
      background: #0b0e14;
      color: #ffd740;
      padding: 2px 7px;
      border-radius: 5px;
      font-weight: 600;
    }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 20px;
    }}
    .tabs {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .tab-btn {{
      background: var(--card);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 8px 14px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.88rem;
      font-weight: 600;
      transition: all 0.15s;
    }}
    .tab-btn:hover {{ background: var(--card-hover); }}
    .tab-btn.active {{
      background: var(--blue);
      border-color: var(--blue);
      color: #fff;
    }}
    .search-input {{
      background: var(--card);
      border: 1px solid var(--border);
      color: #fff;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 0.9rem;
      min-width: 240px;
    }}

    /* Zone Sections */
    .zone-section {{
      margin-bottom: 28px;
      border-radius: 14px;
      overflow: hidden;
      background: var(--card);
      border: 1px solid var(--border);
    }}
    .zone-portfolio {{
      border-top: 4px solid var(--amber);
      box-shadow: 0 4px 20px rgba(255, 171, 0, 0.08);
    }}
    .zone-buy {{
      border-top: 4px solid var(--green);
      box-shadow: 0 4px 20px rgba(0, 230, 118, 0.06);
    }}
    .zone-sell {{
      border-top: 4px solid var(--red);
      box-shadow: 0 4px 20px rgba(255, 23, 68, 0.06);
    }}
    .zone-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 20px;
      background: #171c29;
      border-bottom: 1px solid var(--border);
    }}
    .zone-header h2 {{
      font-size: 1.08rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .zone-portfolio .zone-header h2 {{ color: #ffd740; }}
    .zone-buy .zone-header h2 {{ color: var(--green); }}
    .zone-sell .zone-header h2 {{ color: #ff5252; }}
    .zone-count {{
      background: #23293a;
      color: #fff;
      padding: 3px 10px;
      border-radius: 999px;
      font-size: 0.8rem;
      font-weight: 700;
    }}

    .board-table-wrap {{ overflow-x: auto; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 920px;
    }}
    th, td {{
      padding: 14px 16px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    th {{
      background: #131824;
      color: var(--muted);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    tr.stock-row {{ transition: background 0.15s; cursor: pointer; }}
    tr.stock-row:hover {{ background: var(--card-hover); }}
    .ticker-badge {{
      font-weight: 800;
      font-size: 1.05rem;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .side-pill {{
      font-size: 0.7rem;
      padding: 2px 7px;
      border-radius: 4px;
      font-weight: 700;
    }}
    .side-BUY {{ background: rgba(0, 230, 118, 0.15); color: var(--green); border: 1px solid rgba(0,230,118,0.4); }}
    .side-SELL {{ background: rgba(255, 23, 68, 0.15); color: var(--red); border: 1px solid rgba(255,23,68,0.4); }}
    .price-up {{ color: var(--green); font-weight: 600; }}
    .price-down {{ color: var(--red); font-weight: 600; }}

    /* 6 Buttons (เม็ดกระดุม) */
    .button-strip {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .btn-node {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 3px;
      min-width: 48px;
    }}
    .dot-circle {{
      width: 28px;
      height: 28px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.72rem;
      font-weight: 800;
      border: 2px solid #2e3446;
      background: #1a1f2c;
      color: #6c7284;
    }}
    .dot-green {{
      background: radial-gradient(circle at 30% 30%, #69f0ae, #00c853);
      border-color: #00e676;
      color: #051b0e;
      box-shadow: 0 0 10px var(--green-glow);
    }}
    .dot-red {{
      background: radial-gradient(circle at 30% 30%, #ff8a80, #d50000);
      border-color: #ff1744;
      color: #fff;
      box-shadow: 0 0 10px var(--red-glow);
    }}
    .dot-label {{
      font-size: 0.65rem;
      color: var(--muted);
      white-space: nowrap;
    }}
    .status-badge {{
      display: inline-block;
      padding: 5px 10px;
      border-radius: 6px;
      font-size: 0.82rem;
      font-weight: 600;
    }}
    .st-BUY_NOW {{ background: rgba(0, 230, 118, 0.2); color: #00e676; border: 1px solid #00e676; }}
    .st-SELL_NOW {{ background: rgba(255, 23, 68, 0.2); color: #ff5252; border: 1px solid #ff1744; }}
    .st-WAIT_CONFIRM_BUY, .st-WAIT_CONFIRM_SELL {{ background: rgba(255, 171, 0, 0.18); color: #ffd740; border: 1px solid #ffab00; }}
    .st-COUNTING_BUY, .st-COUNTING_SELL {{ background: rgba(41, 98, 255, 0.18); color: #82b1ff; border: 1px solid #2962ff; }}
    .ext-links a {{
      color: var(--text);
      background: #1f2637;
      border: 1px solid var(--border);
      text-decoration: none;
      padding: 5px 9px;
      border-radius: 6px;
      font-size: 0.78rem;
      margin-right: 5px;
      display: inline-block;
    }}
    .ext-links a:hover {{ background: var(--blue); border-color: var(--blue); color: #fff; }}

    /* Modal for Chart & History */
    .modal-backdrop {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.78);
      z-index: 100;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .modal-backdrop.open {{ display: flex; }}
    .modal-content {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      max-width: 1050px;
      width: 100%;
      max-height: 92vh;
      overflow-y: auto;
      padding: 22px;
    }}
    .modal-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--border);
    }}
    .close-btn {{
      background: #262b3d;
      color: #fff;
      border: none;
      padding: 6px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 700;
    }}
    .chart-img {{
      width: 100%;
      border-radius: 10px;
      border: 1px solid var(--border);
      margin-bottom: 16px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>🎯 กระดานเม็ดกระดุม 6 ขั้นตอน — US Stocks (รายงาน 3 โซน)</h1>
        <p>แยกชัดเจน: 1) หุ้นในพอร์ตรอขายออก 2) Watchlist ขาขึ้นรอซื้อ 3) Watchlist ขาลง</p>
      </div>
      <div style="text-align: right; font-size: 0.85rem; color: var(--muted);">
        <div>อัปเดตล่าสุด: <strong style="color:#fff;">{updated_at}</strong></div>
        <div>คลิกที่แถวหุ้นเพื่อดูรูปกราฟ 3 อินดิเคเตอร์และประวัติสัญญาณ</div>
      </div>
    </header>

    <div class="legend-box">
      <div class="legend-step"><span class="legend-num">1</span> <strong>เม็ด 1:</strong> KDJ สีเขียว/แดง</div>
      <div class="legend-step"><span class="legend-num">2</span> <strong>เม็ด 2:</strong> MACD จุดเขียว/แดง</div>
      <div class="legend-step"><span class="legend-num">3</span> <strong>เม็ด 3:</strong> นับแท่งเทียน 1–9</div>
      <div class="legend-step"><span class="legend-num">4</span> <strong>เม็ด 4:</strong> EMA9 ตัด EMA21 (ใน 9 แท่ง)</div>
      <div class="legend-step"><span class="legend-num">5</span> <strong>เม็ด 5:</strong> แท่งถัดไปคอนเฟิร์ม EMA9 ยก/กดจริง</div>
      <div class="legend-step"><span class="legend-num">6</span> <strong>เม็ด 6:</strong> แจ้งเตือนเข้าซื้อ (BUY) / ขายออก (SELL)</div>
    </div>

    <div class="tg-cmd-bar">
      <span>💬 <strong>คำสั่ง Telegram จัดการพอร์ต:</strong></span>
      <span>เมื่อซื้อหุ้นแล้วพิมพ์ <code>/buy ชื่อหุ้น ราคาทุน</code> (เช่น <code>/buy AAPL 348.20</code>)</span>
      <span>เมื่อขายหุ้นแล้วพิมพ์ <code>/sell ชื่อหุ้น</code></span>
      <span>เพิ่ม/ลบ Watchlist: <code>/add NVDA</code> | <code>/remove NVDA</code></span>
    </div>

    <div class="controls">
      <div class="tabs">
        <button class="tab-btn active" onclick="setFilter('ALL', this)">แสดงครบทั้ง 3 โซน</button>
        <button class="tab-btn" onclick="setFilter('PORTFOLIO_ONLY', this)">💼 เฉพาะโซนที่ 1: หุ้นในพอร์ต (รอขาย)</button>
        <button class="tab-btn" onclick="setFilter('BUY_ONLY', this)">🟢 เฉพาะโซนที่ 2: Watchlist ขาขึ้น</button>
        <button class="tab-btn" onclick="setFilter('SELL_ONLY', this)">🔴 เฉพาะโซนที่ 3: Watchlist ขาลง</button>
      </div>
      <input type="text" id="searchInput" class="search-input" placeholder="ค้นหาชื่อหุ้น เช่น TQQQ, NVDA..." oninput="renderZones()" />
    </div>

    <!-- 💼 ZONE 1: MY PORTFOLIO (สั่งซื้อแล้ว รอจังหวะขายออกเมื่อครบ 6 เม็ดแดง) -->
    <div id="portfolioZoneSection" class="zone-section zone-portfolio">
      <div class="zone-header">
        <h2>💼 โซนที่ 1: หุ้นในพอร์ตของฉัน — สั่งซื้อแล้ว รอจังหวะขายออก (เฝ้ากระดุมแดง 1➔6)</h2>
        <span id="portfolioZoneCount" class="zone-count">0 ตัว</span>
      </div>
      <div class="board-table-wrap">
        <table>
          <thead>
            <tr>
              <th>หุ้นในพอร์ต</th>
              <th>ราคาปัจจุบัน / ต้นทุน (P/L)</th>
              <th>กระดุมเฝ้าระวังจุดขายออก (ครบ 6 แดง = ขายทิ้ง)</th>
              <th>คำแนะนำสำหรับหุ้นในพอร์ตวันนี้</th>
              <th>ค่าอินดิเคเตอร์</th>
              <th>เปิดกราฟ</th>
            </tr>
          </thead>
          <tbody id="portfolioBoardBody"></tbody>
        </table>
      </div>
    </div>

    <!-- 🟢 ZONE 2: WATCHLIST ขาขึ้น (รอเข้าซื้อ) -->
    <div id="buyZoneSection" class="zone-section zone-buy">
      <div class="zone-header">
        <h2>🟢 โซนที่ 2: Watchlist ขาขึ้น — เฝ้ารอจุดเข้าซื้อ (KDJ เขียว 1➔6)</h2>
        <span id="buyZoneCount" class="zone-count">0 ตัว</span>
      </div>
      <div class="board-table-wrap">
        <table>
          <thead>
            <tr>
              <th>หุ้น (Ticker)</th>
              <th>ราคาล่าสุด (1D)</th>
              <th>กระดานเม็ดกระดุม 6 ขั้นตอน (ฝั่งซื้อ 🟢)</th>
              <th>สถานะปัจจุบัน</th>
              <th>ค่าอินดิเคเตอร์</th>
              <th>เปิดกราฟ</th>
            </tr>
          </thead>
          <tbody id="buyBoardBody"></tbody>
        </table>
      </div>
    </div>

    <!-- 🔴 ZONE 3: WATCHLIST ขาลง (พักตัว / ขาลง) -->
    <div id="sellZoneSection" class="zone-section zone-sell">
      <div class="zone-header">
        <h2>🔴 โซนที่ 3: Watchlist ขาลง — พักตัว / เทรนด์ขาลง (KDJ แดง 1➔6)</h2>
        <span id="sellZoneCount" class="zone-count">0 ตัว</span>
      </div>
      <div class="board-table-wrap">
        <table>
          <thead>
            <tr>
              <th>หุ้น (Ticker)</th>
              <th>ราคาล่าสุด (1D)</th>
              <th>กระดานเม็ดกระดุม 6 ขั้นตอน (ฝั่งขาย 🔴)</th>
              <th>สถานะปัจจุบัน</th>
              <th>ค่าอินดิเคเตอร์</th>
              <th>เปิดกราฟ</th>
            </tr>
          </thead>
          <tbody id="sellBoardBody"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Stock Chart & Signal History Modal -->
  <div id="stockModal" class="modal-backdrop" onclick="if(event.target===this) closeModal()">
    <div class="modal-content">
      <div class="modal-header">
        <h2 id="modalTitle">รายละเอียดหุ้น</h2>
        <button class="close-btn" onclick="closeModal()">✕ ปิดหน้าต่าง</button>
      </div>
      <div id="modalBody"></div>
    </div>
  </div>

  <script>
    const SCAN_DATA = {data_json};
    const PORTFOLIO = {portfolio_json};
    let currentFilter = 'ALL';

    const ACTION_PRIORITY = {{
      'BUY_NOW': 1,
      'SELL_NOW': 1,
      'WAIT_CONFIRM_BUY': 2,
      'WAIT_CONFIRM_SELL': 2,
      'COUNTING_BUY': 3,
      'COUNTING_SELL': 3,
      'HOLD_BUY': 4,
      'HOLD_SELL': 4,
      'RESET_TO_GREEN': 5,
      'RESET_TO_RED': 5,
      'WATCH_KDJ_GREEN': 6,
      'WATCH_KDJ_RED': 6
    }};

    function setFilter(filterName, btnEl) {{
      currentFilter = filterName;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btnEl.classList.add('active');
      renderZones();
    }}

    function renderButtonStrip(st) {{
      const colors = st.dot_colors || ['W','W','W','W','W','W'];
      const labels = ['KDJ', 'MACD', 'นับแท่ง', 'EMAตัด', 'ยืนยัน', 'สัญญาณ'];
      return `<div class="button-strip">` + colors.map((c, idx) => {{
        const colorClass = (c === 'G' || c === 'BUY_Rocket') ? 'dot-green' : ((c === 'R' || c === 'SELL_Siren') ? 'dot-red' : '');
        const text = c === 'BUY_Rocket' ? '🚀' : (c === 'SELL_Siren' ? '🚨' : (idx + 1));
        return `
          <div class="btn-node">
            <div class="dot-circle ${{colorClass}}">${{text}}</div>
            <span class="dot-label">${{labels[idx]}}</span>
          </div>
        `;
      }}).join('') + `</div>`;
    }}

    function getPortfolioExitAdvice(st) {{
      if (st.side === 'BUY') {{
        return `<span class="status-badge st-BUY_NOW">✅ กราฟยังเขียว — ถือรันกำไรต่อ (ยังไม่มีเม็ดแดงเตือนขาย)</span>`;
      }}
      if (st.action_today === 'SELL_NOW' || st.action_today === 'HOLD_SELL') {{
        return `<span class="status-badge st-SELL_NOW">🚨 ครบ 6 เม็ดแดงแล้ว! แนะนำขายทิ้งออกจากพอร์ต (EXIT NOW)</span>`;
      }}
      if (st.action_today === 'WAIT_CONFIRM_SELL') {{
        return `<span class="status-badge st-WAIT_CONFIRM_SELL">⚠️ เตรียมขายพรุ่งนี้! EMA9 ตัดลง EMA21 แล้ว รอแท่งพรุ่งนี้คอนเฟิร์มครบ 6 เม็ดแดง</span>`;
      }}
      if (st.action_today === 'COUNTING_SELL') {{
        return `<span class="status-badge st-COUNTING_SELL">⏳ เฝ้าระวังย่อตัว! เกิดจุดแดง MACD นับแท่งที่ ${{st.bar_count}}/${{st.max_bars}} (ยังไม่ครบ 6 เม็ดแดง ยังถือต่อ)</span>`;
      }}
      return `<span class="status-badge">👀 KDJ เริ่มย่อเป็นสีแดง (เม็ดแดงที่ 1) — ยังถือต่อ รอเช็คจุดแดง MACD</span>`;
    }}

    function buildPortfolioRowsHtml(items) {{
      if (!items.length) {{
        return `<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:24px;">ยังไม่มีหุ้นในพอร์ต — เมื่อซื้อหุ้นตัวไหนแล้ว พิมพ์ <code>/buy ชื่อหุ้น ราคา</code> ใน Telegram เพื่อย้ายขึ้นมาเฝ้าจุดขายในโซนนี้</td></tr>`;
      }}
      return items.map(item => {{
        const st = item.latest;
        const pInfo = PORTFOLIO[item.ticker] || {{}};
        const buyPrice = parseFloat(pInfo.buy_price || 0);
        let pnlHtml = `<div style="font-size:0.78rem;color:var(--muted);">ไม่ได้ระบุราคาทุน</div>`;
        if (buyPrice > 0) {{
          const pnlPct = ((st.close - buyPrice) / buyPrice) * 100;
          const pnlClass = pnlPct >= 0 ? 'price-up' : 'price-down';
          const sign = pnlPct >= 0 ? '+' : '';
          pnlHtml = `<div style="font-size:0.8rem;">ทุน: $${{buyPrice.toFixed(2)}} (<span class="${{pnlClass}}">${{sign}}${{pnlPct.toFixed(2)}}%</span>)</div>`;
        }}
        return `
          <tr class="stock-row" onclick="openStockModal('${{item.ticker}}')">
            <td>
              <div class="ticker-badge">
                💼 ${{item.ticker}}
                <span class="side-pill side-${{st.side}}">${{st.side}}</span>
              </div>
              <div style="font-size:0.75rem;color:var(--muted);">วันที่ซื้อ: ${{pInfo.buy_date || '-'}}</div>
            </td>
            <td>
              <div style="font-weight:700;font-size:1rem;">$${{st.close.toFixed(2)}}</div>
              ${{pnlHtml}}
            </td>
            <td>${{renderButtonStrip(st)}}</td>
            <td>${{getPortfolioExitAdvice(st)}}</td>
            <td style="font-size:0.78rem;color:var(--muted);">
              <div>EMA9: <b style="color:#ffeb3b">${{st.ema_fast}}</b> | EMA21: <b style="color:#82b1ff">${{st.ema_slow}}</b></div>
              <div>MACD: <b>${{st.macd}}</b> (Sig: ${{st.macd_signal}})</div>
              <div>KDJ J: <b>${{st.kdj_j}}</b> | D: <b>${{st.kdj_d}}</b></div>
            </td>
            <td class="ext-links" onclick="event.stopPropagation()">
              <a href="https://www.tradingview.com/chart/?symbol=${{item.ticker}}" target="_blank">TradingView ↗</a>
              <a href="https://www.webull.com/quote/nasdaq-${{item.ticker.toLowerCase()}}" target="_blank">Webull ↗</a>
            </td>
          </tr>
        `;
      }}).join('');
    }}

    function buildRowsHtml(items) {{
      if (!items.length) {{
        return `<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:24px;">ไม่มีหุ้นในโซนนี้ตามเงื่อนไขที่เลือก</td></tr>`;
      }}
      return items.map(item => {{
        const st = item.latest;
        const chgClass = st.change_pct >= 0 ? 'price-up' : 'price-down';
        const chgSign = st.change_pct >= 0 ? '+' : '';
        return `
          <tr class="stock-row" onclick="openStockModal('${{item.ticker}}')">
            <td>
              <div class="ticker-badge">
                ${{item.ticker}}
                <span class="side-pill side-${{st.side}}">${{st.side}}</span>
              </div>
              <div style="font-size:0.75rem;color:var(--muted);">แท่งล่าสุด: ${{st.date}}</div>
            </td>
            <td>
              <div style="font-weight:700;font-size:1rem;">$${{st.close.toFixed(2)}}</div>
              <div class="${{chgClass}}" style="font-size:0.82rem;">${{chgSign}}${{st.change_pct.toFixed(2)}}%</div>
            </td>
            <td>${{renderButtonStrip(st)}}</td>
            <td><span class="status-badge st-${{st.action_today}}">${{st.status_text}}</span></td>
            <td style="font-size:0.78rem;color:var(--muted);">
              <div>EMA9: <b style="color:#ffeb3b">${{st.ema_fast}}</b> | EMA21: <b style="color:#82b1ff">${{st.ema_slow}}</b></div>
              <div>MACD: <b>${{st.macd}}</b> (Sig: ${{st.macd_signal}})</div>
              <div>KDJ J: <b>${{st.kdj_j}}</b> | D: <b>${{st.kdj_d}}</b></div>
            </td>
            <td class="ext-links" onclick="event.stopPropagation()">
              <a href="https://www.tradingview.com/chart/?symbol=${{item.ticker}}" target="_blank">TradingView ↗</a>
              <a href="https://www.webull.com/quote/nasdaq-${{item.ticker.toLowerCase()}}" target="_blank">Webull ↗</a>
            </td>
          </tr>
        `;
      }}).join('');
    }}

    function sortZoneItems(items) {{
      return items.slice().sort((a, b) => {{
        const pa = ACTION_PRIORITY[a.latest.action_today] || 99;
        const pb = ACTION_PRIORITY[b.latest.action_today] || 99;
        if (pa !== pb) return pa - pb;
        if ((b.latest.bar_count || 0) !== (a.latest.bar_count || 0)) {{
          return (b.latest.bar_count || 0) - (a.latest.bar_count || 0);
        }}
        return a.ticker.localeCompare(b.ticker);
      }});
    }}

    function renderZones() {{
      const q = (document.getElementById('searchInput').value || '').trim().toUpperCase();
      const baseFiltered = SCAN_DATA.filter(item => {{
        if (q && !item.ticker.includes(q)) return false;
        return true;
      }});

      const portfolioTickers = new Set(Object.keys(PORTFOLIO).map(k => k.toUpperCase()));
      const zone1Portfolio = baseFiltered.filter(x => portfolioTickers.has(x.ticker)).sort((a, b) => {{
        const sa = a.latest.side === 'SELL' ? 0 : 1;
        const sb = b.latest.side === 'SELL' ? 0 : 1;
        if (sa !== sb) return sa - sb;
        const pa = ACTION_PRIORITY[a.latest.action_today] || 99;
        const pb = ACTION_PRIORITY[b.latest.action_today] || 99;
        if (pa !== pb) return pa - pb;
        return (b.latest.bar_count || 0) - (a.latest.bar_count || 0);
      }});
      const zone2Buy = sortZoneItems(baseFiltered.filter(x => !portfolioTickers.has(x.ticker) && x.latest.side === 'BUY'));
      const zone3Sell = sortZoneItems(baseFiltered.filter(x => !portfolioTickers.has(x.ticker) && x.latest.side === 'SELL'));

      document.getElementById('portfolioZoneSection').style.display = (['BUY_ONLY', 'SELL_ONLY'].includes(currentFilter)) ? 'none' : 'block';
      document.getElementById('buyZoneSection').style.display = (['PORTFOLIO_ONLY', 'SELL_ONLY'].includes(currentFilter)) ? 'none' : 'block';
      document.getElementById('sellZoneSection').style.display = (['PORTFOLIO_ONLY', 'BUY_ONLY'].includes(currentFilter)) ? 'none' : 'block';

      document.getElementById('portfolioZoneCount').innerText = `${{zone1Portfolio.length}} ตัว`;
      document.getElementById('buyZoneCount').innerText = `${{zone2Buy.length}} ตัว`;
      document.getElementById('sellZoneCount').innerText = `${{zone3Sell.length}} ตัว`;

      document.getElementById('portfolioBoardBody').innerHTML = buildPortfolioRowsHtml(zone1Portfolio);
      document.getElementById('buyBoardBody').innerHTML = buildRowsHtml(zone2Buy);
      document.getElementById('sellBoardBody').innerHTML = buildRowsHtml(zone3Sell);
    }}

    function openStockModal(ticker) {{
      const item = SCAN_DATA.find(x => x.ticker === ticker);
      if (!item) return;
      document.getElementById('modalTitle').innerText = `${{ticker}} — กราฟ 3 อินดิเคเตอร์ & ประวัติการเกิดสัญญาณครบ 6 เม็ด`;
      const signalsHtml = (item.recent_signals || []).map(sig => `
        <tr>
          <td>${{sig.date}}</td>
          <td><span class="side-pill side-${{sig.side}}">${{sig.action_today}}</span></td>
          <td>$${{sig.close.toFixed(2)}}</td>
          <td>${{sig.buttons_visual}}</td>
          <td>จุด MACD: ${{sig.macd_dot_date || '-'}} | วัน EMA ตัด: ${{sig.ema_cross_date || '-'}}</td>
        </tr>
      `).join('') || '<tr><td colspan="5" style="text-align:center;color:var(--muted);">ยังไม่มีสัญญาณครบ 6 เม็ดในช่วงที่ดึงข้อมูล</td></tr>';

      document.getElementById('modalBody').innerHTML = `
        <img class="chart-img" src="charts/${{ticker}}.png" alt="${{ticker}} Chart" />
        <h3 style="margin-bottom:10px;font-size:1rem;">ประวัติวันที่ครบเงื่อนไขเม็ดที่ 4–6 ย้อนหลัง (${{ticker}})</h3>
        <div class="board-table-wrap">
          <table style="min-width:600px;">
            <thead>
              <tr>
                <th>วันที่</th>
                <th>สัญญาณ</th>
                <th>ราคาปิด</th>
                <th>กระดุม</th>
                <th>ไทม์ไลน์ (MACD -> EMA ตัด)</th>
              </tr>
            </thead>
            <tbody>${{signalsHtml}}</tbody>
          </table>
        </div>
      `;
      document.getElementById('stockModal').classList.add('open');
    }}

    function closeModal() {{
      document.getElementById('stockModal').classList.remove('open');
    }}

    renderZones();
  </script>
</body>
</html>
"""
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_html_path
