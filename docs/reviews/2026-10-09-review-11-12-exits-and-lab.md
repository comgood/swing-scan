# Review, review/11-12-exits-and-lab, 2026-10-09

**Reviewed by**: claude-opus-5-5, as the GA tier's fresh reviewer (it wrote none of this code; the builder lanes may also run on Opus, so for a fully independent second opinion you may want to rerun on another model)
**Scope**: feature 11 (exit types) and feature 12's engine (exit lab) as merged on `origin/main` at `41f27d0`: `engine/src/engine/exits/`, `engine/src/engine/sim/{walk,trade_mode,portfolio,bars}.py`, `engine/src/engine/metrics/{trade_mode,trades}.py`, `engine/src/engine/baseline/random_entries.py`, `_trade_lab` in `engine/src/engine/api.py`, `services/api/src/api/routes/backtest.py`, against spec 0007, spec 0009, spec 0002 and doc 01 (B-3 to B-6, B-9, B-10, B-15, B-16, X-1 to X-10)
**Verdict**: Changes requested

## Summary

The exit work is clean and mostly right. All six exits sit behind one `step()`, the precedence matches spec 0007 line for line, fills and slippage match B-1 to B-7, and the random baseline follows spec 0009's pool and draw exactly. The engine, oracle and unit tests pass (123 tests in `engine/tests/{sim,baseline,metrics}` and `tests/oracle`).

Two things should change before you call the exit lab done. First, a `stop_atr` config loses its R numbers whenever even one trade starts before ATR has warmed up. The random baseline hits this on almost every run, so on the seed 42 market the demo's "ATR stop and target" config shows a null "edge in R" for both templates (I ran it; numbers below). Second, the MAE guide percentiles follow the contract to the letter, but the contract points them the wrong way for a stop guide. That one is a spec question for the owner, not a coding slip.

## Major

### 1. A `stop_atr` config loses `expectancy_r` (and the R edge) when any trade has no ATR at its signal bar, `engine/src/engine/exits/stop_atr.py:21-24`, `engine/src/engine/metrics/trades.py:45-49`

**Problem**: `StopAtrExit.on_entry` sets no stop level when ATR is NaN at the signal bar (`stop_atr.py:23`). For a config whose only stop is `stop_atr`, that trade has `initial_stop = None`, so `make_trade` gives it a null `r_multiple`, `mae_r` and `mfe_r` (`sim/walk.py:54-57`). Then `trade_stats` makes the whole segment's `expectancy_r` null as soon as one trade has no R (`trades.py:47`: `None not in r_multiples`). Spec 0002 line 195 says R metrics are null only when the config has no stop; this config has one.

**Failure scenario** (reproduced): seed 42 market, the five configs from `contracts/mocks/backtest.trade_lab.json`, default `sim`. Random entries skip warm up by design (spec 0009 decision 3), so a sample of 1,380 or 12,378 random IS entries almost surely contains a ticker's first 14 bars.

| Template | Config | strategy IS `expectancy_r` | random IS `expectancy_r` | `edge.is.expectancy_r` | `edge.oos.expectancy_r` |
|---|---|---|---|---|---|
| breakout_52w | ATR stop and target | 0.00922 | null | null | -0.01351 |
| pullback_ema21 | ATR stop and target | 0.00194 | null | null | null |

The other stop configs ("Baseline", "Trailing 10%") get real R edges, so the table looks like this config simply has no R, which is false. A custom rule that can fire in a ticker's first bars (say `close > 10`) breaks the strategy side the same way.

**Why it matters**: X-10 and AC-8 promise an edge in R for every config with a stop. The demo's default lab shows a silent "n/a" on one of its headline rows, and AC-14's footnote ("R needs a stop") would then explain it wrongly.

