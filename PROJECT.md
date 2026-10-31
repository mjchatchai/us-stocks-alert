# Project: Bot 3 (US Pullback) & Bot 4 (Thai SET Pullback) Forensic Audit and Refactoring

## Architecture
- **Bot 3 (US Trend Pullback Scanner)**: `bot3_pullback/`
  - Modules: `indicators.py`, `confluence_engine.py`, `risk_manager.py`, `exit_tracker.py`, `screener.py`, `chart_generator.py`, `telegram_notifier.py`, `command_handler.py`, `dashboard_builder.py`, `main.py`.
  - State & Config: `config/config.json` (portfolio equity $10,000, 0.5% risk = $50, 20% max allocation = $2,000).
- **Bot 4 (Thai SET Trend Pullback Scanner)**: `bot4_thai_pullback/`
  - Modules: `indicators.py`, `confluence_engine.py`, `risk_manager.py`, `exit_tracker.py`, `screener.py`, `chart_generator.py`, `telegram_notifier.py`, `dashboard_builder.py`, `main.py`.
  - State & Config: `config/config.json` (portfolio equity 1,000,000 THB, 0.5% risk = 5,000 THB, 20% max allocation = 200,000 THB, 100-share board lot, SET 8-tier tick sizing).
- **Shared Master Dashboard**: `src/build_master_dashboard.py` -> reads `trade_history` from each bot's `config.json`. Requires `pnl_r` and `pnl_pct` fields.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F01 | Comprehensive Audit Document | Author comprehensive audit proposal in `docs/bot3_bot4_audit_proposal.md` synthesising all 5 areas | M0 | Survey (Explorers 1, 2, 3) |
| F02 | Bot 3 Atomic State Persistence | Implement `tempfile.mkstemp` + `os.replace` in `bot3_pullback/src/main.py` | M1 | Survey (Explorer 1) |
| F03 | Bot 3 Master Dashboard Schema | Add `pnl_r`, `pnl_pct`, and `shares` to `trade_history` in `bot3_pullback/src/main.py` | M1 | Survey (Explorer 1, 3) |
| F04 | Bot 3 Risk Budget & Capital Cap | Remove `max(1, shares)` override; reject trades when budget < 1 share or price > 20% cap ($2,000) | M1 | Survey (Explorer 1) |
| F05 | Bot 3 Single-Share & Blended Exit | Handle `curr_shares <= 1` cleanly at TP1 (3R); calculate true blended R-multiple in `exit_tracker.py` | M1 | Survey (Explorer 1) |
| F06 | Bot 3 Candlestick Rejection Filter | Add shooting-star rejection and require green candle / hammer confirmation in `confluence_engine.py` | M1 | Survey (Explorer 1) |
| F07 | Bot 3 Telegram /stat Command | Implement `/stat` command handler in `bot3_pullback/src/command_handler.py` | M1 | Survey (Explorer 1) |
| F08 | Bot 3 Config & Workflow Parity | Update `max_allocation_per_trade_pct` to 20.0 in `config.json`; add failure alert in workflow | M1 | Survey (Explorer 1, 3) |
| F09 | Bot 4 SET 8-Tier Tick Sizing | Implement full 8-tier tick table, `step_tick_down()`, and `round_to_set_tick()` in `indicators.py` | M2 | Survey (Explorer 2) |
| F10 | Bot 4 SET Board Lot & Risk Floor | Enforce 100-share board lots; invalidate trade (`is_valid=False`, `shares=0`) if affordable < 100 or cap breached | M2 | Survey (Explorer 2) |
| F11 | Bot 4 Zombie 0-Share TP1 Fix | Set `pos["status"] = "CLOSED_TP1"` when single board lot (100 sh) takes profit at 3R | M2 | Survey (Explorer 2) |
| F12 | Bot 4 True Blended R & Dashboard | Implement cumulative blended R-multiple calculation; write `pnl_r` and `pnl_pct` in `trade_history` | M2 | Survey (Explorer 2, 3) |
| F13 | Bot 4 Candlestick Rejection & Turnover | Reject shooting stars / require green candle in `confluence_engine.py`; fix turnover threshold in `screener.py` | M2 | Survey (Explorer 2) |
| F14 | Bot 4 Atomic State & Signal Gating | Implement atomic `save_config`; gate signal execution on `plan.is_valid and plan.shares > 0` | M2 | Survey (Explorer 2) |
| F15 | Bot 4 Telegram & Workflow Parity | Add HTML escaping in `telegram_notifier.py`; add workflow failure notifications | M2 | Survey (Explorer 2, 3) |
| F16 | Comprehensive E2E Test Suite | Build test suite covering Tiers 1-4 (SET tick rules, board lot math, risk caps, blended R, atomic writes, dashboard integration) | M3 | Survey (Explorer 3) |
| F17 | Adversarial Hardening (Tier 5) | Adversarial coverage verification with Challenger and Forensic Auditor integrity checks | M3 | Survey (Explorers 1, 2, 3) |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M0 | Audit Proposal Documentation | Author `docs/bot3_bot4_audit_proposal.md` and project root `PROJECT.md` | none | IN_PROGRESS |
| M1 | Bot 3 Refactoring & Hardening | Implement F02-F08 in `bot3_pullback/` | M0 | PLANNED |
| M2 | Bot 4 Refactoring & SET Compliance | Implement F09-F15 in `bot4_thai_pullback/` | M0 | PLANNED |
| M3 | E2E Testing & Verification (Tiers 1-4) | Build and run comprehensive unit and E2E test suite | M1, M2 | PLANNED |
| M4 | Final Adversarial Gate & Audit (Tier 5) | Challenger stress tests and Forensic Auditor integrity audit | M3 | PLANNED |

