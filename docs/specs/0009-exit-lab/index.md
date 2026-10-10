# 0009. Build the exit lab as a per trade loop over spec 0007's `walk_trade()` and one `step()`

**Date**: 2026-10-08
**Status**: In Progress (owner signed off 2026-10-08)
**Authorized by**: /architect, run unattended overnight by the orchestrator lane; every open
question took /architect's recommended answer (listed below) and waits for the owner

## Summary

This spec designs scope feature 12, the exit lab: you hold one entry rule fixed and compare 2 to 6
exit setups on exactly the same entries, trade by trade, next to a seeded random entry baseline
that goes through the same exits. The engine computes the entry list once, walks every trade with
spec 0007's `walk_trade()` (which calls the single exit `step()`), and returns per trade metrics
only, in IS and OOS columns, with the best IS value marked and MAE and MFE guides from IS trades
only. The engine part (BE lane) starts once feature 9's simulator is on `main` (gate G2, open PR
#31); the exit lab table (FE lane) starts now against `contracts/mocks/backtest.trade_lab.json`.
The contract (`TradeLabResult`, spec 0002) is already frozen, so no contract change is needed.

## Assumed decisions (signed off by the owner, 2026-10-08)

The owner could not answer during this run. Each question took /architect's recommended answer;
the runner up is in [rationale.md](rationale.md).

1. **One loop, no new exit code.** Trade mode calls `walk_trade(entry_row, entry_fill, exits,
   bars, ctx, horizon=sim.horizon_bars)` once per (entry, config), then `make_trade(position, fill,
   entry_date, exit_date, slip, oos_start)`. Those two signatures and `EntryContext` (`ctx`) are
   the ones in PR #31, which is authoritative where spec 0007's shorter sketch differs. The
   horizon lives in `step()` (spec 0007 step 5). Nothing in `engine/sim/trade_mode.py` or
   `engine/baseline/` looks at an exit type.
2. **Never serve half a lab.** The trade mode loop (BE 1) lands in the engine with unit tests while
   `/backtest` still answers 2 to 6 configs with 501 (feature 12). The 501 goes away only in BE 2,
   when the random baseline and the edge columns are real, so `main` never serves random rows
   filled with placeholders.