**Suggested fix**: pick one rule and write it into spec 0007 (spec 0009's follow-up "Feature 11 decides how `stop_atr` handles a null ATR" is still unticked). Options, roughly in order of simplicity: (a) compute `expectancy_r` over the trades that do have R when the config has a stop, and keep it null only for a stopless config; (b) give a null ATR trade a fallback stop so every trade has R; (c) leave such entries out of the random pool for ATR configs (this one breaks "the pool never looks at an exit type", so I would avoid it). Add a unit test with a `stop_atr` config walking one warm and one cold entry.

### 2. The MAE guide percentiles point the wrong way for a stop guide (spec issue), `engine/src/engine/metrics/trade_mode.py:110-115`

**Problem**: `guides_is` takes `np.percentile(mae_pct, 75)` and `(…, 90)` over winners, with `mae_pct` signed (always 0 or below). The 90th percentile of a negative number is the one closest to 0, so p90 comes out shallower than p75. On seed 42 (breakout_52w) you get p75 = -1.69% and p90 = -0.85%; the mock has the same shape (-2.54 and -1.70). Doc 01 §6.5 (line 367) calls these "the 75th/90th percentile MAE of winners (stop guide)". As a stop guide the reader expects "90% of winners never dipped deeper than X", which is the 10th percentile of signed `mae_pct` (or the 90th of its size). As built, a stop at "p90" would stop out about 90% of the winners.

**Why it matters**: the guide row exists to steer the stop choice on IS data. Read the usual way, it steers to a stop far too tight.

**Suggested fix**: this is not a code bug. The code matches spec 0002 line 198 and the frozen mock exactly. You may want to raise it with the owner through /architect: either define the guides as percentiles of `-mae_pct` (or the 25th and 10th of signed `mae_pct`) and update spec 0002, the mock and the X-5 unit test in one `contract-change` PR, or keep the math and relabel the FE row so it says what the number means.

## Minor

### 3. The null ATR rule is decided only in a code comment, `engine/src/engine/exits/stop_atr.py:23`

The choice "no ATR at the signal bar means this trade has no ATR stop" changes results (those trades run with no stop at all, only target, time or horizon), but it lives in an inline comment. Spec 0007 does not record it, spec 0009's follow-up box is open, and `assumptions` does not disclose it. Whatever you decide in finding 1, you may want to record it in spec 0007's "precise rules" list and tick the box.

### 4. The portfolio loop assumes every held ticker has a bar on every session, `engine/src/engine/sim/portfolio.py:81-85` and `:96`

Held positions advance one row per session (`row += 1`) and entries use `signal_row + 1`, without checking that the row's date is the session date. Nothing in `check_market` or `validate_market` forbids a gap inside a ticker's history. On the synthetic weekday calendar this holds, but a live data halt (a missing day) would step the position on its next real bar while the portfolio marks session d, so the position reads a bar dated after d: a look ahead relative to the portfolio's own calendar, and a wrong `exit_date`. This is feature 9 code that features 11 and 12 now lean on. Either assert `bars.date[row] == sessions[i]` (and hold the position for that session when it does not match) or add a "no gaps inside a ticker" check to the D-2 sanity rules. Trade mode is not affected: it walks rows, and a missing day only shifts bar counts.

### 5. Every request with `sim.end` before the last session recomputes every indicator, `engine/src/engine/api.py:241-247`, `:263`, `:486`

`_cut` builds a new `Market`, and `cache_for` keys on object identity, so each windowed request gets a fresh, cold `IndicatorCache` (ATR, the MAs, `rs(126)` and the rule's columns). That is correct (it is what makes B-10 hold), but X-7's "warm under 10 s" is only true without `sim.end`. Worth a line in spec 0009's budget section, or a small per end date cache if a windowed lab turns out slow. For reference, a first call of the five mock configs on pullback_ema21 (18,566 entries, above the 5k to 15k spec 0009 expected) took 7.0 s locally; the budget lane owns the real X-7 number.

### 6. Test gaps

- No test walks a `stop_atr` config over a mix of warm and cold entries and checks the segment's `expectancy_r` (finding 1). `test_stop_atr_without_an_atr_at_the_signal_bar_sets_no_stop` stops at the level.
- No test pins the guide direction (p90 deeper or shallower than p75); the X-5 test checks only IS versus OOS (finding 2).
- No test runs the portfolio loop on a ticker with a missing session (finding 4).

## Nits

- `engine/src/engine/exits/protocol.py:65` and `trail_pct.py:25`: the trail's high water mark starts at the slipped fill (`open × (1 + slip)`), a price that never traded. On an entry bar whose high is below the fill, the next bar's trail sits a little higher than the B-5 rule ("highest high since entry") gives. Tiny (10 bps of the level), and the B-5 oracle passes; mention it in spec 0007 or seed from the open if you prefer.
- `engine/src/engine/exits/step.py:64-72`: `_target` returns the first target in config order. Fine today because `duplicate_exit_type` rejects two targets; a one line comment saying so would help the next reader.

## What is fine (checked, no change needed)

- **One `step()`**: precedence lives only in `exits/step.py`. A grep of `sim/`, `baseline/`, `metrics/` and `api.py` finds no exit type names, `kind ==`, `pending_ma` or `high_water`. Exits only report levels and conditions.
- **No `eval` or `exec`** anywhere in `engine/src` or `services/api/src`.
- **Seed default** stays 42 (`contracts/backtest.py:28`); `assumptions.seed` echoes `sim.seed`; the draw uses one `default_rng(seed)`, IS first, then OOS, from pools sorted by (entry date, ticker), with replacement only when a non empty pool is smaller than its count, and nothing drawn from an empty pool (`random_entries.py:59-72`).
- **Fills and slippage**: stops fill at `min(open, L)`, targets at `max(open, T)`, time, delisting, horizon and end of test at the close, MA at the next open; slippage is applied once in `make_trade` and in the portfolio's cash credit, never inside an exit (B-1 to B-8).
- **Stop before target**: `_decide` runs `_stop` before `_target`, so a bar that touches both exits at the stop (B-4). Equal stop levels break ties `stop_pct`, `stop_atr`, `trail_pct`.
- **Gaps**: a gap through a stop or a target fills at the open; MAE and MFE on a gap bar take only the open; intraday stop and target bars are capped at the level (B-9).
- **Look ahead**: `stop_atr` reads ATR at the signal bar, `close_below_ma` reads the MA on the bar whose close it tests and fills at the next open, the trail reads the high water through b − 1, and the market is cut at `sim.end` before indicators, the random pool and the walker run (B-10 portfolio and trade mode oracles pass, random baseline included).
- **Horizon**: `b == horizon` closes at the close with reason `horizon`, after time and delisting and before the MA check and end of test, as spec 0007 step 5 says (X-9 oracle passes).
- **IS and OOS**: both strategy and random trades take the segment of their entry date; the pool splits on the entry date (t + 1), so a signal on the last IS session lands in OOS for both sides. `oos_start` is `floor(0.7 × n)`.
- **Random pool**: non benchmark, not a ticker's last bar of the cut market, signal date from the window start (X-10).
- **Edge**: strategy minus random, null when either side is null.
- **`best_is`**: directions match spec 0002 line 197 (including `avg_loss_pct` and `avg_mae_pct` higher is better, `horizon_exit_pct` lower is better), nulls are skipped, ties go to the lowest index, and only IS strategy metrics are passed in.
- **Warnings, `baseline_trades` and `entries`**: order, messages, `config_index` and the even spread (exact integer round half up) match spec 0009.
- **Route**: `services/api/src/api/routes/backtest.py` stays thin; 1 config goes to portfolio, 2 to 6 to the lab, `range_outside_data` maps to a 422 under `body`.

## Test coverage

Strong for the happy paths and the precedence table: every exit type has a unit test, the oracles (`test_exits`, `test_mae_mfe`, `test_horizon`, `test_look_ahead`, `test_loop_parity`, `test_entry_signals`) are green, and the baseline tests cover seeding, replacement, empty pools and zero counts. The gaps are the three listed in finding 6, and the first one hides a real bug.
