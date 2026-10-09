# Review, review/9-backtest-engine, 2026-10-09

**Reviewed by**: claude-opus-5-5, a fresh reviewer that did not write this code (GA tier review of feature 9's engine)
**Scope**: the portfolio path on `origin/main` at 6ce1e13: `engine/src/engine/sim/{portfolio,walk,bars}.py`, `engine/src/engine/metrics/{curve,trades}.py`, the `_window`, `_portfolio`, `_split_curve`, `_warnings` path in `engine/src/engine/api.py`, and `services/api/src/api/routes/backtest.py`. Exit classes, the exit lab, trade mode and the random baseline belong to another reviewer and are out of scope here.
**Verdict**: Changes requested

## Summary

The portfolio day loop is small, readable and matches spec 0007 almost line by line: ranking, free slots, sizing, the window cut, `oos_start`, the IS and OOS curve split, the metric formulas and their null cases, thinning, truncation, warnings, `trial` and `assumptions` all check out, and the seed 42 budget is met with a wide margin (about 0.1 s and 0.23 MB warm). Two findings are worth fixing before you call feature 9 done. First, cash from exits that fill later in the session (at the close, or intraday) already funds that same session's entries at the open, which is a small but systematic look ahead in sizing. Second, the loop assumes every ticker has a bar on every window session and nothing checks that; a single missing bar shifts a position one session into the future. The second one is latent today (seed 42 has no gaps) but it would turn on silently with live data.

I reproduced both with small scripts against `engine.api.backtest` (numbers below). The engine, metrics and oracle suites pass (116 tests).

## Major

### 🟠 Cash from a close or intraday exit funds the same morning's entries, `engine/src/engine/sim/portfolio.py:81-93`

**Problem**: On session d the loop steps every held position first (lines 81 to 87) and `close()` credits the proceeds to `cash` right away (line 74), whatever `Fill.at` was. Then the entries fill at open(d) with `notional = min(equity / max_positions, cash)` (line 93). A `time` or `end_of_test` exit fills at close(d), and a stop fills intraday, both later in real time than the open. So the cash cap at the open reads money that only exists after the close, and the size of that money depends on close(d), a price not known at the open. The same thing happens inside the entry loop: if entry 1 stops out intraday on its own entry bar (line 104), entry 2 at the same open is funded by that stop's proceeds.

**Failure scenario** (reproduced): two slots, AAA bought for 50 and tripled, BBB signals the day before AAA's `time` exit. With `time` 50, BBB is cash capped at 50 (equity at BBB's entry close is 199.80). With `time` 4, AAA exits at close(d) on BBB's entry day, its 150 lands in cash before BBB fills at open(d), and BBB gets about 100 (equity 199.60, the extra 0.05 slippage is the bigger BBB position). Same signals, same prices, and the open fill's size depends on whether a position exits at that day's close.

**Why it matters**: The cash cap binds exactly when the book is nearly full and winning, which is when this inflates exposure. The effect per trade is small, but it is always in the optimistic direction, and the project's whole pitch is "no look ahead". It also contradicts the spec's own reasoning for slots: "A slot freed by an exit today waits until tomorrow ... chosen because it needs no intraday ordering assumption." Cash freed today is used today, so the intraday ordering assumption came back in through the cash.

**Suggested fix**: Snapshot cash for the entry step as the cash at close d − 1 plus only the proceeds of fills with `at == "open"` on session d (a gap stop or a pending MA exit, which really happen at the open), and credit close and intraday proceeds after the entry loop. Apply the same rule to entries that exit on their own bar. Since spec 0007 decision 4 only says "capped by the cash on hand", this needs a one line owner call recorded in the spec, plus a unit test that pins it (the scenario above is a ready fixture: `test_the_cash_cap_sizes_an_entry_below_equity_over_slots` with `time` 4).

### 🟠 The loop assumes no missing bars, and nothing enforces it, `engine/src/engine/sim/portfolio.py:83`, `:96`, `:85`

**Problem**: A held position advances with `row += 1` once per window session (line 83), an entry fills at `signal_row + 1` (line 96), and the bar number is `row - entry_row + 1` (line 85). All three assume a ticker's rows line up one to one with the benchmark's sessions between its first and last bar. `validate_market` (`engine/src/engine/contracts/market.py:92`) checks sort order and duplicate keys, and `bar_problems` (`engine/src/engine/data/sanity.py:17`) checks prices and listing dates, but neither checks that a ticker has a bar on every session it is alive, or that it has no bar on a non session.