3. **Random baseline sampling.** The pool is every non benchmark (ticker, signal session t) on
   the cut market with t from `sim.start` on (the same signal date range as the strategy), where
   the ticker has a bar at t and at t + 1 (so t is never its last bar). The pool does not depend
   on the configs and applies no indicator warm up filter, so it never looks at an exit type; a
   null indicator at entry (ATR in a ticker's first bars) is handled inside the exit by feature
   11's `on_entry`, the same way for strategy and random entries. The entry is at open(t + 1)
   like a real signal; the segment is the entry date's. The IS pool and the OOS pool are each
   sorted by (entry date, ticker); one `rng = numpy.random.default_rng(sim.seed)` draws
   `rng.choice(len(pool_is), size=is_count, replace=False)` first, then the same for OOS.
   `replace=True` only when a non empty pool is smaller than its count; an empty pool draws 0
   entries. No cooldown and no rule apply to random entries.
4. **Seed.** `sim.seed`, default 42 from the frozen contract. The default never changes without an
   ADR (AGENTS.md); `assumptions.seed` echoes it.
5. **Horizon warning scope.** `horizon_exits_over_10pct` fires per config when more than 10% of
   that config's strategy trades, IS and OOS together, exit by `horizon`. Random trades never
   trigger it. This refines spec 0002's "whose `horizon_exit_pct` is over 10", which is a per
   segment field and did not say which segment.
6. **`baseline_trades`** are `configs[0]`'s strategy trades (not the random ones), both segments,
   as the parity oracle reads it. Over 2,000 they are spread evenly per spec 0002.
7. **No entry cap (a deviation from doc 02 §8).** Doc 02 §8 mentions a 25k cap with a warning,
   but the frozen `WarningCode` has no code for it. This feature ships without a cap: above 25k
   entries a run is simply slower and may miss X-7 (the synthetic templates give 5k to 15k). If
   X-7 or a real rule shows a need, a `contract-change` PR adds an optional warning code
   (additive, `1.x`). Doc 02 §8 is synced once the owner signs this off.
8. **Table layout.** One row per config with every metric as an IS | OOS column pair, plus an
   "Edge vs random" column group per row. A single "Random entries" row at the bottom shows
   `configs[0]`'s random metrics (doc 01 §6.5); each config row has a disclosure that shows its
   own random metrics, so every edge number can be traced.
9. **Placement.** The exit lab renders on feature 9's `/backtest` page when the response `mode`
   is `trade`; its components live in `apps/web/src/features/exit-lab/`. `ProcedureNote` sits
   directly under the table, then the guide row, then the footnotes (spec 0004).
   `RunTrialCounter` sits beside the assumptions header.
10. **Default configs.** The exit form opens the lab with the five configs of
    `backtest.trade_lab.json` (the demo script's "5 default configs"), held in
    `features/exit-lab/default-configs.ts`. Four of them use feature 11 exits, so they run on the
    real API only once feature 11 is on `main`; until then the lab stays on the mocks (FE 5
    switches to the real API after BE 2 and feature 11).
11. **Time budget test.** The X-7 check runs in `make test` on the seed 42 synthetic market with
    both templates, 6 configs and the baseline. "Warm" means the second of two identical calls in
    one process; that call must keep a body under 6 MB and finish inside the time budget set
    below. It is a hard gate
    locally and report only on CI (shared runners are noisy). The deployed check is feature 15's. A miss is reported to the owner, then fixed by
    profiling first and ADR-016's vectorized windows second.

    **Amended 2026-10-11, on the first real measurement.** The 10 s figure was an assumption
    (doc 02 A4 said "measured on Day 4" and it never was). Here is what the warm run actually
    costs, from the `run-slow` job on PR #93 (GitHub `ubuntu-latest`, in process through
    `engine.api.backtest`):

    | template | entries (strategy + random) | warm | body |
    |---|---|---|---|
    | `breakout_52w` | 2,780 + 2,780 | 2.05 s | 717 KB |
    | `pullback_ema21` | 18,566 + 18,566 | 11.39 s | 716 KB |

    Cost is linear in entries, about 0.6 ms per entry across the 7 walks (6 configs plus the
    baseline), so roughly 0.09 ms per trade walk. `pullback_ema21` misses 10 s by 14%; nothing
    regressed, the template simply produces 6.7 times the entries. The same job measured the
    fixed size market (the 500 ticker, 1,260 bar random walk) inside 10 s.

    Three things follow, and they replace the single 10 s number:

    - **The deployed API is the authority, and its number is published.** X-7 is about the
      deployed Lambda, so that is where the budget is measured: feature 15's `make smoke` reports
      the warm number and the research note carries it. The hard ceiling is the function's own
      30 s timeout (x86_64, 2,048 MB, `infra/README.md` §6); the budget is **20 s warm**, two
      thirds of the ceiling, which leaves room for a slower runtime than the shared runner. Every
      entry is kept: no sampling, no cut to the config count, because metrics computed on a sample
      would weaken exactly the research claim this project is built on (doc 01 §6.6).
    - **Enforcement splits by what is stable.** CI hard gates the fixed size market, which does
      not depend on which template or how noisy the runner is. The seed 42 pair stays report only
      with its numbers printed, as this item already specified. The deployed number comes from
      smoke. QA can then flip X-7 to `required` against the stable half instead of waiting on a
      runner, which is the second path `docs/qa/ac-questions.md#X-7-margin` offers.
    - **The remedy order drops its first rung.** doc 02 §"X-7 misses" starts with raising memory
      from 2,048 MB to 3,008 MB "for more vCPU". That does nothing measurable here: the per trade
      loop is single threaded Python, Lambda already gives a full vCPU at 1,769 MB, and the extra
      memory costs 47% more per billed millisecond. The order is **profile the warm path, then
      ADR-016's vectorized per trade windows (about 2 h), and only then reduce the work** (fewer
      configs in the UI, or sampled entries with disclosure). Reducing the work changes what the
      lab measures, so it stays last.

## Requirements

**User stories**:
- As a researcher, I want to compare several exits on the very same entries, so the only thing
  that changes between rows is the exit.
