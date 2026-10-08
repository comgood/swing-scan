# 0007. Build the portfolio backtest as a day loop over one shared exit `step()`

**Date**: 2026-10-08
**Status**: In Progress (owner signed off 2026-10-08)
**Authorized by**: /architect, run unattended overnight by the orchestrator lane; every open
question took /architect's recommended answer (listed below) and waits for the owner

## Summary

This spec designs scope feature 9: the single config backtest and its report page. The engine
walks the trading days one by one, buys the top ranked new signals into free slots at the next
open, and runs every held position through one shared exit function (`step()`), the same one the
exit lab will use later. It returns IS and OOS metrics side by side, an equity curve against
`DEMO-INDEX`, and a trade list with MAE and MFE. The web app gets a report page that shows the
assumptions header, the metrics, the chart, the trades and the trial counter. The engine part
(BE lane) is built first against the approved oracles in `tests/oracle/` (gate G1, PR #9); the
report page (FE lane) is built in parallel against the existing mocks.

## Assumed decisions (signed off by the owner, 2026-10-08)

The owner could not answer during this run. Each question took /architect's recommended answer;
the runner up is in [rationale.md](rationale.md).

1. **Exit split between features 9 and 11.** Feature 9 builds the `Exit` protocol, `step()` with
   the full doc 02 §7.2 precedence, and the `stop_pct`, `time`, delisting and `end_of_test`
   exits. Feature 11 adds `stop_atr`, `target`, `trail_pct` and `close_below_ma` as new `Exit`
   classes only, never touching `step()`. Until then a request using them returns 501 (feature
   11). So B-9 and B-10 (portfolio half) turn green with feature 11, not 9.
2. **Trade mode stays out.** 2 to 6 configs return 501 naming feature 12 (exit lab). Feature 9
   ships the per trade walker `walk_trade()` only as the internal function that feature 12's
   loop will call, because it costs a few lines and lets the parity oracle land with feature 12
   unchanged.
3. **Day order.** On each session: held positions step first (exits fill), then new entries fill
   at the open from the previous close's ranked signals, then the entry bar's own steps 2 to 5
   run, then everything is marked at the close.
4. **Free slots and sizing.** Slots = `max_positions` minus positions held at the previous close
   (a slot freed today is usable from tomorrow). Each entry's notional = equity at the signal
   close ÷ `max_positions`, capped by the cash on hand; fractional shares, no leverage, cash
   earns 0%.
5. **Ranking.** `rs(126)` at the signal bar, descending, then ticker A to Z; a null `rs(126)`
   (a young ticker) ranks after every non null one. A ticker already held is skipped.
6. **Equity scale.** Equity starts at 100.0; the benchmark curve is `DEMO-INDEX` close rescaled
   to start at 100.0 on the same first session.
7. **IS and OOS.** `oos_start` is the session at index `floor(0.7 × n)` of the backtest window's
   n sessions. Trades go to the segment of their entry date. Curve metrics for OOS run on the
   OOS part of the same continuous equity curve (no restart).
8. **Metric formulas.** 252 sessions a year, risk free rate 0, Sharpe from daily equity returns
   with `ddof=1`, exposure = average share of equity held in positions at each close, a trade
   with `return_pct ≤ 0` counts as a loss (full table below).
9. **Curve and trade limits.** Curves are thinned to at most 500 points by taking every k th
   session (k = ceil(n / 500)) plus always the last; metrics use the full daily curve. The trade
   list keeps the 2,000 most recent trades by entry date when longer, with `trades_truncated`
   and a `trades_truncated` warning.
10. **Window.** `sim.end` cuts the market before anything is computed (no look ahead, B-10).
    `sim.start` only stops signals before it; indicators still warm up on earlier bars.
11. **Report page.** A static `/backtest` page in `apps/web/src/features/backtest/`, reached
    from the template workspace's "Backtest" button. It carries its inputs in the URL
    (`?template=` until feature 10 adds `?r=`, plus `?x=` for the config), and runs on submit.
12. **Chart.** Lightweight Charts (already in the stack, spec 0001) with two lines, strategy and
    benchmark, no overlays.

## Requirements

**User stories**:
- As a researcher, I want to backtest one rule with one exit config as a real portfolio, so I see
  what slot limits, sizing and costs do to the idea.
- As a researcher, I want IS and OOS side by side and the full assumptions, so I can judge the
  result honestly and reproduce it.

**Acceptance criteria** (the contract; doc 01 IDs in brackets):

Engine and API (BE):
- **AC-1** [B-1, B-2]: a `stop_pct` exit fills at `min(open, stop) × (1 − slip)`; a gap below the
  stop fills at the open × (1 − slip). P&L matches to 1e-9.
- **AC-2** [B-7]: a `time` exit with N bars fills at close(entry bar + N − 1) × (1 − slip); the
  entry bar is bar 1.
- **AC-3** [B-8]: a held ticker that delists exits at its last close × (1 − slip), reason
  `delisted`; an open position on the window's last session exits at that close, reason
  `end_of_test`.
- **AC-4** [B-9, with feature 11's target]: MAE and MFE in % and R follow doc 02 §7.2's exit bar
  rule; `R = entry fill − initial stop`, null without a stop.
- **AC-5** [B-10]: replacing every bar after `sim.end` with garbage changes nothing in the
  response (portfolio half; all six exits once feature 11 lands).
- **AC-6** [B-11]: with 15 signals, `max_positions = 10` and no open positions, the top 10 by
  `rs(126)` (then ticker) are entered at equity ÷ 10 each.
- **AC-7** [B-13]: identical inputs give identical responses; a full history seed 42 run
  answers warm in under 3 s with a body under 6 MB.
- **AC-8** [B-14 to B-16]: entries come only from the shared `entry_signals` (rising edge,
  cooldown 10 on accepted signals, no last bar entry); a held ticker's signal is skipped.
- **AC-9**: the response is a valid `PortfolioResult` (spec 0002): metrics IS and OOS, benchmark
  metrics, equity and benchmark at most 500 points, at most 2,000 trades with `trades_total`,
  `trial` from `structure_key` and `pair_key`, warnings `no_entries` and `trades_truncated`
  when they apply, and every undefined number `null`.
- **AC-10** [U-3]: `assumptions` echoes every setting: fill model, slippage, commission 0,
  sizing `equal_weight`, `max_positions`, rising edge, cooldown 10 on `signal`, no last bar
  entry, `same_ticker_overlap=false`, the config, the delisting rule, `oos_start`,
  `oos_fraction=0.3`, and the data mode, version and seed from `market.meta`.
- **AC-11**: 2 to 6 configs return 501 naming feature 12; an exit type feature 11 owns returns
  501 naming feature 11; no market loaded returns 501 (existing).

Report page (FE):
- **AC-12** [U-3]: the report opens with the assumptions header listing every AC-10 item in
  plain words; the labels live in one map, `features/backtest/assumption-labels.ts`, one entry
  per `Assumptions` field, and a null field reads "not used in portfolio mode".
- **AC-13**: metrics show IS and OOS columns side by side, never merged, with the benchmark's
  CAGR and max DD beside them; `null` reads "n/a".
- **AC-14**: the equity chart shows strategy and benchmark from 100, with the OOS start marked.
- **AC-15**: the trade list is sortable (TanStack Table), shows every `Trade` field with
  `format.ts` number formats, marks IS and OOS, and says "showing 2,000 of N" when truncated.
- **AC-16** [U-4]: `RunTrialCounter` sits beside the assumptions header once a 200 result is on
  screen (spec 0004).
- **AC-17** [U-6, U-7]: loading, warming up, 422 (on the right field), 501 and empty
  (`no_entries`) states all render; the page is keyboard usable, axe clean, and holds at 375 px.

## Decision

**Chosen option**: Option 1: a portfolio day loop and a per trade walker, both calling one
`step(position, bar)`.

Exits are small classes behind doc 02's `Exit` protocol; `step()` applies the §7.2 precedence
once; the day loop owns slots, sizing, cash and the equity curve; metrics are pure functions over
trades and the curve; `engine.api.backtest` orchestrates.

**Implementation skills**: `python-testing-patterns` (`wshobson/agents`,
`.claude/skills/python-testing-patterns/`) · `fastapi` (`fastapi/fastapi`,
`.agents/skills/fastapi/`) · `nextjs-app-router-patterns` (`wshobson/agents`,
`.claude/skills/nextjs-app-router-patterns/`) · `shadcn` (`shadcn-ui/ui`, `.agents/skills/shadcn/`)
· `vercel-react-best-practices` (`vercel-labs/agent-skills`,
`.claude/skills/vercel-react-best-practices/`)

## Rationale

Reasoning and options: see [rationale.md](rationale.md).

## Feature design

**Module layout** (engine domain modules from AGENTS.md):

| Module | Owns |
|---|---|
| `engine/exits/protocol.py` | `Exit` protocol (`kind`, `on_entry`, `level`, `at_close`), `Position`, `BarView`, `Fill` |
| `engine/exits/step.py` | `step(position, bar) -> Fill \| None`, the only place precedence lives |
| `engine/exits/stop_pct.py`, `time.py` | the two feature 9 exits; `build_exits(config)` maps `ExitConfig` to objects (501 for feature 11 types) |
| `engine/sim/walk.py` | `walk_trade(entry, exits, bars, horizon=None) -> TradeOutcome` (used by feature 12) |
| `engine/sim/portfolio.py` | `run_portfolio(signals, ranks, market, exits, sim) -> PortfolioRun` (day loop) |
| `engine/metrics/trades.py` | win rate, averages, expectancy (% and R), profit factor, bars, MAE/MFE |
| `engine/metrics/curve.py` | CAGR, max DD, Sharpe, exposure, thinning to 500 points |
| `engine/api.py` | `backtest()`: validate mode, cut the window, signals, run, split, assemble |

**Internal data model** (in memory only; no database):

| Type | Fields |
|---|---|
| `Position` | `ticker`, `entry_index` (session), `fill`, `shares`, `initial_stop: float \| None`, `bars_held` (entry bar = 1), `stop_levels: dict`, `pending_ma: bool`, `high_water`, `mae_low`, `mfe_high` |
| `BarView` | `open`, `high`, `low`, `close`, `b` (bar number in the trade), `is_delisting` (the bar's date is the ticker's `delisted_on`), `is_final` (the window's last session, or the ticker's last bar in the cut market), `horizon: int \| None` |
| `Fill` | `price` (before slippage), `reason: ExitReason`, `at: Literal["open", "intraday_stop", "intraday_target", "close"]` |
| `TradeOutcome` | `Fill`, exit index, `bars_held`, `mae_low`, `mfe_high` → becomes a contract `Trade` |
| `PortfolioRun` | trades, daily equity (one value per session), daily invested share, daily benchmark |

**`step(position, bar)`** (doc 02 §7.2, unchanged by feature 11):
1. pending MA → fill at open, `ma`;
2. stops: `L = max(levels)`; `open ≤ L` → open; else `low ≤ L` → L (reason = the exit whose level
   is L; ties go to `stop_pct`, then `stop_atr`, then `trail_pct`);
3. target: `open ≥ T` → open; else `high ≥ T` → T (only when step 2 did not fire);
4. time: `b == N` → close;
5. delisting: `is_delisting` → close, `delisted` (only a real `delisted_on`, never the end of a
   cut window); horizon (trade mode) → close, `horizon`;
6. `close_below_ma` → set `pending_ma` (exit at the next open);
7. finally `is_final` → close, `end_of_test` (portfolio and trade mode).
Then MAE and MFE update with the §7.2 exit bar cap, keyed on `Fill.at`. Every fill is
× (1 − slip) by the caller, never inside an exit.

**Portfolio day loop**, per session d in the window:
1. step every held position on bar d (ticker order A to Z); credit `shares × fill × (1 − slip)`;
2. take accepted signals at d − 1, skip held tickers, rank (`rs(126)` desc, nulls last, ticker
   asc), fill up to the free slots counted at close d − 1;
3. each entry: `fill = open(d) × (1 + slip)`, `notional = min(equity(d − 1) ÷ max_positions,
   cash)`, `shares = notional ÷ fill`, `on_entry` sets levels; then steps 2 to 7 on bar d;
4. mark to market at close(d): `equity = cash + Σ shares × close`.

**API surface** (no new endpoint; `POST /backtest` from spec 0002):

| Endpoint | Method | Key inputs | Key outputs | Errors |
|---|---|---|---|---|
| `/backtest` | POST | `rule`, `configs` (1), `sim` | `PortfolioResult` | 422 (contract), 501 (configs 2 to 6 → feature 12; feature 11 exit types; no market) |

**Value sourcing**:

| Action | Value | Source |
|---|---|---|
| entries | accepted signals | `engine.rules.entry_signals` (spec 0005), last bar term on |
| ranking | `rs(126)` at the signal bar | indicator cache (spec 0005 definition) |
| entry | fill | `open(d) × (1 + slippage_bps / 10,000)` |
| sizing | notional | equity at close d − 1 ÷ `sim.max_positions`, capped by cash |
| exits | levels and fills | the config's `Exit` objects through `step()` |
| R | initial stop | highest stop level after `on_entry` (`stop_pct`: `fill × (1 − pct/100)`) |
| `entry_price`, `exit_price` | prices | the slipped fills: `open × (1 + slip)` and `Fill.price × (1 − slip)` |
| `return_pct` | return | `(exit_price ÷ entry_price − 1) × 100` |
| `r_multiple` | R multiple | `(exit_price − entry_price) ÷ R`; null without a stop |
| `mae_pct`, `mfe_pct` | extremes | `(mae_low ÷ entry_price − 1) × 100`, `(mfe_high ÷ entry_price − 1) × 100`, where `mae_low` and `mfe_high` start at `entry_price` and then take the capped lows and highs, so `mae_pct ≤ 0 ≤ mfe_pct` always (contract bounds) |
| `mae_r`, `mfe_r` | extremes in R | `(mae_low − entry_price) ÷ R`, `(mfe_high − entry_price) ÷ R`; null without a stop |
| `bars_held` | count | entry bar = 1; the exit bar counts (a pending MA exit at open(b) has `bars_held = b`) |
| `exit_date` | date | the date of the bar the fill happens on |
| segment | `is` or `oos` | `oos` when `entry_date ≥ oos_start`, else `is` |
| calendar | sessions | the benchmark's session dates inside [`sim.start`, `sim.end`] (the window) |
| `oos_start` | date | window session at index `floor(0.7 × n)`, n = window sessions |
| curve metrics | CAGR, max DD, Sharpe, exposure | daily equity of that segment (formulas below) |
| benchmark | curve and metrics | `market.meta.benchmark` closes, rescaled to 100 |
| `trial` | keys | `engine.contracts.trial.structure_key(rule)`, `pair_key(rule, config)` |
| `assumptions.data_*` | mode, version, seed | `market.meta` |

**Precise rules the build must not invent**:
- No rounding anywhere in the engine; values go out as float64 (the oracles check to 1e-9).
- "Held" for the skip rule means held at close d − 1, the same snapshot as the free slots.
- Signals that find no free slot are dropped, never queued to a later day.
- An entry is skipped when its notional would be 0 or less (no cash left).
- Same bar reasons follow `step()`'s order: a stop beats a target beats time beats delisting
  beats `end_of_test`. Among stops at the same level, `stop_pct`, then `stop_atr`, then
  `trail_pct` (a choice made here; doc 02 does not rank equal levels).
- Delisting means the bar's date equals the ticker's `delisted_on`. The fixture loader
  (`engine.data.fixtures`) sets `delisted_on` to a ticker's last bar when it stops before the
  data does, so B-8 and B-15 read the same way.
- Trades are listed by entry date, then ticker A to Z. Truncation keeps the last 2,000 of that
  order. Metrics always use every trade, never the truncated list.
- Warnings, in this order: `no_entries` when the run made zero trades (`config_index` 0,
  message "No entries: the rule never produced a signal that could be filled in this window."),
  then `trades_truncated` (`config_index` null, message "Showing the latest 2,000 of N trades;
  metrics use all of them.").
- Thinning: indexes 0, k, 2k, … plus the last index, deduplicated; equity and benchmark use the
  same dates. A session missing from the benchmark series carries the previous close forward.
- Assumptions in portfolio mode: `sizing="equal_weight"`, `horizon_bars=null`, `seed=null`,
  `same_ticker_overlap=false`, `baseline_config_index=0`, `commission_bps=0`,
  `data_seed=market.meta.seed` (null in live mode). The report shows null ones as "not used in
  portfolio mode".

**Metric formulas** (per segment; `n` = trades, returns in %):

| Metric | Formula | Null when |
|---|---|---|
| `win_rate_pct` | trades with `return_pct > 0` ÷ n × 100 | n = 0 |
| `avg_win_pct`, `avg_loss_pct` | mean `return_pct` of wins, of losses (≤ 0) | no wins, no losses |
| `expectancy_pct` | mean `return_pct` | n = 0 |
| `expectancy_r` | mean `r_multiple` | no stop in the config, or n = 0 |
| `profit_factor` | Σ wins ÷ abs(Σ losses) | n = 0, or abs(Σ losses) = 0 |
| `avg_bars_held` | mean `bars_held` | n = 0 |
| `cagr_pct` | `((E_end ÷ E_start)^(252 ÷ s) − 1) × 100`, s = sessions in the segment; E_start = the close before the segment's first session (100 for IS) | s < 2 |
| `max_dd_pct` | `min(E ÷ running max(E) − 1) × 100` over the segment's closes, the running max carrying the IS peak into OOS (≤ 0) | s < 2 |
| `sharpe` | `mean(r) ÷ std(r, ddof=1) × sqrt(252)`, r = daily equity returns, the first one against E_start | fewer than 2 returns or std = 0 |
| `exposure_pct` | mean over the segment's closes of `Σ positions value ÷ equity × 100` | s = 0 |

**Key invariants**:
- Exit precedence exists only in `step()`; no exit is special cased anywhere else (AGENTS.md).
- Nothing after `sim.end` is read; indicators are computed on the cut market.
- Portfolio mode has no randomness; `sim.seed` is ignored and `assumptions.seed` is null.
- Cash never goes below 0; at most `max_positions` positions; one position per ticker.
- `engine` imports no web framework; `services/api` stays a thin route.

**Security model**: no auth, no secrets; inputs are the validated contract. The 6 MB response
cap is enforced by the 500 point and 2,000 trade limits.

**Configuration required**: none new.

**Critical test scenarios**:
- Oracles that gate feature 9: B-1, B-2, B-7, B-8 and the portfolio tests in B-14, B-15 and
  B-16, verifies **AC-1** to **AC-3**, **AC-8**
- Oracles that turn green later: B-3 to B-6, B-9 and B-10's portfolio test with feature 11; the
  parity test, B-10's trade mode test and the trade mode halves of B-15, B-16 and X-9 with
  feature 12. They do not gate this feature's merge.
- Feature 9 unit tests standing in until then: MAE and MFE (both caps, both signs, R) on a
  `stop_pct` plus `time` fixture; look ahead on the B-10 random walk with `stop_pct` and `time`
  only; B-11's 15 signals into 10 slots, verifies **AC-4**, **AC-5**, **AC-6**
- Unit: `step()` precedence table, one case per row, and the stop beating the target on one bar, verifies **AC-1**, **AC-4**
- Unit: cash cap when equity ÷ slots exceeds cash; a slot freed today is not reused today, verifies **AC-6**
- Unit: each metric's formula and its null case; thinning keeps the last point, verifies **AC-9**
- Run twice on seed 42, equal; timing and size under budget, verifies **AC-7**
- API: 2 configs and a `trail_pct` config return 501 with the right feature, verifies **AC-11**
- Web: every state against the mocks, the 375 px and axe checks, verifies **AC-12** to **AC-17**

## Build plan

Tracer Bullet: one thin thread through engine, API and page first, then thicken. BE and FE run
in parallel; FE uses `contracts/mocks/backtest.portfolio*.json` and `backtest.no_entries.json`
until the API is real.

**BE lane (engine, `services/api`)**
1. Thread: `Exit` protocol, `step()`, `stop_pct`, `time`, delisting and `end_of_test`;
   `walk_trade()`; the day loop on fixtures; `engine.api.backtest` returning a minimal valid
   `PortfolioResult`; the route's 501 gate removed for 1 config. Satisfies **AC-1** to **AC-3**,
   **AC-8**, **AC-11**
2. Portfolio rules: ranking, slots, sizing, cash cap, held ticker skip, window cut and
   `oos_start`. Satisfies **AC-5**, **AC-6**
3. Metrics and response: trade and curve metrics with nulls, benchmark, thinning, truncation,
   warnings, `trial`, `assumptions`. Satisfies **AC-4**, **AC-9**, **AC-10**
4. Budget: seed 42 determinism, the 3 s and 6 MB test. If it misses, profile first; the
   fallback is ADR-016's order (vectorize the hot loop), and a miss is reported to the owner,
   never hidden. Satisfies **AC-7**

**FE lane (report page)**
5. Thread: `/backtest` page with the exit form (`stop_pct`, `time`) and sim fields, submit,
   the assumptions header and metrics table from the mock. Satisfies **AC-12**, **AC-13**
6. Chart, trade list, trial counter, and every state; `/ui` gallery entries; switch to the real
   API when BE task 1 merges. Satisfies **AC-14** to **AC-17**

## Consequences

**Positive**:
- One `step()` means features 11 and 12 add exits and a loop without touching precedence, and
  the parity oracle holds by construction.
- The day loop is plain Python over about 1,260 sessions and at most 20 positions: fast enough,
  easy to read against the oracles.
- Every number in the report traces to a formula in this spec.

**Negative / tradeoffs**:
- Until feature 11, a config with `stop_atr`, `target`, `trail_pct` or `close_below_ma` returns
  501, and oracles B-9 and B-10 (portfolio half) stay red.
- A slot freed by an exit today waits until tomorrow; slightly lower exposure than a same day
  reuse, chosen because it needs no intraday ordering assumption.
- Sizing at the previous close means an entry can be a little over or under 1/N of today's
  equity after the open gap, and the cash cap can make it smaller than 1/N when no exit freed
  cash; the assumptions header says sizing is "equity ÷ max positions at the signal close,
  capped by cash".
- Metrics use sessions, not calendar days, for CAGR (252 a year); fine on the weekday only
  synthetic calendar, slightly off on live data with holidays.

**Neutral**:
- `engine.api.FEATURE_NAMES` gains 11 and 12 so the 501 messages name the right feature.

## Follow-up

- [x] Owner sign-off on the twelve assumed decisions above.
- [ ] Feature 11 adds the four remaining `Exit` classes against this spec's `step()`; B-9 and
  B-10 (portfolio) turn green there.
- [ ] Feature 12 builds the trade mode loop on `walk_trade()` and makes the parity oracle green.
- [ ] Feature 10 replaces `?template=` with `?r=` on the report page.
- [ ] Feature 15 measures the cold start with a backtest after the scan warm up.