**Failure scenario** (reproduced): AAA enters on 2020-01-07; drop its 2020-01-09 bar (the market still passes `validate_market`). On session 2020-01-09 the loop reads AAA's next row, which is 2020-01-10, so equity on 01-09 is marked at the 01-10 close (124.93 instead of about 108). Every later session is one day early, and on 2020-01-14 the position reaches its last row (2020-01-15, `is_last`) and exits `end_of_test` with `exit_date` 2020-01-15, while the curve already books that price on 01-14. `bars_held` is 6 for a 7 session hold. A signal row whose next row skips a session also fills at an open dated after `entry_date`'s session. The same shift, in the other direction, happens if a ticker has a bar on a date the benchmark lacks.

**Why it matters**: Seed 42 has zero gaps (I checked all 501 tickers), so nothing is wrong in the deployed demo today. But live mode is in the contract (`data_mode`), vendor data has halts and missing days, and the failure is silent look ahead with no error, the exact thing B-10 exists to rule out. The B-10 oracle uses gap free random walks, so it would not catch it.

**Suggested fix**: Make the invariant explicit where it is cheapest: add a D-2 check in `bar_problems` that every ticker has exactly the benchmark's sessions between its first and last bar (and none outside them), so a bad market fails at load. Optionally also assert `bars.date[row] == sessions[i]` in the loop in debug, or handle a missing bar by skipping the step and carrying the last mark. Add a unit test with a dropped bar either way.

## Minor

### 🟡 Any Pydantic error, including a response bug, becomes a 422 on the request, `services/api/src/api/routes/backtest.py:29-34`

**Problem**: The route catches every `pydantic.ValidationError` from `use_cases.backtest` and turns it into a 422 with `loc` prefixed by `body`. It is meant for `range_outside_data`, but building `Trade`, `PortfolioMetrics` or `PortfolioResult` also raises `ValidationError` when an engine invariant breaks (a contract bound, the `oos_start` match rule in `test_response_rules.py`).

**Why it matters**: A real engine bug would reach the user as "your request is invalid" pointing at a field that does not exist in the request, and would not show up as a 500 in logs. The module docstring of `engine/api.py` promises the opposite for `NotImplementedError`.

**Suggested fix**: Raise a dedicated exception (or filter on the `range_outside_data` error type) and let any other `ValidationError` stay a 500.

### 🟡 `start` after `end` gives a misleading 422, `engine/src/engine/api.py:265-267`

**Problem**: When both dates are inside the data but `start > end`, the window is empty and the code raises `range_outside_data` on `start` with "start must be between <first> and <last>", although `start` already is.

**Suggested fix**: A distinct message (for example "start must be on or before end") or error type for the empty window case, so the form can show it on the right field (AC-17 asks for 422s "on the right field").

### 🟡 Test gaps on the portfolio wiring, `engine/tests/sim/test_portfolio_rules.py`

- `_split_curve` (`api.py:302`) is tested only through `curve_stats` unit tests; the one engine test of the split uses a flat benchmark and a single IS trade, so nothing proves through `backtest()` that OOS starts from the last IS close and carries the IS peak (a swapped argument would still pass).
- Truncation is tested only through `_warnings(2600)`; no engine test checks `trades[-2000:]` keeps the latest by (entry date, ticker), with `trades_total` and `trades_truncated` set (`services/api/tests/test_contract_artifacts.py` checks the mocks, not the engine).
- Nothing pins the cash timing or the missing bar behavior above.

### 🟡 A ticker whose bars just stop exits as `end_of_test` mid window, `engine/src/engine/sim/bars.py:63`

`is_final` folds in `is_last`, so a ticker whose data ends early without a `delisted_on` exits `end_of_test` in the middle of the window, at a date that is not the test's end. Spec 0007 relies on the fixture loader setting `delisted_on`; the same must hold for any future live loader. Worth a line in `engine/AGENTS.md` gotchas, or folding into the D-2 check from the second major.

## Nits