- As a researcher, I want each exit measured against random entries through the same exit, so I
  can see how much of a result is just the market drifting up.
- As a researcher, I want the table to steer me to choose on IS and read OOS once, so I do not
  overfit by picking the best OOS row.

**Acceptance criteria** (the contract; doc 01 IDs in brackets):

Engine and API (BE):
- **AC-1** [X-1, B-14 to B-16]: for 2 to 6 configs the entry list (ticker, entry date, entry
  price) is computed once from the shared `entry_signals` and is identical across configs; every
  accepted signal is one unit notional trade, same ticker overlap allowed; `entries.hash` and
  `entries.count` follow spec 0002.
- **AC-2** [X-2]: 1 config runs portfolio mode (spec 0007), 2 to 6 run trade mode, 7 return 422
  `too_many_configs` (existing contract).
- **AC-3** [X-9]: a trade still open on bar `sim.horizon_bars` (entry bar = 1) exits at that close
  × (1 − slip) with reason `horizon`; a trade that reaches the cut market's last bar first exits
  `end_of_test`, or `delisted` on a real `delisted_on`.
- **AC-4** [X-8]: each config row carries `TradeMetrics` for strategy and random, IS and OOS, with
  `expectancy_per_bar_pct`, `distinct_weeks` and `horizon_exit_pct`, matching a hand checked
  fixture, and the response has no CAGR, max DD or Sharpe anywhere.
- **AC-5** [X-4]: a config without a stop has null `expectancy_r`, `r_multiple`, `mae_r`, `mfe_r`
  and null R edges.
- **AC-6** [X-3]: `best_is` holds, per ranked metric, the index of the config with the best non
  null strategy IS value (spec 0002 directions, ties to the lowest index); OOS, random and edge
  values are never ranked.
- **AC-7** [X-5]: `guides_is` comes from `configs[0]`'s strategy IS trades only; on a fixture
  where adding OOS trades would move them, they equal the IS only values.
- **AC-8** [X-10]: the random sample has exactly the strategy's IS and OOS counts, only on pool
  entries (assumed decision 3), and the same seed gives the same sample; each config's
  `edge` equals strategy minus random under that config, null when either side is null. The one
  exception: an empty segment pool gives 0 random entries there, null random metrics (counts 0)
  and null edges.
- **AC-9** [X-9]: `horizon_exits_over_10pct` is raised for exactly the configs over 10% (assumed
  decision 5), with `config_index` and the message from the mock's pattern.
- **AC-10** [B-10]: poisoning every bar after `sim.end` changes nothing in a trade mode response,
  random baseline included (the oracle uses every exit type, so it is fully green only once
  feature 11 lands).
- **AC-11** [X-7]: 6 configs plus the baseline answer warm with a body under 6 MB, and two
  identical requests give identical bodies. The time budget is **20 s on the deployed API**,
  measured by feature 15's smoke and published with the number (the function's own timeout is
  30 s). In process, CI hard gates the **fixed size market** (500 tickers, 1,260 bars) at 10 s;
  the seed 42 pair reports its numbers without failing CI, because the runner is shared. Measured
  2026-10-11: `breakout_52w` 2.05 s, `pullback_ema21` 11.39 s (design item 11 has the table).
- **AC-12** [U-3]: `assumptions` in trade mode: `sizing="unit_notional"`,
  `same_ticker_overlap=true`, `max_positions=null`, `horizon_bars=sim.horizon_bars`,
  `seed=sim.seed`, every config, `baseline_config_index=0`, and the other fields as in spec 0007.

Exit lab report (FE):
- **AC-13** [X-3]: the table shows one row per config, each metric as an IS | OOS pair; the cell
  named by `best_is` is highlighted in the IS column only, with a visible "best IS" marker that
  does not rely on color; no OOS, random or edge cell is ever highlighted.
- **AC-14** [X-4]: expectancy shows in %, and in R for configs with a stop; R cells of a stopless
  config read "n/a", and a footnote explains that R needs a stop.
- **AC-15** [X-9]: a config named by a `horizon_exits_over_10pct` warning shows a warning badge on
  its row with the warning message.