## Interface Contracts
### `bot3_pullback/src/risk_manager.py` ↔ `main.py`
- `calculate_position_size(entry_price, stop_loss, port_equity)` -> `PositionPlan(entry_price, stop_loss, shares, target_3r, target_5r, is_valid, invalid_reason)`
- When `shares == 0` or risk budget / capital cap violated: `is_valid = False`, `shares = 0`.
- `main.py` must check `if not plan.is_valid or plan.shares <= 0: continue`.

### `bot4_thai_pullback/src/indicators.py` ↔ `risk_manager.py` / `exit_tracker.py`
- `get_thai_tick_size(price: float) -> float`: 8-tier SET table (<2: 0.01, 2-5: 0.02, 5-10: 0.05, 10-25: 0.10, 25-100: 0.25, 100-200: 0.50, 200-400: 1.00, >=400: 2.00).
- `step_tick_down(price: float) -> float`: Steps down exactly 1 tick across tier boundaries (e.g. 5.00 -> 4.98, 25.00 -> 24.90, 100.00 -> 99.75).
- `round_to_set_tick(price: float) -> float`: Rounds price to nearest legal tick on SET order books.

### `exit_tracker.py` ↔ `main.py` ↔ `src/build_master_dashboard.py`
- Position dictionary contains:
  - `entry_price`, `entry_shares`, `current_shares`, `current_sl`, `tp1_hit`, `tp2_hit`, `total_realized_pnl`, `initial_risk_dollar`
- Blended R formula:
  - `unrealized_pnl = (curr_close - entry_price) * current_shares`
  - `total_pnl = total_realized_pnl + unrealized_pnl`
  - `blended_r = round(total_pnl / initial_risk_dollar, 2)`
- Closed trade record in `trade_history`:
  - `ticker`, `entry_date`, `exit_date`, `entry_price`, `exit_price`, `shares`, `exit_reason`, `realized_pnl`, `pnl_r`, `pnl_pct`, `r_multiple`
- When `curr_shares == 0` at TP1: status marked `"CLOSED_TP1"`, `exit_price = target_3r`, removed from active positions and appended to `trade_history`.

## Code Layout
- `bot3_pullback/src/`:
  - `main.py`, `risk_manager.py`, `exit_tracker.py`, `confluence_engine.py`, `screener.py`, `indicators.py`, `command_handler.py`, `telegram_notifier.py`, `dashboard_builder.py`
- `bot3_pullback/config/config.json`
- `bot4_thai_pullback/src/`:
  - `main.py`, `risk_manager.py`, `exit_tracker.py`, `confluence_engine.py`, `screener.py`, `indicators.py`, `telegram_notifier.py`, `dashboard_builder.py`
- `bot4_thai_pullback/config/config.json`
- `docs/bot3_bot4_audit_proposal.md`
- `scratch/` & `tests/`: E2E and adversarial test harnesses