- ⚪ `engine/src/engine/metrics/curve.py:59-60`, `thin()` drops the step point before the last when adding the last makes 501 points. That is the right call for the contract's 500 cap, but it differs from the spec's literal "every k th plus always the last"; note it in spec 0007 so the FE and QA read the same rule.
- ⚪ `engine/src/engine/sim/walk.py:57`, `if risk` treats a zero risk like no stop (R null). Fine, but the spec's null rule says "no stop in the config"; a comment would stop someone "fixing" it into a division by zero.
- ⚪ `engine/src/engine/sim/portfolio.py:92`, `max(free, 0)` can never matter (`held` never exceeds `max_positions`); harmless.

## Checked and fine

- **Day order**: held positions step A to Z, then entries from session i − 1 signals, then the entry bar's own `step()` with `b = 1`, then the mark at close. Matches spec 0007 decision 3 and the loop text.
- **Ranking**: `rs(126)` read at the signal row, descending, NaN (null) last, then ticker A to Z; one signal per ticker per day, so no ties left. Held skip and free slots both use the close d − 1 snapshot (`held_before`); a slot freed today is not reused today.
- **Sizing**: `equity` is the previous close's value, capped by cash, skip when notional ≤ 0; cash never goes below 0; fractional shares. Entry fill `open × (1 + slip)`, exit `Fill.price × (1 − slip)`, slippage applied by the caller only.
- **Window cut**: `sim.end` cuts `market.bars` before any cache, signal or `is_last` is computed, so no last bar entry and cooldown read the cut market (B-10 holds by construction; the poisoned future test passes). A cut market gets its own cache, which is cheap (about 0.12 s with `end` one session before the last). `sim.start` only filters sessions; indicators and the cooldown chain still warm up on earlier bars, so the backtest and the scan see the same signals.
- **`oos_start`**: `floor((1 − 0.3) × n)`; I checked `1 − 0.3` gives the same floor as `0.7` for every n up to 5,000. Trades split on `entry_date ≥ oos_start`, where `entry_date` is the fill session.
- **Delisting and end of test**: `is_delisting` only for a real `delisted_on`, so a ticker alive past a cut `end` exits `end_of_test`, not `delisted`. Every open position exits on the last session.
- **Curve metrics**: CAGR with s sessions and E_start = 100 for IS and the last IS close for OOS; max DD with `max(100, *IS)` carried into OOS; Sharpe from `statistics.stdev` (ddof = 1) with the first return against E_start, null when std is 0 or fewer than 2 sessions; exposure as the mean invested share, null with no sessions. The benchmark is rescaled to 100 on the first window session, and the strategy curve is also exactly 100 there (no entry can fill on session 0), so the two line up.
- **Trade metrics**: wins `> 0`, losses `≤ 0`, profit factor null when n = 0 or the loss sum is 0, `expectancy_r` null when any trade lacks R.
- **Output**: trades sorted by (entry date, ticker), last 2,000 kept, metrics on all trades; warnings `no_entries` (config 0) then `trades_truncated` (config null) with the spec's messages; `trial` from `structure_key` and `pair_key`; `assumptions` carries every AC-10 item with the portfolio mode nulls.
- **Determinism and budget**: no randomness on this path; positions step in sorted order and dict order is insertion order, so float sums are reproducible. Seed 42 warm runs take about 0.08 to 0.12 s with a 0.23 MB body, far under 3 s and 6 MB, and the B-13 acceptance tests measure both templates.
- **Boundaries**: `engine` imports no web framework; the route is thin.

## Strengths

- One `step()` really is the only place precedence lives; the portfolio loop and `walk_trade()` both call it and share `make_trade()`, so the parity oracle holds by construction.
- The loop is about 60 lines and reads directly against the spec's four steps, which makes look ahead easy to audit.
- Metric functions are pure, unrounded, and their null cases follow the spec table one for one, each with a unit test.

## Test coverage

The engine has good unit coverage of the formulas, nulls, thinning, ranking, B-11, the cash cap, the start filter and the poisoned future (B-10 stand in), and the acceptance suite covers B-13's determinism and budget. Missing: an end to end check of the IS to OOS curve hand off, engine level truncation, the cash timing rule, and a market with a missing bar (see the Minor test gaps finding).