- **AC-16** [X-10]: each row shows edge vs random (expectancy %, expectancy R, expectancy per bar,
  win rate) for IS and OOS; a "Random entries" row shows `configs[0]`'s random metrics; each row
  can disclose its own random metrics.
- **AC-17** [X-5]: the guide row shows winner MAE p75 and p90 and median MFE with the label "from
  the baseline config's IS trades only"; null reads "n/a".
- **AC-18** [U-8, spec 0004]: `ProcedureNote` renders directly under the table;
  `RunTrialCounter` sits beside the assumptions header once a 200 result is on screen and records
  one pair per config.
- **AC-19** [U-3]: the assumptions header lists every AC-12 item through feature 9's
  `assumption-labels.ts`; null fields read "not used in trade mode"; the horizon, the seed and
  "same ticker trades may overlap" are stated.
- **AC-20** [X-2, U-5 to U-7]: the exit form holds 2 to 6 configs (add disabled at 6),
  `configs[0]` is labelled the baseline; loading, warming up, 422 on the right exit field, 501 and
  `no_entries` states render; the table scrolls inside its container at 375 px with a sticky
  config column; the page is keyboard usable and axe clean.

## Decision

**Chosen option**: Option 1: a per trade loop over spec 0007's `walk_trade()`, a separate seeded
baseline module, and per trade metrics computed once per (config, side, segment).

`engine.api.backtest` routes 2 to 6 configs to a thin trade mode use case: entries once, random
sample once, then each config walks both lists through the same `Exit` objects and `step()`.

**Implementation skills**: `python-testing-patterns` (`wshobson/agents`,
`.claude/skills/python-testing-patterns/`) · `fastapi` (`fastapi/fastapi`,
`.agents/skills/fastapi/`) · `nextjs-app-router-patterns` (`wshobson/agents`,
`.claude/skills/nextjs-app-router-patterns/`) · `shadcn` (`shadcn-ui/ui`, `.agents/skills/shadcn/`)
· `tailwind-design-system` (`wshobson/agents`, `.claude/skills/tailwind-design-system/`)

## Rationale

Reasoning and options: see [rationale.md](rationale.md).

## Feature design

**Module layout** (engine domain modules from AGENTS.md):

