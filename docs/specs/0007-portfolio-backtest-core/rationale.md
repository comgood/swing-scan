# 0007. Portfolio backtest core: decision record

## Context

Scope feature 9 (`· GA`) is the first real backtest: one rule, one exit config, a portfolio with
limited slots, IS and OOS, an equity curve against the benchmark, a trade list with MAE and MFE,
and a report page. Doc 01 (B-1 to B-16, U-3) and doc 02 (§5.4, §7.1 to §7.3, ADR-006, 008, 014,
016) fix most of the behaviour: next open fills, 10 bps a side, equal weight of equity ÷
`max_positions`, ranking by `rs(126)`, one position per ticker, OOS as the last 30% of dates,
`end_of_test` at the final close, the `Exit` protocol and the per bar precedence, and the rule
that both loops call one `step()`. Spec 0002 freezes the request and the `PortfolioResult` shape.
Spec 0005 provides the indicator cache and the shared `entry_signals` function.

What none of them fix: how the code is split into modules, which exits ship now versus feature
11, the order of events inside a day, how free slots and cash interact, how a null `rs(126)`
ranks, the equity scale, the exact metric formulas and their null cases, how the curves are
thinned to 500 points and which trades survive the 2,000 cap, how `sim.start` and `sim.end` cut
the data, and what the report page looks like and where it lives.

Forces: the owner approved the oracles in `tests/oracle/` (gate G1, PR #9), and the BE lane builds
the engine next, so BE work must be sliceable on its own. The FE lane can start at once on the
mocks. Every decision must keep the oracles' readings (README in `tests/oracle/`). The API runs in
Lambda with a 6 MB response cap and a 3 s warm budget (B-13). AGENTS.md forbids special casing an
exit outside `step()`.

## Options considered

### Option 1: Day loop plus per trade walker over one `step()` (chosen)

The portfolio loop walks sessions, managing slots and cash, and calls `step()` for each held
position. A tiny `walk_trade()` calls the same `step()` along one trade's own bars, ready for the
exit lab.

**Pros**:
- Matches doc 02 §7.3 and ADR-008 exactly; parity holds by construction.
- Each piece is small and testable alone: exits, `step()`, slots, metrics.

**Cons**:
- Two loops to keep in mind, even if the second is tiny now.

### Option 2: Precompute every trade with the walker, then allocate slots

Walk every signal's trade independently first (exits do not depend on the portfolio), then run a
light allocation pass that picks which trades the slots take.

**Pros**:
- One loop for exits; the portfolio pass is pure bookkeeping.

**Cons**:
- Walks trades the portfolio never takes (thousands on full history), wasting the 3 s budget.
- Diverges from doc 02's stated design, which the oracles and reviewers read against.

### Option 3: Vectorized simulation

Express entries, exits and equity as array operations (NumPy or Polars).

**Pros**:
- Fast at large scale.

**Cons**:
- Path dependent rules (slots, trailing levels, pending MA, the cooldown chain) make vectorized
  code hard to read and hard to check against hand computed oracles; ADR-006 and ADR-016 say
  loops first, vectorize only if profiling demands it.

### Sub decisions (each with its runner up)

| Question | Chosen | Runner up and why not |
|---|---|---|
| Exits in feature 9 | `stop_pct`, `time`, delisting, `end_of_test`; feature 11 adds the rest | all six now: blurs feature 11's GA review and doubles this PR |
| Trade mode | 501 naming feature 12; `walk_trade()` shipped internally | build trade mode too: that is feature 12's spec and its own decision |
| Day order | exits, then entries at the open, then entry bar steps, then mark | entries before exits: frees no slot either way, but reads less naturally against §7.2 |
| Freed slots | usable from the next session | same day reuse: needs an intraday order of exits and entries the data cannot give |
| Sizing | equity at the signal close ÷ N, capped by cash | equity at the open: needs the open of every holding first, same result within noise |
| Null `rs(126)` | ranks last | excluded: a young ticker could never enter, a hidden filter (ADR-013 forbids those) |
| Equity scale | starts at 100, benchmark rescaled to 100 | dollars (100,000): adds a fake account size that means nothing with fractional shares |
| OOS curve | continuous curve, OOS slice | restart at 100 for OOS: hides the drawdown carried in from IS |
| Sharpe | daily, rf 0, `ddof=1`, × sqrt(252) | monthly: too few points in a short OOS |
| Exposure | average invested share at the close | share of days with any position: says 100% for a portfolio that holds one tiny position |
| Zero return trade | a loss | its own bucket: no field for it in the contract |
| 500 point curve | every k th session plus the last | largest triangle downsampling: nicer shape, more code, and metrics do not use it anyway |
| 2,000 trade cap | most recent by entry date | first 2,000: would drop the OOS trades, the ones you read last and most |
| `sim.start` | stops signals only; warm up uses earlier bars | cut the data too: every indicator would restart warming up at `start` |
| Report route | static `/backtest` with URL inputs | a modal on the scan page: no shareable link |
| Chart | Lightweight Charts, two lines | Recharts: a second chart library in the bundle |

## Rationale

Option 1 is what doc 02 already promises, and the oracles (especially the loop parity test) were
written against it. Its real advantage is that precedence exists in exactly one function, so
features 11 and 12 extend the engine by adding classes and a loop, never by editing a hot path the
GA review has already passed. Option 2 is clever but walks thousands of trades the portfolio
never takes; Option 3 trades readability for speed we do not need at 500 tickers.

Splitting the exits keeps feature 9 shippable by the BE lane tomorrow: `stop_pct` and `time` cover
B-1, B-2, B-7, B-8, B-11 and B-14 to B-16, while feature 11 carries its own GA review for the
trickier exits (ATR at the signal bar, trailing levels, the pending MA). The cost, B-9 and B-10's
portfolio half waiting for feature 11, is visible in the scope and acceptable.

The sub decisions all lean towards what can be checked by hand: next day slot reuse, sizing at a
known close, a continuous equity curve, and formulas written in the spec with explicit null cases,
so `/check verify` and QA can recompute any number on the report.
