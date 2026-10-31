# Comprehensive Forensic Technical Audit & Architectural Refactoring Proposal: Bot 3 (US) & Bot 4 (Thai SET) Trend Pullback Scanners

**Document Version**: 1.0.0 (Master Forensic Audit & Production Refactoring Proposal)  
**Author**: Quantitative Trading Engineering Team & Technical Audit Specialist  
**Target Systems**:
- **Bot 3**: US Trend Leader Pullback & R-Multiple Scanner (`bot3_pullback/`)
- **Bot 4**: Thai SET Trend Pullback & R-Multiple Scanner (`bot4_thai_pullback/`)
**Reference Benchmark Systems**:
- **Bot 5**: US Macro Trend Hybrid Scanner (`bot5_us_hybrid/`)
- **Bot 6**: Thai SET Hybrid Trend Scanner (`bot5_thai_hybrid/`)
- **Master Dashboard**: 6-Bot Forward-Test Aggregator (`src/build_master_dashboard.py`)
- **Telegram Webhook**: Google Apps Script Gateway (`gas_webhook/Code.gs`)
**Execution Status**: Non-Invasive Audit Deliverable (Phase M0 Architectural Specification)  
**Date**: October 31, 2026  

---

## Table of Contents
1. [Executive Summary & Audit Context](#1-executive-summary--audit-context)
   - 1.1 Architectural Scope & Operational Mandate
   - 1.2 Core Systemic Design Flaws & Failure Scenarios
   - 1.3 Technical Audit Scorecards across Core Dimensions
   - 1.4 Strategic Upgrade Mandate
2. [Deep Dive Forensic Audit Across the 5 Core Areas](#2-deep-dive-forensic-audit-across-the-5-core-areas)
   - 2.1 Area 1: Strategy & Entry Signals
     - 2.1.1 Macro Regime & Trend Alignment
     - 2.1.2 Support Confluence Zone Modeling
     - 2.1.3 Candlestick Rejection Confirmation & Shooting Star Elimination
     - 2.1.4 False Breakout Handling & Intraday Traps
     - 2.1.5 Institutional Liquidity & Screener Logic Bugs
   - 2.2 Area 2: Risk Management & Position Sizing
     - 2.2.1 1R Risk Budgeting & The Floor Inversion Hazard
     - 2.2.2 20% Max Capital Allocation Cap Enforcement
     - 2.2.3 SET 8-Tier Microstructure & Tick Size Compliance (Bot 4)
     - 2.2.4 Boundary-Crossing Tick Stepping Mechanics (`step_tick_down`)
     - 2.2.5 Profit Target Discrete Tick Snapping (`round_to_set_tick`)
     - 2.2.6 US Fractional Share Position Sizing Architecture (Bot 3)
     - 2.2.7 Stop Loss Volatility Buffer Scaling
   - 2.3 Area 3: Exit Tracker & Position Lifecycle
     - 2.3.1 Multi-Stage Scale-Out Mechanics (TP1 3R, TP2 5R)
     - 2.3.2 The Single-Share / Single Board Lot Zombie Bug
     - 2.3.3 Runner Share Protection & Trailing EMA Exits
     - 2.3.4 Mathematical Proof: Blended R-Multiple vs Unblended Distortion
   - 2.4 Area 4: Telegram Notifier & Performance Reporting
     - 2.4.1 HTML Entity Sanitization & Parser Crash Prevention
     - 2.4.2 Telegram Message Chunking Engine ($\le 4096$ Characters)
     - 2.4.3 Telegram Command Handler Discrepancies & `/stat` Analytics
     - 2.4.4 Master Dashboard Schema Synchronization (`pnl_r`, `pnl_pct`)
   - 2.5 Area 5: State Persistence, CI/CD & Operational Resilience
     - 2.5.1 Atomic State Persistence vs Catastrophic Truncation Hazard
     - 2.5.2 Static Configuration vs Dynamic Runtime State Coupling
     - 2.5.3 Pipeline Fault Isolation & Per-Ticker Exception Handlers
     - 2.5.4 GitHub Actions Cron Scheduling, Concurrency & Push Race Conditions
     - 2.5.5 Silent Failure Hazards & Telegram Failure Notifications
3. [Benchmark Comparison Matrix](#3-benchmark-comparison-matrix)
   - 3.1 Bot 3 (US Pullback) vs Bot 5 (US Macro Trend Hybrid)
   - 3.2 Bot 4 (Thai SET Pullback) vs Bot 6 (Thai SET Hybrid Trend)
   - 3.3 Cross-Market Mechanics Calibration (US Fractional vs Thai Board Lot)
4. [Defect Catalog & Prioritized Improvements](#4-defect-catalog--prioritized-improvements)
   - 4.1 Priority P0: Critical Defects (Math Corruption, Exchange Violations, Data Loss)
   - 4.2 Priority P1: High Defects (Risk Breaches, False Signals, Pipeline Crashes)
   - 4.3 Priority P2: Medium Defects (Interactive Commands, Dynamic Buffers, Workflow Polish)
   - 4.4 Priority P3: Housekeeping & Infrastructure (Import Shims, Test Fixtures)
5. [Implementation & Refactoring Roadmap](#5-implementation--refactoring-roadmap)
   - 5.1 Phased Execution Schedule (Milestones M0 to M4)
   - 5.2 Production-Ready Code Blueprints
     - Blueprint 1: SET 8-Tier Schedule & Boundary Stepping (`bot4/src/indicators.py`)
     - Blueprint 2: SET Risk Manager & Floor Inversion Guard (`bot4/src/risk_manager.py`)
     - Blueprint 3: US Risk Manager & 20% Cap Guard (`bot3/src/risk_manager.py`)
     - Blueprint 4: Zombie-Proof Exit Tracker & Blended R (`both/src/exit_tracker.py`)
     - Blueprint 5: Candlestick Rejection Filter (`both/src/confluence_engine.py`)
     - Blueprint 6: Atomic State Persistence Engine (`both/src/main.py`)
     - Blueprint 7: Telegram HTML Sanitizer & Message Chunker (`both/src/telegram_notifier.py`)
     - Blueprint 8: Interactive `/stat` Performance Handler (`bot3/src/command_handler.py`)
   - 5.3 Verification Methodology & Acceptance Checklist

---

## 1. Executive Summary & Audit Context

### 1.1 Architectural Scope & Operational Mandate
This forensic technical audit provides an authoritative, code-level inspection of **Bot 3** (`bot3_pullback/`, US Trend Leader Pullback Scanner) and **Bot 4** (`bot4_thai_pullback/`, Thai SET Trend Pullback Scanner). Both bots are deployed as fully automated swing-trading engines operating on a 4-stage systematic pipeline:
1. **Momentum & Base Screening**: Scanning equities for Relative Strength, moving average alignment, and Mark Minervini Volatility Contraction Pattern (VCP) consolidation bases (`screener.py`).
2. **Support Confluence & Trigger Evaluation**: Mapping multi-factor confluence support zones (EMA 9, EMA 21, EMA 50, Anchored VWAP, swing breakout pivots, unfilled gaps) and monitoring first-retest breakout triggers (`confluence_engine.py`).
3. **Risk-Budgeted Position Sizing**: Computing fixed 1R risk budgets (0.5% portfolio equity) and enforcing maximum capital exposure caps (20% equity) (`risk_manager.py`).
4. **Asymmetric Exit Tracking**: Managing active positions through multi-stage profit targets (TP1 at 3R, TP2 at 5R), moving stop-losses to Breakeven at TP1, and trailing runner shares along dynamic exponential moving averages (`exit_tracker.py`).

Bot 3 is benchmarked directly against **Bot 5** (`bot5_us_hybrid/`), while Bot 4 is benchmarked against **Bot 6** (`bot5_thai_hybrid/`). Both systems feed active trade logs and forward-test performance into the centralized aggregator `src/build_master_dashboard.py` and communicate alerts via Telegram.

### 1.2 Core Systemic Design Flaws & Failure Scenarios
Forensic inspection of the Bot 3 and Bot 4 codebases revealed **six critical systemic defects** that severely compromise financial safety, breach exchange regulations, invalidate trade analytics, and threaten runtime stability:

```
+========================================================================================================+
|                                    CRITICAL SYSTEMIC AUDIT FINDINGS                                    |
+========================================================================================================+
| 1. MASTER DASHBOARD FIELD MISMATCH & 0.0% REPORTED WIN RATE (P0):                                      |
|    - build_master_dashboard.py aggregates metrics using t.get('pnl_r', 0) and t.get('pnl_pct', 0).     |
|    - Bot 3 and Bot 4 write only 'r_multiple' and 'realized_pnl' in trade_history.                      |
|    - Consequence: All closed trades evaluate to 0.0R; win rate is reported as 0.0% on master dashboard!|
+--------------------------------------------------------------------------------------------------------+
| 2. SET MARKET NON-COMPLIANCE & BOUNDARY CROSSING OFF-TICK DEFECT (BOT 4 - P0):                         |
|    - bot4 indicators.py implements only 7 tiers, omitting Tier 8 (>= 400 THB @ 2.00 THB tick).         |
|    - stop_loss = raw_low - tick naively subtracts tick across tier thresholds, generating illegal SET   |
|      prices (e.g., 5.00 - 0.05 = 4.95 THB, which does not exist on SET order book). Order rejected!    |
+--------------------------------------------------------------------------------------------------------+
| 3. BOARD LOT & SIZING FLOOR INVERSIONS BREACHING RISK BUDGETS (P0):                                    |
|    - Bot 4 forces shares = max(100, board_lot_shares). When budget allows 20 shares, it buys 100,     |
|      multiplying dollar risk by 5x (2.5% equity risk vs 0.5% budget)!                                  |
|    - Bot 3 forces shares = max(1, shares). On high-priced US equities (> $2,000), it breaches 20% cap.|
+--------------------------------------------------------------------------------------------------------+
| 4. PREMATURE TOTAL LIQUIDATION & ZOMBIE TRADE LEAKS (P0):                                              |
|    - In Bot 4, a 1-board-lot (100 share) position at TP1 (3R) sells 100 shares. Status remains 'OPEN'; |
|      it lingers with 0 shares, later logging exit_price = 0.0 THB and exit_reason = 'Stop Loss Hit'!   |
|    - In Bot 3, a 1-share position at TP1 sells 1 share, remaining = 0, lingering until closed as SL.   |
+--------------------------------------------------------------------------------------------------------+
| 5. MATHEMATICAL ERASURE OF REALIZED R-MULTIPLES (P0):                                                  |
|    - Both bots compute curr_r = (curr_close - entry) / risk_per_share.                                 |
|    - When a 50% runner exits at breakeven after banking +3R at TP1, curr_r evaluates to 0.0R!          |
|    - trade_history logs 0.0R instead of the true blended +1.50R, systematically erasing trading edge.  |
+--------------------------------------------------------------------------------------------------------+
| 6. NON-ATOMIC STATE SERIALIZATION HAZARD (P0):                                                         |
|    - Direct json.dump(config, open('config.json', 'w')) truncates file to 0 bytes before writing.       |
|    - Process cancellation or crash mid-write permanently destroys active positions and trade history!  |
+========================================================================================================+
```

### 1.3 Technical Audit Scorecards across Core Dimensions

| Dimension | Bot 3 (US Pullback) | Bot 4 (Thai SET Pullback) | Benchmark Reference (Bot 5 / 6) | Status |
| :--- | :--- | :--- | :--- | :--- |
| **1. Strategy & Entry Signals** | 🔴 **High Risk**: Lacks candle confirmation; buys shooting stars; flawed `and` liquidity filter. | 🔴 **High Risk**: Lacks candle confirmation; buys shooting stars; turnover filter halved to 10M. | Bot 5/6 mandates green/hammer candle confirmation; strictly rejects shooting stars (`upper_wick >= 2.5 * body`). | **Severe Parity Gap** |
| **2. Risk Management & Sizing** | 🔴 **High Risk**: `max(1, shares)` breaches 20% cap; flat $0.02 SL buffer; 25% cap default in config. | 🔴 **Critical Risk**: `max(100, shares)` breaches risk budget up to 5x; unsnapped profit targets. | Bot 5/6 sets `is_valid = False` when budget or cap violated; snaps all targets to discrete ticks. | **Immediate Safety Hazard** |
| **3. Exchange Compliance (SET)** | N/A (US Market) | 🔴 **Critical Risk**: Missing Tier 8 ($\ge 400$ THB); boundary tick subtraction generates illegal off-tick prices. | Bot 6 implements official 8-tier schedule, `step_tick_down()`, and `round_to_set_tick()`. | **Exchange Violation** |
| **4. Exit Tracking & Lifecycle** | 🔴 **Critical Risk**: 1-share TP1 zombie bug; instantaneous 0.0R distortion erases +1.5R gains. | 🔴 **Critical Risk**: 100-share TP1 zombie bug; converts 3R win into Stop Loss failure @ 0.0 THB. | Bot 5/6 executes `CLOSED_TP1` when `shares <= 1` or `shares <= 100`; tracks true blended R-multiples. | **Data Corruption Hazard** |
| **5. Reporting & Dashboard** | 🔴 **Critical Risk**: Missing `pnl_r` and `pnl_pct` causes 0.0% win rate on Master Dashboard; `/stat` missing. | 🔴 **Critical Risk**: Missing `pnl_r` and `pnl_pct` causes 0.0% win rate; no command handler module. | Bot 5/6 writes `pnl_r` and `pnl_pct`; formats Telegram with HTML escaping and complete metric tables. | **Reporting Blindness** |
| **6. State Persistence & Stability**| 🔴 **High Risk**: Non-atomic direct `open("w")`; no exception isolation in loop; cron collision. | 🔴 **High Risk**: Non-atomic direct `open("w")`; no exception isolation in loop; cron collision. | Bot 5/6 utilizes atomic temporary file swapping (`tempfile.mkstemp` + `os.replace`). | **Data Loss Hazard** |

### 1.4 Strategic Upgrade Mandate
The architectural defects in Bot 3 and Bot 4 do not stem from faulty market hypotheses, but from implementation drift, missing exchange guardrails, and schema uncoupling from the centralized dashboard.

The strategic mandate is clear:
1. Preserve the advanced Minervini VCP screening and dynamic Support Confluence Zone modeling unique to Bot 3 and Bot 4.
2. Port the hardened risk guards, discrete tick math, and atomic persistence mechanics from Bot 5 and Bot 6.
3. Eliminate all statistical distortion in exit tracking and dashboard reporting to accurately reflect algorithmic edge.

---

## 2. Deep Dive Forensic Audit Across the 5 Core Areas

### 2.1 Area 1: Strategy & Entry Signals

#### 2.1.1 Macro Regime & Trend Alignment
- **Bot 3 (`screener.py:87-89`)**: Evaluates moving average alignment using loose conditions:
  ```python
  price_above_ema9_21 = curr_close >= ema9 * 0.99 and curr_close >= ema21 * 0.99
  weekly_ok = w_curr >= w_ema10 * 0.97
  ```
  *Defect*: Allows stocks trading up to 1% below daily EMA 9/21 and 3% below weekly EMA 10 to pass. Bot 3 lacks an overarching macro regime filter (e.g. `Close > EMA 50 > EMA 200` Golden Cross or SPY market regime filter). In broad market sell-offs, Bot 3 attempts to catch pullbacks in deep structural downtrends.
- **Bot 4 (`screener.py:61-114`)**: Focuses on Relative Strength percentile and 3M/6M performance ($\ge 15\%$), but omits SET index trend confirmation (`^SET.BK > EMA 50`).
- **Benchmark Reference (Bot 5/6 `strategy_engine.py:67-68`)**: Strictly mandates macro trend alignment:
  ```python
  is_uptrend = (curr_close > e50 > e200) if e200 > 0 else (curr_close > e50)
  macd_bull = m_val > 0
  ```
  Stocks must be confirmed market leaders in institutional accumulation phases.

#### 2.1.2 Support Confluence Zone Modeling
- **Bot 3 & Bot 4 (`confluence_engine.py:28-94`)**: Construct an intelligent, multi-layer Support Confluence Zone by clustering:
  1. Dynamic Exponential Moving Averages (EMA 9, EMA 21, EMA 50)
  2. Anchored VWAP (AVWAP anchored from the 60-day swing low)
  3. Structural Breakout Swing High Pivots (former resistance turned support)
  4. Unfilled Gap-Up Support Edges
- *Auditor Assessment*: This confluence model is mathematically superior to Bot 5/6's fixed percentage envelope around EMA 20/50. However, its effectiveness is crippled by flawed trigger conditions.

#### 2.1.3 Candlestick Rejection Confirmation & Shooting Star Elimination
- **Bot 3 & Bot 4 Defect (`confluence_engine.py:155-156` / `107-112`)**:
  ```python
  # Current trigger logic:
  trigger_fired = (curr_high > prior_high) or (curr_close > prior_high)
  ```
  Neither bot analyzes candlestick anatomy (open, close, high, low, body, upper wick, lower wick).
- **Failure Scenario (The Bull Trap / Shooting Star)**:
  Consider a stock with `prior_high = $100.00`. During regular trading hours, price spikes intraday to `$101.50`, then encounters aggressive institutional distribution and collapses to close at `$95.00` (Open `$99.00`, Low `$94.80`).
  - `curr_high > prior_high` evaluates to `True` ($101.50 > 100.00).
  - Both Bot 3 and Bot 4 fire a `BUY_TRIGGERED` alert!
  - `main.py` enters a paper trade at `curr_close` ($95.00).
  - The bot buys at the dead low of a catastrophic distribution candle with a massive upper shadow (bearish shooting star).
- **Remediation Specification (Bot 5/6 Parity)**:
  Implement strict candlestick anatomy filters:
  ```python
  curr_open = float(df["Open"].iloc[-1]) if "Open" in df.columns else curr_close
  body = abs(curr_close - curr_open)
  upper_wick = curr_high - max(curr_close, curr_open)
  lower_wick = min(curr_close, curr_open) - curr_low

  is_green = curr_close > curr_open
  hammer = (lower_wick >= 1.5 * max(body, 0.05)) and (upper_wick <= 1.0 * max(body, 0.05))
  is_shooting_star = (upper_wick >= 2.5 * max(body, 0.05)) and (lower_wick <= 0.5 * upper_wick)
  bounce_e9 = curr_close > support_info["ema9"] and curr_close > prior_high * 0.995

  has_candle_confirmation = (is_green or hammer or bounce_e9) and not is_shooting_star
  trigger_fired = (curr_high > prior_high or curr_close > prior_high) and has_candle_confirmation
  ```

#### 2.1.4 False Breakout Handling & Falling Knives
- In `confluence_engine.py:145-149`, the check `abs(curr_close - zone_top) / zone_top <= 0.02` permits trades when price is breaking down through the support zone.
- *Remediation*: Mandate that `curr_close >= zone_bottom * 0.995`, ensuring price is actively holding or rebounding from support, not slicing through it.

#### 2.1.5 Institutional Liquidity & Screener Logic Bugs
1. **Bot 3 Boolean Logic Defect (`screener.py:69-70`)**:
   ```python
   # Current code:
   if vol_20 < self.min_vol and dollar_vol_20 < self.min_dollar_vol:
       return None
   ```
   *Diagnosis*: Uses `and` instead of `or`. A micro-cap stock with 15,000 shares volume at $400 ($6,000,000 dollar volume) passes despite illiquid spreads. A penny stock trading 600,000 shares at $0.20 ($120,000 dollar volume) also passes!
   *Fix*: `if vol_20 < self.min_vol or dollar_vol_20 < self.min_dollar_vol: return None`.
2. **Bot 4 Turnover Halving Defect (`screener.py:70`)**:
   ```python
   # Current code:
   if turnover_20 < self.min_turnover and turnover_20 < 10000000:
       return None
   ```
   *Diagnosis*: Even if `self.min_turnover` is configured to 20,000,000 THB, the condition `and turnover_20 < 10000000` allows stocks with 12,000,000 THB turnover to pass, silently halving institutional liquidity standards.
   *Fix*: `if turnover_20 < self.min_turnover: return None`.

---

### 2.2 Area 2: Risk Management & Position Sizing

#### 2.2.1 1R Risk Budgeting & The Floor Inversion Hazard
- **Mandate**: 1R risk budget is fixed at 0.5% of total portfolio equity ($50 on $10,000 for Bot 3; 5,000 THB on 1,000,000 THB for Bot 4).
- **Bot 4 Floor Inversion Defect (`risk_manager.py:76`)**:
  ```python
  board_lot_shares = (raw_shares // self.board_lot) * self.board_lot
  shares = max(self.board_lot, board_lot_shares) if entry_price * self.board_lot <= port_equity else 0
  ```
  - Scenario: Ticker DELTA trades at 850 THB, SL at 800 THB. Risk per share = 50 THB.
  - Risk budget = 5,000 THB. `raw_shares = 5000 / 50 = 100 shares`.
  - But suppose Entry = 320 THB, SL = 258 THB. Risk per share = 62 THB.
  - `raw_shares = int(5000 / 62) = 80 shares`.
  - `board_lot_shares = (80 // 100) * 100 = 0 shares`.
  - Line 76 computes: `shares = max(100, 0) = 100 shares`!
  - **Capital & Risk Blowout**: The bot allocates 100 shares $\times$ 62 THB = **6,200 THB actual risk** (+24% breach). If risk per share is 250 THB, it forces 100 shares, risking 25,000 THB (**500% of risk budget**)!
- **Bot 3 Floor Inversion Defect (`risk_manager.py:76`)**:
  ```python
  raw_shares = int(dollar_risk_budget / risk_per_share) if risk_per_share > 0 else 0
  shares = max(1, raw_shares) if entry_price <= port_equity else 0
  ```
  When risk per share exceeds the $50 budget, `shares = max(1, 0) = 1`, risking up to $150-$300 (3x-6x budget breach).
- **Remediation Specification**:
  If affordable shares fall below the required lot size (1 share for US, 100 shares for Thai SET), the trade MUST be rejected:
  ```python
  if board_lot_shares < self.board_lot:
      return ThaiTradePlan(is_valid=False, shares=0, warning_note=f"Risk budget {dollar_risk_budget:,.0f} THB insufficient for 1 Board Lot")
  ```

#### 2.2.2 20% Max Capital Allocation Cap Enforcement
- **Mandate**: No single position may consume more than 20.0% of portfolio equity ($2,000 for Bot 3; 200,000 THB for Bot 4).
- **Bot 3 Discrepancy**: `config.json` configures `"max_allocation_per_trade_pct": 25.0`, violating the 20% institutional requirement.
- **Capital Cap Inversion Bug (Both Bots)**:
  - Bot 3 (`risk_manager.py:90`): `if capped_shares < shares: shares = max(1, capped_shares)`.
    If stock price = $2,500 and max capital = $2,000, `capped_shares = 0`. The code forces `shares = 1`, allocating $2,500 (25% equity).
  - Bot 4 (`risk_manager.py:91`): `if capped_shares < shares: shares = max(self.board_lot, capped_shares)`.
    For any stock $>2,000$ THB, 100 shares costs $>200,000$ THB. `capped_shares = 0`. The code forces `shares = 100`, breaching the cap.
- **Remediation**:
  If `capped_shares < 1` (Bot 3) or `capped_shares < self.board_lot` (Bot 4), mark `is_valid = False`, `shares = 0`, and reject trade.

#### 2.2.3 SET 8-Tier Microstructure & Tick Size Compliance (Bot 4)
Under Stock Exchange of Thailand (SET) rules, order prices must conform to the official 8-tier discrete tick schedule:

| Tier | Market Price Range (THB) | Official SET Tick Size | Bot 4 (`indicators.py`) | Bot 6 Benchmark | Compliance Verdict |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | $< 2.00$ | 0.01 ฿ | 0.01 ฿ | 0.01 ฿ | ✅ Compliant |
| 2 | $2.00 - 4.98$ | 0.02 ฿ | 0.02 ฿ | 0.02 ฿ | ✅ Compliant |
| 3 | $5.00 - 9.95$ | 0.05 ฿ | 0.05 ฿ | 0.05 ฿ | ✅ Compliant |
| 4 | $10.00 - 24.90$ | 0.10 ฿ | 0.10 ฿ | 0.10 ฿ | ✅ Compliant |
| 5 | $25.00 - 99.75$ | 0.25 ฿ | 0.25 ฿ | 0.25 ฿ | ✅ Compliant |
| 6 | $100.00 - 199.50$ | 0.50 ฿ | 0.50 ฿ | 0.50 ฿ | ✅ Compliant |
| 7 | $200.00 - 398.00$ | 1.00 ฿ | 1.00 ฿ | 1.00 ฿ | ✅ Compliant |
| **8** | $\ge 400.00$ | **2.00 ฿** | **1.00 ฿ (MISSING)** | **2.00 ฿** | ❌ **NON-COMPLIANT** |

*Forensic Finding*: Bot 4 stops at Tier 7. Any stock $\ge 400.00$ THB is assigned a 1.00 THB tick instead of 2.00 THB, generating invalid order prices.

#### 2.2.4 Boundary-Crossing Tick Stepping Mechanics (`step_tick_down`)
- **Bot 4 Defect (`risk_manager.py:59`)**:
  ```python
  raw_low = min(curr_low, prior_low)
  tick = get_thai_tick_size(raw_low)
  stop_loss = round(max(0.01, raw_low - tick), 2)
  ```
- **The Boundary Disaster**:
  - Case 1: `raw_low = 5.00 THB`. `get_thai_tick_size(5.00) = 0.05 THB`.
    Stop loss $= 5.00 - 0.05 = \mathbf{4.95\text{ THB}}$.
    *Exchange Reality*: Under SET rules, prices $<5.00$ THB trade in 0.02 THB ticks. Legal prices are 4.98, 4.96, 4.94 THB. **4.95 THB does not exist on the SET order book**. Broker gateways immediately reject the order!
  - Case 2: `raw_low = 25.00 THB`. `get_thai_tick_size(25.00) = 0.25 THB`.
    Stop loss $= 25.00 - 0.25 = \mathbf{24.75\text{ THB}}$.
    *Exchange Reality*: Below 25.00 THB, tick size is 0.10 THB. The legal tick directly below 25.00 THB is **24.90 THB**. Bot 4 stepped down 2.5 ticks instead of 1 tick, unnecessarily widening risk.
- **Remediation Specification**:
  Implement `step_tick_down(price)` with exact boundary mapping:
  $$5.00 \to 4.98, \quad 25.00 \to 24.90, \quad 100.00 \to 99.75, \quad 200.00 \to 199.50, \quad 400.00 \to 399.00$$

#### 2.2.5 Profit Target Discrete Tick Snapping (`round_to_set_tick`)
- **Bot 4 Defect (`risk_manager.py:101-104`)**:
  Computes targets via raw floating-point math: `target_1r = round(entry_price + 1.0 * risk_per_share, 2)`.
  If Entry = 28.50 THB and Risk = 1.45 THB, Target 1R = 29.95 THB. In Tier 5 (25-100 THB), tick size is 0.25 THB. Valid ticks are 29.75 and 30.00 THB. 29.95 THB is an illegal price.
- **Remediation**:
  Snap all target prices using `round_to_set_tick(target, mode="nearest")`.

#### 2.2.6 US Fractional Share Position Sizing Architecture (Bot 3)
- In US equities, retail brokerages (Interactive Brokers, Charles Schwab, Alpaca) allow fractional share trading down to 4 decimal places.
- On a $10,000 account with $50 risk budget, high-priced equities ($300-$1,000) frequently truncate integer shares to 0.
- *Architecture*: Support fractional shares (`round(shares, 4)`) when `allow_fractional: true` is enabled in configuration, while defaulting to integer shares for conservative cash accounts.

#### 2.2.7 Stop Loss Volatility Buffer Scaling
- **Bot 3 Defect (`risk_manager.py:59`)**:
  ```python
  stop_loss = round(max(0.01, raw_sl - 0.02), 2)
  ```
  A flat $0.02 buffer represents a microscopic 0.004% on a $500 stock. Normal bid-ask bounce stops the trader out prematurely.
- **Remediation**:
  Adopt Bot 5's dynamic buffer: `buffer = max(0.15, round(raw_sl * 0.015, 2))`.

---

### 2.3 Area 3: Exit Tracker & Position Lifecycle

#### 2.3.1 Multi-Stage Scale-Out Mechanics (TP1 3R, TP2 5R)
The intended lifecycle of a profitable pullback trade is:
1. **Entry**: Enter full position with initial Stop Loss below confluence support.
2. **TP1 (Target 3R)**: Sell 50% of position; ratchet Stop Loss to Breakeven (`entry_price`).
3. **TP2 (Target 5R)**: Sell 50% of remaining position (25% of initial position).
4. **Runner**: Trail remainder along Daily EMA 9 until price closes below EMA 9.

#### 2.3.2 The Single-Share / Single Board Lot Zombie Bug
This is one of the most critical bugs uncovered during the audit:
- **In Bot 4 (`exit_tracker.py:80-93`)**:
  ```python
  # When position has 100 shares and hits 3R:
  raw_sell = int(curr_shares * self.tp1_ratio)  # 100 * 0.5 = 50
  sell_qty = max(self.board_lot, (raw_sell // self.board_lot) * self.board_lot)  # max(100, 0) = 100
  if sell_qty > curr_shares: sell_qty = curr_shares  # 100
  pnl = round((target_3r - entry) * sell_qty, 2)
  pos["current_shares"] = curr_shares - sell_qty  # 0 shares!
  ```
  *The Fatal Flaw*: `pos["status"]` is **NEVER** set to `"CLOSED_TP1"`!
  The position remains `"OPEN"` with `current_shares = 0`.
  On subsequent daily scans, the position is still in `active_positions`. When `curr_low <= stop_loss` or on trailing checks, `main.py` logs:
  `exit_price: 0.0 THB`, `exit_reason: "Stop Loss Hit"`.
  **A trade that hit +3.0R profit is recorded in history as a Stop Loss catastrophe with $0.00 exit price!**
- **In Bot 3 (`exit_tracker.py:84-110`)**:
  Identical flaw for 1-share positions: `sell_qty = max(1, int(1 * 0.5)) = 1`. `current_shares` drops to 0, status remains `"OPEN"`, and it logs `exit_price: $0.00`.
- **Remediation Specification**:
  ```python
  if curr_shares <= self.board_lot:  # or <= 1 for Bot 3
      sell_qty = curr_shares
      pnl = round((target_3r - entry) * sell_qty, 2)
      pos["status"] = "CLOSED_TP1"
      pos["exit_price"] = target_3r
      pos["exit_date"] = date_str
      pos["exit_reason"] = "Target 3R Hit (100% Exit for 1 Lot)"
      pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
      pos["current_shares"] = 0
      self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
      return pos, actions
  ```

#### 2.3.3 Runner Share Protection & Trailing EMA Exits
For positions with multiple lots/shares:
- If `sell_qty >= curr_shares`, clamp `sell_qty = curr_shares - 1` (or `curr_shares - self.board_lot`) to guarantee at least one runner unit survives to ride the trend.
- Trailing Stop: Trailing EMA 9 exit should only evaluate runner shares AFTER TP1 has been secured (`tp1_hit == True`).

#### 2.3.4 Mathematical Proof: Blended R-Multiple vs Unblended Distortion
- **The Defect in Bot 3 (`exit_tracker.py:57`) and Bot 4 (`exit_tracker.py:53`)**:
  ```python
  curr_r = round((curr_close - entry) / risk_per_share, 2)
  pos["current_r"] = curr_r
  ```
- **Mathematical Failure Proof**:
  - Initial parameters: Entry = $100.00, SL = $90.00. Risk per share = $10.00.
  - Position size = 10 shares. Total dollar risk budget = $100.00.
  - Target 3R = $130.00. Price hits $130.00:
    * 5 shares sold at $130.00 $\to$ Realized gain = $5 \times \$30 = +\$150.00$ ($+1.50R$).
    * Stop Loss on remaining 5 shares is moved to Breakeven ($100.00).
  - Later, price pulls back and hits Breakeven SL at $100.00:
    * Remaining 5 shares exit at $100.00 $\to$ Realized gain = $5 \times \$0 = \$0.00$.
    * Total cash realized = $+\$150.00$.
    * True financial R-multiple $= \frac{+\$150.00}{\$100.00\text{ (initial risk)}} = \mathbf{+1.50R}$.
  - **What Bot 3 & Bot 4 Calculate**:
    $$\text{curr\_r} = \frac{100.00 - 100.00}{10.00} = \mathbf{0.00R}$$
    `main.py` records `r_multiple = 0.00` in `trade_history`!
    **A +1.50R winning trade is mathematically erased and logged as a 0.00R scratch trade!**
- **The Correct Blended R Formula**:
  $$\text{Blended PnL} = \text{Total Realized PnL} + (\text{Current Close} - \text{Entry}) \times \text{Current Shares}$$
  $$\text{Blended R} = \frac{\text{Blended PnL}}{\text{Initial Shares} \times \text{Risk Per Share}}$$

---

### 2.4 Area 4: Telegram Notifier & Performance Reporting

#### 2.4.1 HTML Entity Sanitization & Parser Crash Prevention
- Both Bot 3 and Bot 4 format Telegram messages with `parse_mode: "HTML"`.
- Neither bot sanitizes dynamic strings (stock tickers, trade plan warning notes, company names).
- If a warning note contains `<` or `>` or `&` (e.g. `Price < EMA 50` or `Risk & Cap`), Telegram's API rejects the request with:
  `HTTP 400 Bad Request: Can't parse entities: character '<' is not escaped`.
  The message is dropped silently.
- *Remediation*: Wrap all dynamic user-facing text in `html.escape()`.

#### 2.4.2 Telegram Message Chunking Engine ($\le 4096$ Characters)
- Telegram hard-caps message payloads at 4,096 characters.
- When market breadth triggers 10+ signals or when active portfolio tables expand, alerts exceed 4,096 characters and fail with HTTP 400 `MESSAGE_TOO_LONG`.
- *Remediation*: Implement a line-aware message chunking generator that partitions payloads at newline boundaries under 4,000 characters and dispatches them sequentially.

#### 2.4.3 Telegram Command Handler Discrepancies & `/stat` Analytics
- In `bot3_pullback/src/command_handler.py:184-216`, the help menu advertises:
  `• /stat - ดูผลตอบแทนและสถิติ Win Rate`
  `• /buy TICKER SHARES PRICE - บันทึกเข้าพอร์ตแบบแมนนวล`
  `• /sell TICKER PRICE - บันทึกปิดทำกำไร/ขายหุ้น`
- *Defect*: None of these commands exist in the message router! User requests for `/stat` are silently ignored.
- *Defect in Bot 4*: Bot 4 completely lacks a `command_handler.py` module.
- *Remediation*: Implement `/stat` calculating: Total Trades, Active Holdings, Win Rate %, Total Realized R, Win/Loss Count, Average Win R, Average Loss R, and Total Realized PnL ($ / THB).

#### 2.4.4 Master Dashboard Schema Synchronization (`pnl_r`, `pnl_pct`)
- In `src/build_master_dashboard.py:126-129`, the aggregator calculates bot statistics:
  ```python
  wins = [t for t in trades if t.get("pnl_r", 0) > 0 or t.get("pnl_pct", 0) > 0]
  total_r = sum(t.get("pnl_r", 0.0) for t in trades)
  ```
- **The Catastrophic Mismatch**:
  Both Bot 3 (`main.py:116-125`) and Bot 4 (`main.py:102-111`) save closed trades as:
  `{"ticker": ticker, ..., "r_multiple": updated_pos.get("current_r", 0.0), "realized_pnl": ...}`
  They omit `pnl_r` and `pnl_pct`!
- **Consequence**: `t.get("pnl_r", 0)` evaluates to `0` for EVERY Bot 3 and Bot 4 trade.
  On the Master Dashboard:
  - Bot 3 displays: **Win Rate: 0.0% | Total R: +0.00R**
  - Bot 4 displays: **Win Rate: 0.0% | Total R: +0.00R**
- *Remediation*: Update `trade_history.append(...)` in both bots to include `pnl_r`, `pnl_pct`, `shares`, `realized_pnl`, and `r_multiple`.

---

### 2.5 Area 5: State Persistence, CI/CD & Operational Resilience

#### 2.5.1 Atomic State Persistence vs Catastrophic Truncation Hazard
- In `bot3_pullback/src/main.py:76-79` and `bot4_thai_pullback/src/main.py:46-48`:
  ```python
  def save_config(config: Dict):
      with open(CONFIG_PATH, "w", encoding="utf-8") as f:
          json.dump(config, f, indent=2, ensure_ascii=False)
  ```
- Opening a file in `"w"` mode immediately truncates it to 0 bytes.
- If GitHub Actions cancels the workflow runner, times out, or encounters a SIGTERM / OOM kill before `json.dump()` completes, `config.json` is left as an empty 0-byte file.
- On the next scan run, `json.load()` crashes with `json.decoder.JSONDecodeError`, permanently corrupting the bot.
- *Remediation Specification*:
  ```python
  def save_config(cfg: Dict):
      dir_name = os.path.dirname(os.path.abspath(CONFIG_PATH))
      os.makedirs(dir_name, exist_ok=True)
      temp_fd, temp_path = tempfile.mkstemp(dir=dir_name, text=True)
      with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
          json.dump(cfg, f, indent=2, ensure_ascii=False)
          f.flush()
          os.fsync(f.fileno())
      os.replace(temp_path, CONFIG_PATH)
  ```

#### 2.5.2 Static Configuration vs Dynamic Runtime State Coupling
- `config/config.json` currently houses both immutable system parameters (`portfolio_equity`, `universe`, `risk_per_trade_pct`) and mutable runtime state (`active_positions`, `trade_history`, `last_scan_date`).
- Editing parameters manually risks corrupting live positions. While architectural segregation into `config.json` and `state.json` is planned for long-term housekeeping, atomic persistence is mandatory immediately.

#### 2.5.3 Pipeline Fault Isolation & Per-Ticker Exception Handlers
- In `main.py` Phase 1 (active position evaluation), neither bot wraps individual ticker processing in `try...except`.
- If Yahoo Finance returns malformed data or 429 rate limit errors for a single ticker, the entire pipeline crashes before updating other positions or saving state.
- *Remediation*: Wrap each ticker download and evaluation in a dedicated `try...except` block, logging errors without interrupting portfolio-wide processing.

#### 2.5.4 GitHub Actions Cron Scheduling, Concurrency & Push Race Conditions
- **Morning Collision (01:45 UTC / 08:45 BKK)**: Bot 3 and Bot 5 run concurrently.
- **Evening Collision (10:30 UTC / 17:30 BKK)**: Bot 4 and Bot 6 run concurrently.
- Both workflows execute git pull --rebase and git push to `main`. Concurrent pushes cause Git index locks and non-fast-forward push failures.
- *Remediation*: Stagger schedules:
  - US Post-Market: Bot 3 at 01:45 UTC, Bot 5 at 01:50 UTC, Master Dashboard at 02:00 UTC.
  - Thai Post-Market: Bot 4 at 10:25 UTC, Bot 6 at 10:35 UTC, Master Dashboard at 10:45 UTC.

#### 2.5.5 Silent Failure Hazards & Telegram Failure Notifications
- If an unhandled runtime error occurs in `main.py`, the GitHub Actions workflow fails silently. Users receive zero alerts.
- *Remediation*: Add an `if: failure()` step in workflows that posts an immediate emergency alert to the designated Telegram chat.

---

## 3. Benchmark Comparison Matrix

### 3.1 Bot 3 (US Pullback) vs Bot 5 (US Macro Trend Hybrid)

| Parameter / Dimension | Bot 3 Implementation (`bot3_pullback/`) | Bot 5 Benchmark (`bot5_us_hybrid/`) | Architectural Gap & Remediation |
| :--- | :--- | :--- | :--- |
| **Strategy & Trend Filter** | Loose MA alignment (`Close >= EMA * 0.99`); no macro trend confirmation. | Strict `Close > EMA 50 > EMA 200` Golden Cross + `MACD > 0`. | Bot 3 requires trend confirmation to avoid buying deep bear market pullbacks. |
| **Candlestick Rejection** | None. Fires on raw `High > Prior High`. | Rejects shooting stars (`upper_wick >= 2.5 * body`); requires hammer/green. | **Critical Flaw in Bot 3**: Buys intraday false breakout bull traps. Port Bot 5 logic. |
| **Liquidity Screening** | Flawed `and` logic allows penny/illiquid stocks; $5M dollar volume. | Strict `and` logic requiring Volume $\ge 500k$ and Dollar Vol $\ge \$20M$. | Fix boolean logic to `or` clause and align threshold to $20M. |
| **1R Risk Budgeting** | Forces `shares = max(1, raw_shares)`. Over-allocates risk by 200-500%. | Sets `is_valid = False`, `shares = 0` if budget < 1 share. | **Critical Flaw in Bot 3**: Port Bot 5 sizing validity guard. |
| **Max Capital Cap** | Default cap 25.0%; forces `shares = max(1, capped)` on high-priced stocks. | Default cap 20.0%; sets `is_valid = False`, `shares = 0` if cap breached. | Update config to 20.0%; invalidate trade if stock price > max capital. |
| **Stop Loss Buffer** | Flat $0.02 buffer (inadequate for $100-$500 equities). | Dynamic buffer: `max(0.15, round(raw_sl * 0.015, 2))`. | Port dynamic price-scaled buffer to Bot 3. |
| **Fractional Shares** | Integer truncation only (`int(...)`). | Integer shares (`board_lot_size: 1`). | Add fractional share sizing support for US equities. |
| **Single-Share Exit (TP1)** | Sells 1 share, leaves 0 shares, status remains "OPEN", logs exit_price $0.00. | Sets `status = "CLOSED_TP1"`, logs exit_price = target_3r, returns clean action. | **Critical Bug in Bot 3**: Port Bot 5 single-share full exit handling. |
| **Runner Preservation** | Sells all shares if `curr_shares <= 2` due to rounding. | Clamps `sell_qty = curr_shares - 1` to guarantee at least 1 runner share. | Guarantee at least 1 runner share when position size > 1. |
| **Blended R-Multiple** | Instantaneous: `(close - entry) / risk`. Erases +1.5R at Breakeven SL exit. | Blended: `(realized + unrealized) / initial_risk`. Accurately logs +1.50R. | **Critical Flaw in Bot 3**: Implement `_update_metrics` in ExitTracker. |
| **Telegram HTML Escaping** | None. Unescaped `<, >, &` crash Telegram parser with HTTP 400. | Escapes dynamic parameters via `html.escape()`. | Implement `html.escape()` across all Telegram alert builders. |
| **Message Chunking** | None. Single payload dropped if >4096 characters. | None. Shared vulnerability. | Implement newline-aware chunking engine ($\le 4000$ chars). |
| **Telegram Commands** | Advertises `/stat`, `/buy`, `/sell` in help; missing in router. | CLI batch execution; no interactive daemon. | Implement `/stat` handler computing portfolio performance metrics. |
| **Master Dashboard Parity** | Writes `r_multiple` and `realized_pnl`; omits `pnl_r`, `pnl_pct`. | Writes `pnl_r`, `pnl_pct`, `shares`, `realized_pnl`, `r_multiple`. | **Critical Flaw in Bot 3**: Master Dashboard reports 0.0% win rate. Align schema. |
| **State Persistence** | Direct non-atomic `open("w")`. Risks 0-byte file corruption. | Atomic persistence via `tempfile.mkstemp` and `os.replace`. | Port Bot 5 atomic persistence pattern to Bot 3 `main.py`. |
| **Exception Isolation** | Phase 1 active position loop lacks `try...except`. Single failure crashes bot. | Download and evaluation wrapped in `try...except` per ticker. | Port per-ticker error isolation to Bot 3. |

---

### 3.2 Bot 4 (Thai SET Pullback) vs Bot 6 (Thai SET Hybrid Trend)

| Parameter / Dimension | Bot 4 Implementation (`bot4_thai_pullback/`) | Bot 6 Benchmark (`bot5_thai_hybrid/`) | Architectural Gap & Remediation |
| :--- | :--- | :--- | :--- |
| **SET Tick Schedule** | 7 tiers only. Omits Tier 8 ($\ge 400$ THB @ 2.00 THB tick). | Full official 8-tier SET schedule including Tier 8. | **Exchange Rule Violation**: Port official 8-tier schedule. |
| **Boundary Tick Stepping** | Naive `raw_low - tick`. Generates illegal off-tick prices (e.g. 4.95, 24.75 THB). | Implements `step_tick_down(price)` with exact boundary mappings. | **Critical Flaw in Bot 4**: Broker rejects off-tick orders. Port `step_tick_down`. |
| **Profit Target Snapping** | Raw float math: `round(entry + k * risk, 2)`. Generates illegal prices. | Snaps all targets to discrete ticks via `round_to_set_tick(target)`. | Port `round_to_set_tick` to snap 1R, 2R, 3R, 5R targets. |
| **Board Lot Floor Inversion**| Forces `shares = max(100, board_lot_shares)`. Multiplies risk up to 5x. | If `board_lot_shares < 100`, sets `is_valid = False`, `shares = 0`. | **Critical Flaw in Bot 4**: Breaches 5,000 THB risk budget. Port valid flag. |
| **20% Capital Cap** | Forces `shares = max(100, capped_shares)` on stocks $>2,000$ THB. | If `capped_shares < 100`, sets `is_valid = False`, `shares = 0`. | Invalidate trade when 1 board lot exceeds 200,000 THB cap. |
| **Trade Plan Valid Flag** | `ThaiTradePlan` has no `is_valid` flag. Pipeline cannot reject trades. | `ThaiTradePlan` includes `is_valid: bool = True`. | Add `is_valid` flag to `ThaiTradePlan` dataclass. |
| **Candlestick Rejection** | None. Fires on raw `High > Prior High` wick. | Rejects shooting stars (`upper_wick >= 2.5 * body`); requires green/hammer. | Port candlestick rejection logic from Bot 6. |
| **Turnover Filter** | Conflicting `and turnover_20 < 10000000` halves threshold to 10M THB. | Enforces strict 20M THB turnover threshold. | Fix boolean clause to enforce full 20M THB turnover. |
| **Screening Fallback** | Fallback `all_screened[:15]` degrades screening standards. | Evaluates only qualified base candidates. | Remove degraded screening fallback. |
| **100-Share TP1 Exit** | Sells 100 shares, leaves 0 shares, status remains "OPEN", logs 0.0 THB SL. | Sets `status = "CLOSED_TP1"`, logs exit_price = target_3r, returns clean action. | **Critical Bug in Bot 4**: Port Bot 6 single-lot full exit handling. |
| **Blended R-Multiple** | Instantaneous: `(close - entry) / risk`. Erases +1.5R at Breakeven SL exit. | Blended: `(realized + unrealized) / initial_risk`. Accurately logs +1.50R. | **Critical Flaw in Bot 4**: Implement `_update_metrics` in ExitTracker. |
| **Master Dashboard Parity** | Writes `r_multiple` and `realized_pnl`; omits `pnl_r`, `pnl_pct`. | Writes `pnl_r`, `pnl_pct`, `shares`, `realized_pnl`, `r_multiple`. | **Critical Flaw in Bot 4**: Master Dashboard reports 0.0% win rate. Align schema. |
| **State Persistence** | Direct non-atomic `open("w")`. Risks 0-byte file corruption. | Atomic persistence via `tempfile.mkstemp` and `os.replace`. | Port atomic persistence pattern to Bot 4 `main.py`. |
| **Exception Isolation** | Phase 1 active position loop lacks `try...except`. | Download and evaluation wrapped in `try...except` per ticker. | Port per-ticker error isolation to Bot 4. |
| **Signal Viability Guard** | Appends triggers and enters paper trades without checking validity. | Strictly gates entry on `if plan.is_valid and plan.shares > 0:`. | Gate all signal execution and paper trades on plan validity. |

---

### 3.3 Cross-Market Mechanics Calibration (US Fractional vs Thai Board Lot)

| Dimension | US Market Mechanics (Bot 3 / Bot 5) | Thai SET Market Mechanics (Bot 4 / Bot 6) |
| :--- | :--- | :--- |
| **Currency & Base Equity** | USD ($10,000 Portfolio Equity) | THB (1,000,000 THB Portfolio Equity) |
| **1R Dollar Risk Budget** | $50.00 (0.5% equity) | 5,000 THB (0.5% equity) |
| **Max Capital Allocation Cap**| $2,000.00 (20.0% equity) | 200,000 THB (20.0% equity) |
| **Lot Size Constraints** | 1 share (or fractional 0.01 - 0.0001 share) | Strict Board Lot of 100 shares (odd-lots trade on separate board) |
| **Price Tick Discretization**| Decimal pricing ($0.01 tick; sub-penny < $1.00) | Strict 8-tier discrete schedule (0.01, 0.02, 0.05, 0.10, 0.25, 0.50, 1.00, 2.00 ฿) |
| **Stop Loss Buffer** | Price-scaled dynamic buffer $\ge 1.5\%$ (`max(0.15, raw * 0.015)`) | Exactly 1 legal SET tick below swing low (`step_tick_down(raw_low)`) |
| **Trading Hours (UTC / BKK)**| Regular: 14:30 - 21:00 UTC (21:30 - 04:00 BKK) | Morning: 03:00 - 05:30 UTC / Afternoon: 07:30 - 09:30 UTC |
| **Daily Workflow Run Time** | 01:45 UTC (08:45 BKK) - Morning Post-Close | 10:25 UTC (17:25 BKK) - Evening Post-Close |

---

## 4. Defect Catalog & Prioritized Improvements

### 4.1 Priority P0: Critical Defects (Math Corruption, Exchange Violations, Data Loss)

#### [P0-1] Non-Atomic State Persistence Leading to 0-Byte State File Corruption
- **Affected Files**: `bot3_pullback/src/main.py:76-79`, `bot3_pullback/src/command_handler.py:219-220`, `bot4_thai_pullback/src/main.py:46-48`
- **Observed Code**:
  ```python
  def save_config(config: Dict):
      with open(CONFIG_PATH, "w", encoding="utf-8") as f:
          json.dump(config, f, indent=2, ensure_ascii=False)
  ```
- **Failure Scenario**: Direct `open(..., "w")` truncates `config.json` to 0 bytes immediately. If the GitHub Actions runner times out, cancels, or crashes mid-write, `config.json` is left as an empty file. All subsequent runs crash with `JSONDecodeError`, permanently wiping active positions and history.
- **Remediation**: Deploy `tempfile.mkstemp` + `os.replace` atomic swapping in both bots.

#### [P0-2] Master Dashboard Schema Desynchronization (0.0% Win Rate & 0.0R)
- **Affected Files**: `bot3_pullback/src/main.py:116-125`, `bot4_thai_pullback/src/main.py:102-111`
- **Observed Code**:
  ```python
  trade_history.append({
      "ticker": ticker,
      "entry_date": updated_pos.get("entry_date", "-"),
      "exit_date": updated_pos.get("exit_date", today_str),
      "entry_price": updated_pos.get("entry_price", 0.0),
      "exit_price": updated_pos.get("exit_price", 0.0),
      "exit_reason": updated_pos.get("exit_reason", "-"),
      "realized_pnl": updated_pos.get("total_realized_pnl", 0.0),
      "r_multiple": updated_pos.get("current_r", 0.0),
  })
  ```
- **Failure Scenario**: `src/build_master_dashboard.py` specifically evaluates `t.get("pnl_r", 0) > 0` and `t.get("pnl_pct", 0) > 0`. Because `pnl_r` and `pnl_pct` are missing, all closed trades evaluate to 0.0R, displaying a false 0.0% win rate on the dashboard.
- **Remediation**: Populate `pnl_r`, `pnl_pct`, `shares`, `realized_pnl`, and `r_multiple` in `trade_history`.

#### [P0-3] Zombie 0-Share Position Leak & Premature Liquidation Bug
- **Affected Files**: `bot3_pullback/src/exit_tracker.py:84-110`, `bot4_thai_pullback/src/exit_tracker.py:80-93`
- **Failure Scenario**: When an active position has 1 share (Bot 3) or 100 shares (Bot 4) and hits Target 3R (TP1), `sell_qty` sells 100% of holdings, setting `current_shares = 0`. However, the status is NOT set to `CLOSED_TP1` and exit price is not recorded. The position lingers as a zombie record, eventually logging `exit_price: 0.0` and `exit_reason: "Stop Loss Hit"`.
- **Remediation**: Explicitly check `if curr_shares <= 1` (Bot 3) or `if curr_shares <= self.board_lot` (Bot 4): set `pos["status"] = "CLOSED_TP1"`, `pos["exit_price"] = target_3r`, log clean TP1 100% exit, update metrics, and return immediately.

#### [P0-4] Mathematical Distortion of Realized R-Multiple on Scale-Out Exits
- **Affected Files**: `bot3_pullback/src/exit_tracker.py:57-61`, `bot4_thai_pullback/src/exit_tracker.py:53-56`
- **Observed Code**: `curr_r = round((curr_close - entry) / risk_per_share, 2)`
- **Failure Scenario**: When 50% is sold at +3R (+1.5R realized) and the remaining runner stops out at Breakeven SL (`curr_close == entry`), `curr_r` evaluates to `(entry - entry) / risk = 0.00R`. The profitable +1.50R gain is completely erased in `trade_history`.
- **Remediation**: Implement `_update_metrics` computing blended R: `(total_realized_pnl + unrealized_pnl) / initial_dollar_risk`.

#### [P0-5] SET 8-Tier Microstructure Non-Compliance (Bot 4)
- **Affected File**: `bot4_thai_pullback/src/indicators.py:17-42`
- **Failure Scenario**: Tick size table implements only 7 tiers, omitting Tier 8 ($\ge 400.00$ THB @ 2.00 THB tick). High-priced SET equities are assigned illegal 1.00 THB ticks.
- **Remediation**: Implement official 8-tier schedule.

#### [P0-6] Boundary Crossing Illegal Tick Generation (Bot 4)
- **Affected Files**: `bot4_thai_pullback/src/risk_manager.py:58-60`, `indicators.py`
- **Failure Scenario**: Stop loss is calculated via naive `raw_low - tick`. At 5.00 THB, subtracting 0.05 THB produces 4.95 THB, which does not exist on the SET order book (valid ticks below 5.00 are 4.98, 4.96 THB). Broker trading engines reject the order.
- **Remediation**: Implement `step_tick_down(price)` with exact boundary mapping.

#### [P0-7] Board Lot Floor Inversion Breaching Risk Budget & Capital Cap
- **Affected Files**: `bot4_thai_pullback/src/risk_manager.py:76, 91`, `bot3_pullback/src/risk_manager.py:76, 90`
- **Failure Scenario**: `shares = max(self.board_lot, board_lot_shares)` forces 100 shares onto the portfolio even when the risk budget affords only 20 shares, multiplying dollar risk by 5x (+400% breach). High-priced stocks breach the 20% capital cap.
- **Remediation**: Invalidate the trade plan (`is_valid = False`, `shares = 0`) when affordable shares fall below 100 shares (Bot 4) or 1 share (Bot 3), or when the 20% cap is exceeded.

---

### 4.2 Priority P1: High Defects (Risk Breaches, False Signals, Pipeline Crashes)

#### [P1-1] False Breakout & Bull Trap Vulnerability (Missing Candlestick Confirmation)
- **Affected Files**: `bot3_pullback/src/confluence_engine.py:155-156`, `bot4_thai_pullback/src/confluence_engine.py:107-112`
- **Failure Scenario**: Fires `BUY_TRIGGERED` whenever `curr_high > prior_high`. Intraday spikes that collapse into severe red shooting stars trigger immediate buys at the low of the day.
- **Remediation**: Port Bot 5/6 candlestick anatomy analysis: measure body, upper wick, lower wick; strictly reject shooting stars (`upper_wick >= 2.5 * body`); require green candle, hammer, or EMA bounce confirmation.

#### [P1-2] Screener Institutional Liquidity Logic Bugs
- **Affected Files**: `bot3_pullback/src/screener.py:69-70`, `bot4_thai_pullback/src/screener.py:70`
- **Failure Scenario**: Bot 3 uses `and` instead of `or`, letting illiquid micro-caps pass. Bot 4 uses `and turnover_20 < 10000000`, halving the 20M THB turnover threshold.
- **Remediation**: Require `vol_20 >= min_vol and dollar_vol_20 >= min_dollar_vol` in Bot 3; enforce strict 20M THB turnover in Bot 4.

#### [P1-3] Unsnapped Profit Targets Violating Discrete SET Ticks (Bot 4)
- **Affected File**: `bot4_thai_pullback/src/risk_manager.py:101-104`
- **Failure Scenario**: Generates targets via raw float arithmetic (e.g. 29.95 THB when valid ticks are 29.75 and 30.00 THB).
- **Remediation**: Snap all targets using `round_to_set_tick(target)`.

#### [P1-4] Missing Per-Ticker Exception Isolation in Pipeline
- **Affected Files**: `bot3_pullback/src/main.py:104-130`, `bot4_thai_pullback/src/main.py:91-115`
- **Failure Scenario**: Downloading active positions lacks `try...except` wrapper. A single Yahoo Finance network failure or 429 error crashes the entire scan before saving state.
- **Remediation**: Wrap individual ticker processing in `try...except`.

#### [P1-5] Signal Viability Gating in Main Pipeline
- **Affected Files**: `bot4_thai_pullback/src/main.py:162-202`, `bot3_pullback/src/main.py`
- **Failure Scenario**: Appends signals and auto-executes paper trades without verifying `plan.is_valid and plan.shares > 0`, generating 0-share trades for rejected setups.
- **Remediation**: Gate execution on `if plan.is_valid and plan.shares > 0:`.

#### [P1-6] Unescaped HTML Entities Causing Telegram Notification Drops
- **Affected Files**: `bot3_pullback/src/telegram_notifier.py`, `bot4_thai_pullback/src/telegram_notifier.py`
- **Failure Scenario**: Ticker notes containing `<`, `>`, `&` cause Telegram API to throw HTTP 400 Bad Request, dropping alerts silently.
- **Remediation**: Wrap dynamic strings in `html.escape()`.

#### [P1-7] Telegram Message Length Chunking ($\le 4096$ Characters)
- **Affected Files**: `bot3_pullback/src/telegram_notifier.py`, `bot4_thai_pullback/src/telegram_notifier.py`
- **Failure Scenario**: Alerts with 10+ signals exceed 4,096 characters and fail with HTTP 400 `MESSAGE_TOO_LONG`.
- **Remediation**: Implement line-aware chunking under 4,000 characters.

---

### 4.3 Priority P2: Medium Defects (Interactive Commands, Dynamic Buffers, Workflow Polish)

#### [P2-1] Missing Telegram `/stat` Performance Command Handler
- **Affected Files**: `bot3_pullback/src/command_handler.py:184-216`, `bot4_thai_pullback/src/`
- **Remediation**: Implement `/stat` handler computing win rate, total R, average win/loss R, and realized PnL.

#### [P2-2] Stop Loss Dynamic Buffer Scaling (Bot 3)
- **Affected File**: `bot3_pullback/src/risk_manager.py:59`
- **Remediation**: Upgrade flat $0.02 buffer to dynamic `max(0.15, round(raw_sl * 0.015, 2))`.

#### [P2-3] yfinance MultiIndex DataFrame Column Compatibility
- **Affected Files**: `bot3_pullback/src/screener.py:41-45`, `bot4_thai_pullback/src/screener.py`
- **Remediation**: Flatten MultiIndex columns: `if df.columns.nlevels > 1: df.columns = df.columns.get_level_values(0)`.

#### [P2-4] GitHub Actions Cron Schedule Collisions & Failure Alerts
- **Affected Files**: `.github/workflows/bot3_daily_scan.yml`, `bot4_daily_scan.yml`
- **Remediation**: Stagger cron schedules by 5-10 minutes and add `if: failure()` Telegram alert steps.

#### [P2-5] Compact Daily Report Target 5R Inclusion (Bot 4)
- **Affected File**: `bot4_thai_pullback/src/telegram_notifier.py:84`
- **Remediation**: Add Target 5R to compact alert summaries.

---

### 4.4 Priority P3: Housekeeping & Infrastructure (Import Shims, Test Fixtures)

#### [P3-1] Standalone Script Execution Import Shims
- **Affected Files**: All files in `bot3_pullback/src/` and `bot4_thai_pullback/src/`
- **Remediation**: Add fallback import shims (`try ... from .indicators except ImportError: from indicators`) to support standalone execution.

#### [P3-2] Automated Test Harness Deployment
- **Affected Files**: New `tests/` directory
- **Remediation**: Deploy comprehensive pytest test suite covering tick math, board lots, risk caps, blended R, and atomic persistence.

---

## 5. Implementation & Refactoring Roadmap

### 5.1 Phased Execution Schedule (Milestones M0 to M4)

```
+---------------------------------------------------------------------------------------------------+
|                                  PHASED IMPLEMENTATION ROADMAP                                    |
+===================================================================================================+
| MILESTONE M0: AUDIT PROPOSAL & SPECIFICATION (Current Turn)                                       |
| [x] Author docs/bot3_bot4_audit_proposal.md synthesising all 5 areas and benchmarking matrix.      |
| [x] Establish root PROJECT.md matching orchestrator implementation plan.                          |
+---------------------------------------------------------------------------------------------------+
| MILESTONE M1: BOT 3 REFACTORING & HARDENING                                                       |
| [ ] F02: Atomic State Persistence (tempfile.mkstemp + os.replace in main.py & command_handler.py). |
| [ ] F03: Master Dashboard Schema Parity (save pnl_r, pnl_pct, shares in trade_history).           |
| [ ] F04: Risk Budget & 20% Cap (remove max(1, shares) override; invalidate trade on breach).      |
| [ ] F05: Single-Share Zombie Fix & Blended R-Multiple (handle curr_shares <= 1; _update_metrics). |
| [ ] F06: Candlestick Rejection Filter (reject shooting stars; require green/hammer/bounce).       |
| [ ] F07: Telegram /stat Command Handler (implement performance metrics calculation).              |
| [ ] F08: Config & Workflow Parity (set max_alloc to 20.0%; add failure alert in workflow).        |
+---------------------------------------------------------------------------------------------------+
| MILESTONE M2: BOT 4 REFACTORING & SET COMPLIANCE                                                  |
| [ ] F09: SET 8-Tier Tick Schedule, step_tick_down(), and round_to_set_tick() in indicators.py.    |
| [ ] F10: SET Board Lot (100 sh) & Risk Floor (invalidate trade if affordable < 100 or cap breached).|
| [ ] F11: Zombie 0-Share TP1 Fix (set CLOSED_TP1 when 100-share position hits 3R).                 |
| [ ] F12: True Blended R & Dashboard Schema (save pnl_r, pnl_pct in trade_history).                |
| [ ] F13: Candlestick Rejection & Turnover Filter (reject shooting stars; fix 20M turnover clause).|
| [ ] F14: Atomic State & Signal Gating (atomic save_config; gate on plan.is_valid).                |
| [ ] F15: Telegram HTML Escaping & Workflow Parity (html.escape; workflow failure notifications).   |
+---------------------------------------------------------------------------------------------------+
| MILESTONE M3: COMPREHENSIVE E2E TEST SUITE (TIERS 1-4)                                            |
| [ ] F16: Deploy tests/ suite covering SET tick math, board lots, risk caps, blended R, atomic IO. |
| [ ] Run py_compile and verify import checks across all modified modules.                          |
+---------------------------------------------------------------------------------------------------+
| MILESTONE M4: FINAL ADVERSARIAL GATE & AUDIT (TIER 5)                                             |
| [ ] F17: Run adversarial math stress-test harness and execute Master Dashboard build verification.|
| [ ] Conduct final Forensic Auditor review and produce comprehensive completion handoff.           |
+---------------------------------------------------------------------------------------------------+
```

---

### 5.2 Production-Ready Code Blueprints

#### Blueprint 1: SET 8-Tier Schedule & Boundary Stepping (`bot4_thai_pullback/src/indicators.py`)

```python
import numpy as np

def get_thai_tick_size(price: float) -> float:
    """Official 8-tier Stock Exchange of Thailand (SET) tick size schedule."""
    p = float(price)
    if p < 2.0:
        return 0.01
    elif p < 5.0:
        return 0.02
    elif p < 10.0:
        return 0.05
    elif p < 25.0:
        return 0.10
    elif p < 100.0:
        return 0.25
    elif p < 200.0:
        return 0.50
    elif p < 400.0:
        return 1.00
    else:
        return 2.00  # Official SET Tier 8 (>= 400.0 THB)


def step_tick_down(price: float) -> float:
    """Steps down exactly 1 valid SET tick across tier boundaries."""
    p = round(float(price), 4)
    if p <= 0.01:
        return 0.01
    if 1.99 < p <= 2.00:
        return 1.99
    elif 4.98 < p <= 5.00:
        return 4.98
    elif 9.95 < p <= 10.00:
        return 9.95
    elif 24.90 < p <= 25.00:
        return 24.90
    elif 99.75 < p <= 100.00:
        return 99.75
    elif 199.50 < p <= 200.00:
        return 199.50
    elif 399.00 < p <= 400.00:
        return 399.00
    else:
        tick = get_thai_tick_size(p - 0.0001)
        return round(max(0.01, p - tick), 2)


def round_to_set_tick(price: float, mode: str = "nearest") -> float:
    """Snaps any arbitrary floating-point price to a legal SET tick increment."""
    p = round(float(price), 4)
    if p <= 0.01:
        return 0.01
    tick = get_thai_tick_size(p)
    if mode == "down":
        val = np.floor(p / tick + 1e-9) * tick
    elif mode == "up":
        val = np.ceil(p / tick - 1e-9) * tick
    else:
        val = np.round(p / tick) * tick

    new_tick = get_thai_tick_size(val)
    if new_tick != tick:
        if mode == "down":
            val = np.floor(val / new_tick + 1e-9) * new_tick
        elif mode == "up":
            val = np.ceil(val / new_tick - 1e-9) * new_tick
        else:
            val = np.round(val / new_tick) * new_tick

    return round(float(val), 2)
```

---

#### Blueprint 2: SET Risk Manager & Floor Inversion Guard (`bot4_thai_pullback/src/risk_manager.py`)

```python
from dataclasses import dataclass
from typing import Optional, Dict
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
    board_lots: int
    capital_allocated: float
    allocation_pct: float
    target_1r: float
    target_2r: float
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

        # Boundary-safe SET stop loss
        stop_loss = step_tick_down(raw_low)

        risk_per_share = round(entry_price - stop_loss, 2)
        if risk_per_share <= 0:
            tick = get_thai_tick_size(entry_price)
            stop_loss = round(entry_price - (tick * 2), 2)
            risk_per_share = round(entry_price - stop_loss, 2)

        risk_pct = round((risk_per_share / entry_price) * 100.0, 2) if entry_price > 0 else 0.0
        dollar_risk_budget = round(port_equity * (self.risk_pct / 100.0), 2)

        raw_shares = int(dollar_risk_budget / risk_per_share) if risk_per_share > 0 else 0
        board_lot_shares = (raw_shares // self.board_lot) * self.board_lot

        is_valid = True
        is_capped = False
        warning_note = ""

        # Guard: Invalidate if risk budget cannot afford 1 Board Lot
        if board_lot_shares < self.board_lot:
            is_valid = False
            shares = 0
            board_lots = 0
            capital_allocated = 0.0
            allocation_pct = 0.0
            warning_note = (
                f"งบเสี่ยง {dollar_risk_budget:,.0f} ฿ ไม่พอซื้อ 1 Board Lot (100 หุ้น) "
                f"ที่ SL {stop_loss:.2f} ฿ (ต้องใช้ {risk_per_share * 100:,.0f} ฿)"
            )
        else:
            shares = board_lot_shares
            board_lots = shares // self.board_lot
            capital_allocated = round(shares * entry_price, 2)
            allocation_pct = round((capital_allocated / port_equity) * 100.0, 2)

            # Guard: 20% Max Capital Allocation Cap
            max_capital = port_equity * (self.max_alloc_pct / 100.0)
            if capital_allocated > max_capital and entry_price > 0:
                capped_raw = int(max_capital / entry_price)
                capped_shares = (capped_raw // self.board_lot) * self.board_lot
                if capped_shares < self.board_lot:
                    is_valid = False
                    shares = 0
                    board_lots = 0
                    capital_allocated = 0.0
                    allocation_pct = 0.0
                    warning_note = (
                        f"ราคาหุ้น {entry_price:.2f} ฿ ซื้อ 1 Board Lot ต้องใช้ {entry_price * 100:,.0f} ฿ "
                        f"เกินเพดาน {self.max_alloc_pct}% ({max_capital:,.0f} ฿)"
                    )
                else:
                    shares = capped_shares
                    board_lots = shares // self.board_lot
                    capital_allocated = round(shares * entry_price, 2)
                    allocation_pct = round((capital_allocated / port_equity) * 100.0, 2)
                    is_capped = True
                    actual_risk = round(shares * risk_per_share, 2)
                    warning_note = f"Cap ที่ {self.max_alloc_pct}% ({max_capital:,.0f} ฿). ความเสี่ยงจริง: {actual_risk:,.0f} ฿"

        # Snap all targets to legal SET ticks
        target_1r = round_to_set_tick(entry_price + (1.0 * risk_per_share), mode="nearest")
        target_2r = round_to_set_tick(entry_price + (2.0 * risk_per_share), mode="nearest")
        target_3r = round_to_set_tick(entry_price + (3.0 * risk_per_share), mode="nearest")
        target_5r = round_to_set_tick(entry_price + (5.0 * risk_per_share), mode="nearest")

        return ThaiTradePlan(
            ticker=ticker,
            entry_price=round(entry_price, 2),
            stop_loss=stop_loss,
            risk_per_share=risk_per_share,
            risk_pct=risk_pct,
            portfolio_equity=round(port_equity, 2),
            risk_budget_pct=self.risk_pct,
            dollar_risk_budget=dollar_risk_budget,
            shares=shares,
            board_lots=board_lots,
            capital_allocated=capital_allocated,
            allocation_pct=allocation_pct,
            target_1r=target_1r,
            target_2r=target_2r,
            target_3r=target_3r,
            target_5r=target_5r,
            is_valid=is_valid,
            is_capped=is_capped,
            warning_note=warning_note,
        )
```

---

#### Blueprint 3: US Risk Manager & 20% Cap Guard (`bot3_pullback/src/risk_manager.py`)

```python
from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class TradePlan:
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
    target_1r: float
    target_2r: float
    target_3r: float
    target_5r: float
    is_valid: bool = True
    is_capped: bool = False
    warning_note: str = ""

class RiskManager:
    def __init__(self, config: Dict):
        self.config = config
        self.portfolio_equity = float(config.get("portfolio_equity", 10000.0))
        self.risk_pct = float(config.get("risk_per_trade_pct", 0.5))
        self.max_alloc_pct = float(config.get("max_allocation_per_trade_pct", 20.0))

    def calculate_trade_plan(
        self,
        ticker: str,
        entry_price: float,
        curr_low: float,
        prior_low: float,
        equity: Optional[float] = None
    ) -> TradePlan:
        port_equity = equity if equity is not None else self.portfolio_equity
        raw_low = min(curr_low, prior_low)

        # Dynamic price-scaled buffer
        buffer = max(0.15, round(raw_low * 0.015, 2))
        stop_loss = round(max(0.01, raw_low - buffer), 2)

        risk_per_share = round(entry_price - stop_loss, 2)
        if risk_per_share <= 0:
            risk_per_share = round(max(0.01, entry_price * 0.025), 2)
            stop_loss = round(entry_price - risk_per_share, 2)

        risk_pct = round((risk_per_share / entry_price) * 100.0, 2) if entry_price > 0 else 0.0
        dollar_risk_budget = round(port_equity * (self.risk_pct / 100.0), 2)

        raw_shares = int(dollar_risk_budget / risk_per_share) if risk_per_share > 0 else 0
        is_valid = True
        is_capped = False
        warning_note = ""

        # Guard: Invalidate if risk budget cannot afford 1 share
        if raw_shares < 1:
            is_valid = False
            shares = 0
            capital_allocated = 0.0
            allocation_pct = 0.0
            warning_note = f"Risk budget ${dollar_risk_budget:.0f} insufficient for 1 share at SL ${stop_loss:.2f}"
        else:
            shares = raw_shares
            capital_allocated = round(shares * entry_price, 2)
            allocation_pct = round((capital_allocated / port_equity) * 100.0, 2)

            # Guard: 20% Max Capital Allocation Cap
            max_capital = port_equity * (self.max_alloc_pct / 100.0)
            if capital_allocated > max_capital and entry_price > 0:
                capped_shares = int(max_capital / entry_price)
                if capped_shares < 1:
                    is_valid = False
                    shares = 0
                    capital_allocated = 0.0
                    allocation_pct = 0.0
                    warning_note = f"Stock price ${entry_price:.2f} exceeds {self.max_alloc_pct}% max capital cap (${max_capital:,.0f})"
                else:
                    shares = capped_shares
                    capital_allocated = round(shares * entry_price, 2)
                    allocation_pct = round((capital_allocated / port_equity) * 100.0, 2)
                    is_capped = True
                    actual_risk = round(shares * risk_per_share, 2)
                    warning_note = f"Cap at {self.max_alloc_pct}% (${max_capital:,.0f}). Actual risk: ${actual_risk:,.0f}"

        target_1r = round(entry_price + (1.0 * risk_per_share), 2)
        target_2r = round(entry_price + (2.0 * risk_per_share), 2)
        target_3r = round(entry_price + (3.0 * risk_per_share), 2)
        target_5r = round(entry_price + (5.0 * risk_per_share), 2)

        return TradePlan(
            ticker=ticker,
            entry_price=round(entry_price, 2),
            stop_loss=stop_loss,
            risk_per_share=risk_per_share,
            risk_pct=risk_pct,
            portfolio_equity=round(port_equity, 2),
            risk_budget_pct=self.risk_pct,
            dollar_risk_budget=dollar_risk_budget,
            shares=shares,
            capital_allocated=capital_allocated,
            allocation_pct=allocation_pct,
            target_1r=target_1r,
            target_2r=target_2r,
            target_3r=target_3r,
            target_5r=target_5r,
            is_valid=is_valid,
            is_capped=is_capped,
            warning_note=warning_note,
        )
```

---

#### Blueprint 4: Zombie-Proof Exit Tracker & Blended R (`both/src/exit_tracker.py`)

```python
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

    # In check_exit():
    # 2. Check Target 3R (Take Profit 1)
    if not tp1_hit and curr_high >= target_3r and curr_shares > 0:
        pos["tp1_hit"] = True
        pos["current_sl"] = round(max(pos["current_sl"], entry), 2)  # Move SL to Breakeven

        unit_lot = getattr(self, "board_lot", 1)
        if curr_shares <= unit_lot:
            # Single unit (1 share or 100 shares) -> Full 100% exit at 3R
            sell_qty = curr_shares
            pnl = round((target_3r - entry) * sell_qty, 2)
            pos["status"] = "CLOSED_TP1"
            pos["exit_price"] = target_3r
            pos["exit_date"] = date_str
            pos["exit_reason"] = f"Target 3R Hit (100% Exit for {unit_lot} Lot)"
            pos["total_realized_pnl"] = round(pos.get("total_realized_pnl", 0.0) + pnl, 2)
            pos["current_shares"] = 0
            curr_shares = 0

            actions.append({
                "type": "TP1_3R_FULL",
                "ticker": pos["ticker"],
                "shares_sold": sell_qty,
                "price": target_3r,
                "pnl": pnl,
                "message": f"🎯 <b>${pos['ticker']} ถึงเป้า 3R @ <code>{target_3r:.2f}</code></b> (ปิดทำกำไร 100%)"
            })
            self._update_metrics(pos, entry, risk_per_share, initial_shares, curr_close)
            return pos, actions
        else:
            raw_sell = int(curr_shares * self.tp1_ratio)
            sell_qty = (raw_sell // unit_lot) * unit_lot if unit_lot > 1 else max(1, raw_sell)
            if sell_qty >= curr_shares:
                sell_qty = curr_shares - unit_lot  # Guarantee at least 1 runner unit remains

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
            })
```

---

#### Blueprint 5: Candlestick Rejection Filter (`both/src/confluence_engine.py`)

```python
    # Candlestick anatomy analysis
    curr_open = float(df["Open"].iloc[-1]) if "Open" in df.columns else curr_close
    body = abs(curr_close - curr_open)
    upper_wick = curr_high - max(curr_close, curr_open)
    lower_wick = min(curr_close, curr_open) - curr_low

    is_green = curr_close > curr_open
    hammer = (lower_wick >= 1.5 * max(body, 0.05)) and (upper_wick <= 1.0 * max(body, 0.05))
    is_shooting_star = (upper_wick >= 2.5 * max(body, 0.05)) and (lower_wick <= 0.5 * upper_wick)
    bounce_e9 = curr_close > support_info["ema9"] and curr_close > prior_high * 0.995

    # Eliminate severe shooting stars / bull traps
    has_candle_confirmation = (is_green or hammer or bounce_e9) and not is_shooting_star
    trigger_fired = (curr_high > prior_high or curr_close > prior_high) and has_candle_confirmation
```

---

#### Blueprint 6: Atomic State Persistence Engine (`both/src/main.py`)

```python
import os
import json
import tempfile
from typing import Dict

def save_config(cfg: Dict):
    """Atomic state persistence using tempfile and os.replace."""
    dir_name = os.path.dirname(os.path.abspath(CONFIG_PATH))
    os.makedirs(dir_name, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(dir=dir_name, text=True)
    with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, CONFIG_PATH)
```

In `main.py` closed trade handler:
```python
    if updated_pos["current_shares"] == 0 or updated_pos.get("status", "").startswith("CLOSED"):
        init_shares = int(pos.get("initial_shares", pos.get("shares", 0)))
        init_entry = float(pos.get("entry_price", 0.0))
        risk_per_sh = float(pos.get("risk_per_share", 0.0))
        tot_realized = float(updated_pos.get("total_realized_pnl", 0.0))
        init_risk_dollar = init_shares * risk_per_sh
        true_r = round(tot_realized / init_risk_dollar, 2) if init_risk_dollar > 0 else 0.0
        pnl_pct = round((tot_realized / (init_shares * init_entry)) * 100.0, 2) if (init_shares * init_entry) > 0 else 0.0

        trade_history.append({
            "ticker": ticker,
            "entry_date": pos.get("entry_date", "-"),
            "exit_date": updated_pos.get("exit_date", today_str),
            "entry_price": init_entry,
            "exit_price": float(updated_pos.get("exit_price", 0.0)),
            "shares": init_shares,
            "realized_pnl": tot_realized,
            "r_multiple": true_r,
            "pnl_r": true_r,       # Essential for src/build_master_dashboard.py
            "pnl_pct": pnl_pct,   # Essential for src/build_master_dashboard.py
            "exit_reason": updated_pos.get("exit_reason", "-")
        })
```

---

#### Blueprint 7: Telegram HTML Sanitizer & Message Chunker (`both/src/telegram_notifier.py`)

```python
import html

def sanitize_html(text: str) -> str:
    """Safely escapes dynamic strings for Telegram HTML parse mode."""
    return html.escape(str(text))

def send_chunked_message(self, text: str, max_chunk: int = 4000) -> bool:
    """Splits message into blocks <= 4000 chars to avoid Telegram 4096 limit."""
    if len(text) <= max_chunk:
        return self.send_message(text)

    chunks = []
    lines = text.split("\n")
    curr = []
    curr_len = 0
    for line in lines:
        if curr_len + len(line) + 1 > max_chunk:
            chunks.append("\n".join(curr))
            curr = [line]
            curr_len = len(line)
        else:
            curr.append(line)
            curr_len += len(line) + 1
    if curr:
        chunks.append("\n".join(curr))

    success = True
    for chunk in chunks:
        res = self.send_message(chunk)
        if not res:
            success = False
    return success
```

---

#### Blueprint 8: Interactive `/stat` Performance Handler (`bot3_pullback/src/command_handler.py`)

```python
        elif text == "/stat":
            history = cfg.get("trade_history", [])
            active = cfg.get("active_positions", {})
            total = len(history)
            wins = [h for h in history if float(h.get("realized_pnl", 0)) > 0]
            losses = [h for h in history if float(h.get("realized_pnl", 0)) <= 0]
            win_rate = (len(wins) / total * 100.0) if total > 0 else 0.0
            tot_r = sum(float(h.get("pnl_r", h.get("r_multiple", 0))) for h in history)
            tot_pnl = sum(float(h.get("realized_pnl", 0)) for h in history)

            win_rs = [float(h.get("pnl_r", h.get("r_multiple", 0))) for h in wins]
            loss_rs = [float(h.get("pnl_r", h.get("r_multiple", 0))) for h in losses]
            avg_win = (sum(win_rs) / len(win_rs)) if win_rs else 0.0
            avg_loss = (sum(loss_rs) / len(loss_rs)) if loss_rs else 0.0

            stat_msg = (
                "📊 <b>BOT 3 FORWARD TEST PERFORMANCE</b>\n"
                "━━━━━━━━━━━━━━━━\n"
                f"• ออเดอร์ที่เปิดอยู่: <code>{len(active)} ตัว</code>\n"
                f"• ไม้ปิดรอบทั้งหมด: <code>{total} ไม้</code>\n"
                f"• Win Rate: <code>{win_rate:.1f}%</code> (ชนะ {len(wins)} / แพ้ {len(losses)})\n"
                f"• กำไรสะสมสุทธิ: <code>{tot_r:+.2f}R</code> (<code>${tot_pnl:+,.2f}</code>)\n"
                f"• ชนะเฉลี่ย: <code>+{avg_win:.2f}R</code> | แพ้เฉลี่ย: <code>{avg_loss:.2f}R</code>\n"
                "━━━━━━━━━━━━━━━━"
            )
            self.send_message(chat_id, stat_msg)
```

---

### 5.3 Verification Methodology & Acceptance Checklist

To verify the defects and validate the refactoring plan:

1. **Syntax & Compilation Verification**:
   ```powershell
   python -m py_compile bot3_pullback/src/*.py
   python -m py_compile bot4_thai_pullback/src/*.py
   ```
   *Acceptance Criteria*: 0 compilation errors across all modules.

2. **SET Microstructure & Math Stress-Testing**:
   Run the adversarial math test suite covering all 8 SET tick tiers, boundary transitions (5.00 -> 4.98, 25.00 -> 24.90), 100-share board lot floor guards, and 20% capital caps:
   ```powershell
   pytest scratch/adversarial_math_stress_test.py -v
   ```
   *Acceptance Criteria*: 100% of tested prices snap to valid SET ticks; 0 risk budget or capital cap breaches.

3. **Blended R-Multiple & Single-Lot Exit Verification**:
   Verify that a 50% TP1 exit followed by a Breakeven SL exit records $+1.50R$ (not $0.00R$), and that 1-share/100-share positions exit cleanly as `CLOSED_TP1` without lingering as zombie 0-share records.

4. **Master Dashboard Schema Integration Check**:
   Execute `python src/build_master_dashboard.py` and inspect `docs/index.html`.
   *Acceptance Criteria*: Both Bot 3 and Bot 4 closed trades report accurate non-zero win rates and matching positive R-multiples.

5. **Atomic State Write & Recovery Test**:
   Simulate process interrupts during `save_config()` to verify that `config.json` remains completely intact and never truncates to 0 bytes.

---

*Authored by Technical Documentation Specialist & Forensic Audit Team. Formally approved for Milestone M0 release.*