| Module | Owns |
|---|---|
| `engine/sim/walk.py` (spec 0007, PR #31) | `walk_trade()`, `make_trade()`, `EntryContext`; reused unchanged, PR #31 signatures |
| `engine/sim/trade_mode.py` | `run_trade_mode(entries, configs, bars, sim, oos_start) -> list[ConfigTrades]`: one `walk_trade()` per (entry, config) |
| `engine/baseline/random_entries.py` | `eligible_pool(market, start, oos_start) -> (pool_is, pool_oos)`, `sample(pool_is, pool_oos, is_count, oos_count, seed) -> list[EntryPoint]`; never sees a config |
| `engine/metrics/trade_mode.py` | `trade_metrics(trades) -> TradeMetrics`, `edge(strategy, random)`, `best_is(rows)`, `guides_is(trades)`, `horizon_warnings(...)` |
| `engine/api.py` | `backtest()`: 2 to 6 configs → `_trade_lab()`; drops the 501 for trade mode in BE 2 |
| `apps/web/src/features/exit-lab/` | `ExitLabTable`, `GuideRow`, `ExitLabReport`, `default-configs.ts`, `columns.ts` |

**Data model sketch** (in memory only; no database, no new contract types):

| Type | Fields |
|---|---|
| `EntryPoint` | `ticker`, `signal_row`, `entry_row` (signal row + 1), `entry_date`, `entry_fill` = open × (1 + slip), `segment` |
| `ConfigTrades` | `config_index`, `strategy: list[Trade]`, `random: list[Trade]` |
| contract `TradeLabResult`, `ConfigRow`, `TradeMetrics`, `EdgeMetrics`, `BestIs`, `Guides`, `Entries` | frozen in spec 0002; filled as below |

**State transitions**: none; every request is stateless.

**Trade mode flow** (one request):
1. Cut the market at `sim.end` (spec 0007 decision 10); compute `oos_start` the same way.
2. Entries: `entry_signals(rule)` on the cut market, signals at t in [`sim.start`, last session
   − 1], sorted by (entry date, ticker). One list for every config (X-1).
3. Random: build the pool, draw IS then OOS with the seed (assumed decision 3).
4. For each config: `build_exits(config)` (feature 11 types 501 until feature 11), then
   `walk_trade(..., horizon=sim.horizon_bars)` over the strategy list and the random list; each
   outcome goes through `make_trade()` with the same slip and `oos_start`.
5. Metrics per (config, strategy or random, IS or OOS); edge; `best_is`; `guides_is`;
   warnings; `baseline_trades`; `assumptions`; `trial`.

**API surface** (no new endpoint; `POST /api/v1/backtest` from spec 0002):

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/backtest` | POST | `rule`, `configs` (2 to 6), `sim` (`horizon_bars`, `seed`, `slippage_bps`, `start`, `end`) | `TradeLabResult` (`mode: "trade"`) | public | 422 (contract, 7 configs), 501 (until BE 2; feature 11 exit types; no market) |

**Value sourcing**:

| Action | Value | Source |
|---|---|---|
| entries | list | `engine.rules.entry_signals` (spec 0005), last bar term on, once per request |
| entry | fill | `open(t + 1) × (1 + slippage_bps / 10,000)`, unit notional |
| `entries.count`, `is_count`, `oos_count` | counts | the strategy entry list, by entry segment |
| `entries.distinct_weeks` | count | distinct ISO (year, week) of strategy entry dates (spec 0002) |
| `entries.hash` | hash | spec 0002 (`sha256` of sorted `ticker|entry_date` lines) |
| `entries.random_is_count`, `random_oos_count` | counts | the drawn random sample's sizes |
| random pool | (ticker, t) | assumed decision 3; benchmark excluded via `market.meta.benchmark` |
| random draw | sample | `numpy.random.default_rng(sim.seed)`, `Generator.choice(len(pool), size=k, replace=False)`, IS first, then OOS, from pools sorted by (entry date, ticker) |
| exits | fills | `build_exits(config)` through `step()` via `walk_trade()` |
| horizon | bars | `sim.horizon_bars` (5 to 252, default 60) |
| `Trade` fields | all | `make_trade()` (spec 0007 value sourcing), segment by entry date |
| `TradeMetrics` | every field | spec 0002 metric definitions; `distinct_weeks` per segment over that side's entry dates |
| `edge.*` | four numbers | strategy minus random, same config and segment; null when either is null |
| `best_is` | indexes | spec 0002 directions over `rows[i].strategy.is` only |
| `guides_is` | three numbers | spec 0002, over `configs[0]` strategy trades with `segment = "is"` |
| `baseline_trades`, `_total`, `_truncated` | list | `configs[0]` strategy trades, sorted by entry date then ticker, even spread over 2,000 (spec 0002) |
| warnings | list | in order: `no_entries` (`config_index` null, "No entries: the rule never produced a signal in this window."), each `horizon_exits_over_10pct` in config order (`config_index` i, "{name}: more than 10% of trades hit the {h} bar horizon, so its results are cut short."), `trades_truncated` (`config_index` null, as in spec 0007, "Showing 2,000 of N baseline trades; metrics use all of them.") |
| `assumptions` | trade mode fields | AC-12; spec 0002 value sourcing row |
| `trial` | keys | `structure_key(rule)`, one `pair_key(rule, config)` per config |
| FE highlight | cell | `best_is[metric]` → that row's IS cell |
| FE badge | row | only `warnings` with code `horizon_exits_over_10pct`, on the row at its `config_index` |
| FE "no stop" | footnote trigger | any config whose `exits` has no `stop_pct`, `stop_atr` or `trail_pct` |
| FE "Random entries" row | metrics | `rows[0].random` |
| FE defaults | configs | `features/exit-lab/default-configs.ts` (the mock's five) |
| FE inputs | rule and configs | the page URL (`?r=` or `?template=`, `?x=`), as in spec 0007 |

**Precise rules the build must not invent**:
- No rounding in the engine; float64 out (oracles check to 1e-9).
- A random trade and a strategy trade on the same (ticker, entry date) are both kept; they are
  separate samples.
- Random entries ignore the rule, its validity and the cooldown; they share the slippage, the
  exits, the horizon and `oos_start`.
- `no_entries`: rows still carry every config with `n_trades = 0`, `distinct_weeks = 0`, every
  other metric null, random counts 0 (no draw), `best_is` and `guides_is` all null.
- A non empty pool smaller than its count draws with replacement and the response is otherwise
  unchanged (only on tiny fixtures; the synthetic pool is about 600k pairs). An empty pool draws
  0 (AC-8's exception).
- Highlight ranking uses unrounded values; display rounding (`format.ts`) never changes the winner.

**Key invariants**:
- Exit precedence lives only in `step()`; no exit is special cased in trade mode or the baseline
  (AGENTS.md).
- The strategy entry list is byte identical for every config of one request.
- Nothing after `sim.end` is read; the random pool is built on the cut market.
- Same request, same seed, same body.
- No CAGR, max DD or Sharpe exists in a trade mode response (contract types enforce it).
- `engine` imports no web framework; `services/api` stays a thin route.

**Security model**: public, no auth, no secrets; inputs are the validated contract. The 6 MB cap
holds because rows are aggregates and only one trade list (≤ 2,000) ships.

**Configuration required**: none new.

**Critical test scenarios**:
- Oracles that turn green with this feature: `test_loop_parity`, `test_horizon` (both X-9
  tests), B-10's trade mode test, the trade mode halves of B-15 and B-16; those using `target`
  or `trail_pct` also need feature 11, verifies **AC-1**, **AC-3**, **AC-9**, **AC-10**
- Unit: a 3 config fixture where the entry hash and count match across configs, verifies **AC-1**
- Unit: a hand checked 6 trade fixture for every `TradeMetrics` field, IS and OOS, and the JSON
  has no `cagr_pct`, `max_dd_pct`, `sharpe` keys, verifies **AC-4**, **AC-5**
- Unit: `best_is` directions and ties, OOS better than IS never moves it, verifies **AC-6**
- Unit: the X-5 fixture where OOS winners would shift p75 and p90, verifies **AC-7**
- Unit: 120 IS and 40 OOS strategy entries give 120 and 40 random entries, all in the pool, same
  seed equal, a different seed different; edge equals strategy minus random; an empty OOS pool
  gives 0 and null edges, verifies **AC-8**
- Unit: a config with 5% IS, 30% OOS and 12% combined horizon exits warns; one at 8% combined
  does not, verifies **AC-9**
- API: 2 configs before BE 2 return 501 naming feature 12; 7 configs return 422, verifies **AC-2**
- Budget: seed 42, both templates, 6 configs, warm, under 10 s and 6 MB, run twice equal,
  verifies **AC-11**, **AC-12**
- Web (Vitest + MSW on `backtest.trade_lab.json`): highlight only in IS cells, n/a and footnote
  on "MA exit, no stop", badge on "Wide target, no stop", guide row, procedure note placement,
  every state, 375 px and axe, verifies **AC-13** to **AC-20**

## Build plan

Tracer Bullet, thickening spec 0007's thread. FE runs now on the mocks; BE starts after G2
(PR #31 merged).

**BE lane (`engine/`, `services/api/`)**
1. Trade mode thread: `trade_mode.py` over `walk_trade()` with the horizon, shared entries,
   `trade_metrics`, `best_is`, `guides_is`, warnings, `baseline_trades`, `assumptions`, `trial`,
   all unit tested in the engine; `/backtest` keeps 501 for 2 to 6 configs (assumed decision 2).
   Satisfies **AC-1**, **AC-3** to **AC-7**, **AC-9**, **AC-12**
2. Random baseline and edge: `baseline/random_entries.py`, random rows, `edge`, then drop the
   501; B-10 trade mode and parity tests. Satisfies **AC-2**, **AC-8**, **AC-10**
3. Budget: the X-7 test on seed 42; profile; ADR-016 vectorized windows only if it misses, and a
   miss is reported in the PR, never hidden. Satisfies **AC-11**
3a. Enforcement split (after the 2026-10-11 measurement): the fixed size market becomes the hard
   CI gate at 10 s, the seed 42 pair stays report only with its numbers printed, and feature 15's
   smoke measures the deployed warm number against 20 s. No engine change; the work is in
   `engine/tests/sim/test_lab_budget.py`, `tests/acceptance/test_exit_lab.py` and feature 15's
   smoke script. Satisfies the amended **AC-11**

**FE lane (`apps/web/src/features/exit-lab/`)**
4. Table thread against the mock: `ExitLabTable` (IS | OOS pairs, best IS highlight with a non
   color marker, R n/a and footnote, horizon badge, edge group, Random entries row, per row
   disclosure), `ProcedureNote` directly under it, `GuideRow`; `/ui` gallery entries.
   Satisfies **AC-13** to **AC-18**
5. Page wiring once feature 9's report page is on `main`: 2 to 6 config exit form with defaults,
   `mode` switch on `/backtest`, trade mode assumptions header, `RunTrialCounter`, baseline trade
   list, every state, 375 px, axe; switch to the real API after BE 2. Satisfies **AC-19**,
   **AC-20**

## Consequences

**Positive**:
- Trade mode adds a loop and a sampler but no exit logic, so features 11 and 12 can land in either
  order and the parity oracle holds by construction.
- The edge column gives an honest yardstick on biased data at the cost of one extra pass.
- FE is unblocked today; the frozen contract and mock cover every table state.

**Negative / tradeoffs**:
- Plain Python walks about 2.7M steps in the worst case (doc 02 §8); X-7 may miss and cost the
  ADR-016 rewrite (about 2 h). It did miss, by 14% on `pullback_ema21`, and the 2026-10-11
  amendment chose the published measurement over the rewrite for now.
- The budget is now a number this project publishes rather than one it quietly passes, so a
  reviewer can read 11.39 s next to the claim. That is the cost of keeping every entry: the honest
  number is less flattering than the original 10 s promise, and the deployed figure is still owed
  by feature 15.
- Nothing fails CI today if the seed 42 run gets slower, by design. The fixed size gate catches a
  real regression in the loop; a template that simply produces more entries will not turn CI red,
  it will show up in the printed numbers and in smoke.
- Random entries skip every warm up, so they can sit earlier in a ticker's life than any strategy
  entry could, and an ATR stop on such an entry follows feature 11's null ATR rule.
- The 501 stays on trade mode until BE 2, so FE cannot hit the real API for the lab until then.
- No entry cap: a very loose rule makes a slower run rather than a capped one.

**Neutral**:
- `engine.api.FEATURE_NAMES` gains 12 (spec 0007 already plans it).

## Follow-up

- [x] Owner sign-off on the eleven assumed decisions above.
- [ ] Depends on PR #31 (feature 9 BE thread with `step()` and `walk_trade()`) merging (G2).
- [ ] Feature 11's exits turn the parity, X-9 and B-10 trade mode oracles fully green and let the
  default configs run on the real API (AC-10, AC-20).
- [ ] Feature 11 decides how `stop_atr` handles a null ATR at the signal bar (strategy and random
  entries alike).
- [ ] If X-7 shows a need, a `contract-change` PR adds an entry cap warning code; sync doc 02 §8's
  25k cap line either way once signed off.
- [ ] Feature 15 measures X-7 on the deployed API. **Now the authority for the budget**: smoke
  reports the warm number against 20 s and the research note publishes it.
- [ ] Carry the amended AC-11 into the three places that still say 10 s: doc 01's X-7 row (the
  owner's product criterion), `docs/qa/ac-questions.md#X-7-margin` (QA's ruling, whose second
  path this takes), and doc 02's "X-7 misses" ladder (drop the memory rung). Each sits in its
  owner's lane, so none is edited here.
- [ ] Build the enforcement split: `engine/tests/sim/test_lab_budget.py` fails on CI for the fixed
  size market and keeps printing the seed 42 numbers; `tests/acceptance/test_exit_lab.py` gates
  X-7 on the fixed size market. Then QA can flip X-7 to `required` in `status.yaml`.
- [ ] Spec 0007 (truncation keeps the last 2,000) and spec 0002 (even spread) differ; this spec
  follows spec 0002 for `baseline_trades`. Reconcile spec 0007 when its owner signs off.
- [ ] X-5S (scatter) and X-6 (portfolio mode exit lab) stay Stretch.
