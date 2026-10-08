# 0009. Exit lab: decision record

## Context

Scope feature 12 (`· GA`) is the exit lab: one entry rule, 2 to 6 exit configs, identical
entries, per trade metrics in IS and OOS columns, and a seeded random entry baseline run through
the same exits (doc 01 §6.5, X-1 to X-5, X-7 to X-10; doc 02 §7.3, §7.4, §8; ADR-008, 014, 016,
017). Spec 0002 already froze `TradeLabResult` with its metric definitions, `best_is` directions,
`guides_is`, the entries hash and the trade list cap. Spec 0007 (feature 9) designed the `Exit`
protocol, the single `step()` with the horizon at step 5, and `walk_trade()`, which open PR #31
implements. Spec 0004 owns `ProcedureNote` and `RunTrialCounter` and leaves their placement on
the exit lab to this feature. Oracles in `tests/oracle/` (parity, horizon, B-10 trade mode,
B-15 and B-16 trade mode) define correctness.

What none of them fix: where the trade mode loop and the baseline live, how the random pool is
built and drawn (which bars count as eligible, draw order, replacement), what the warning scope
for the horizon is, what `baseline_trades` holds, whether an entry cap applies, how the table is
laid out, where the procedure note and guide row sit, which configs the form starts with, and how
the time budget is checked.

Forces: the BE lane is the critical path and cannot touch trade mode until G2 (PR #31). The FE
lane is free now and has a mock covering a stopless config and a horizon warning. AGENTS.md
forbids special casing an exit outside `step()` and changing the baseline seed default without an
ADR. Lambda caps the response at 6 MB and the budget is 10 s warm for 6 configs plus the baseline.

## Options considered

### Option 1: Per trade loop over `walk_trade()`, separate baseline module (chosen)

**Pros**:
- Exactly doc 02 §7.3 and ADR-008; parity holds by construction because both loops call `step()`.
- Each part (loop, sampler, metrics) is small and unit testable without infrastructure.

**Cons**:
- Plain Python per step; the 10 s budget is not guaranteed and may force ADR-016's rewrite.

### Option 2: Vectorized per trade windows from day one (ADR-016's fallback)

Build an E × horizon array per config and resolve exits with NumPy masks.

**Pros**:
- Likely 10x faster; the budget is safe.

**Cons**:
- Exit precedence would be reimplemented outside `step()`, which AGENTS.md forbids unless `step()`
  itself is vectorized; that is a rewrite of feature 9's core before any measurement says it is
  needed (premature optimisation).

### Option 3: Run each config through the portfolio day loop

**Pros**:
- One loop for both modes.

**Cons**:
- Slot competition makes entries differ by exit, breaking X-1; doc 01 rejects it (ADR-014).

### Sub decisions (recommended pick, runner up)

1. Random pool warm up: no filter, leaving a null ATR to feature 11's `on_entry` for random and
   strategy entries alike (runner up: require exit indicators non null at t; rejected after the
   cross check because the pool would depend on the configs, so adding one config would change
   every row's random sample, and the sampler would have to know exit types).
2. Draw: one PCG64 generator, IS then OOS, without replacement (runner up: with replacement;
   rejected because duplicate random trades inflate the sample's apparent size).
3. Horizon warning over all of a config's strategy trades (runner up: IS only; rejected because
   doc 01 X-9 says "trades", and the oracle reads all).
4. Hold the 501 until the baseline lands (runner up: ship trade mode with zero random rows;
   rejected because `main` would serve misleading edge numbers).
5. Table with config rows and IS | OOS pairs (runner up: metrics as rows and configs as columns;
   rejected because doc 01 and doc 02 W6 specify one row per config).
6. Exit lab on `/backtest` switching on `mode` (runner up: a separate `/exit-lab` route;
   rejected because the request is the same and the URL already carries `?x=` configs).

## Cross check

A read only pass by a second model (Sonnet) checked the draft against specs 0002, 0004 and 0007,
docs 01 and 02, the contract, the mock and the oracles. Its findings were folded in: the random
pool no longer depends on the configs or exit types, an empty pool has a defined result, the
feature 11 dependency of the default configs and of B-10 is explicit, PR #31's `walk_trade()` and
`make_trade()` signatures are named as authoritative, the horizon warning scope is stated as a
refinement of spec 0002, the 25k cap is flagged as a doc 02 deviation, `trades_truncated` uses
`config_index` null, the draw call is named, and "warm" is defined for the budget test.

## Rationale

Option 1 is the only one that keeps precedence in one place, which is the property the oracles
and the AGENTS.md rule protect, and it reuses code feature 9 already writes. The performance risk
is real but measured early (BE 3), with a known fallback, instead of paying for it up front. The
sub decisions keep the honesty properties (same seed same sample, IS only highlighting, edge
traceable per row) and keep `main` from ever showing a half built lab.
