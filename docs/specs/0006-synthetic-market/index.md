# 0006. Generate the synthetic market from a seeded NumPy factor model at build time

**Date**: 2026-10-07 (assumed by /develop) · ratified by /architect 2026-10-08
**Status**: Proposed, pending owner sign-off
**Authorized by**: owner's standing instruction to the DI lane agent, during /develop; ratification
run unattended overnight, every open question took /architect's recommended answer (listed below)

## Summary

This spec fixes how the app's invented stock market is made. One seed drives a small factor model
(a market factor with planted regimes, ten sector factors, fat tailed noise per ticker, and a
documented momentum edge), so the same seed always gives the same 500 tickers over 1,260 trading
days, plus a `DEMO-INDEX` benchmark, about 25 delistings and 25 late listings. The data is
generated when the API image builds and when you run `make data`; it is never committed. The code
already exists in `engine/src/engine/synthetic/` and `engine/src/engine/data/`; this ratification
confirms what was built, writes every number down, and records why.

## Assumed decisions (pending owner sign-off)

The owner could not answer during this run. Each question took /architect's recommended answer.
Where the earlier assumed text and the code disagreed, the recommendation was to keep the code
(it is tested and already feeds features 8 and 9) and correct the text; see *Follow-up*.

1. **Generator.** A pure seeded factor model in NumPy, generated at build time, never committed.
   Runner up: independent random walks per ticker (simpler, but no regimes, no sector
   correlation, no planted edge).
2. **Randomness.** One `numpy.random.default_rng(seed)` (PCG64) drawn in a fixed order, prices
   rounded to 4 decimals, volumes to whole shares. Runner up: one generator per ticker (harder to
   keep the draw order stable).
3. **Calendar.** 1,260 weekdays from Mon 2021-01-04, no holidays, fixed end date. Runner up: a
   real exchange calendar (adds a dependency and a holiday table for no research gain).
4. **Bear guarantee.** Exactly one planted bear of 120 to 180 sessions, starting between session
   302 and 693, total market log return drawn in [−0.45, −0.30], always followed by a recovery
   run. Runner up: rely on random regimes (D-3 could fail for some seeds).
5. **`DEMO-INDEX`.** The market factor itself, level 1,000 at the start. Runner up: an equal
   weight average of the tickers (it would inherit delistings and the planted momentum).
6. **Planted edge.** `0.10 × clip(L63, −0.5, 0.5) / 63` added to each ticker's daily expected log
   return, off for a ticker until it has 63 sessions of history and off during an acquired
   ticker's pinned period. Runner up: no planted edge (the demo would show nothing to find, and
   the research note could not check that the tools find a known effect).
7. **Listings and delistings.** 25 mid sample listings (first bar in sessions 252 to 1,008), 25
   delistings disjoint from them (last bar in sessions 202 to 1,239), each one `bankruptcy` with
   probability 0.6, else `acquired` (seed 42 gives 12 and 13). Runner up: delist at random with no price story (a backtest would then exit at
   prices that look like nothing happened).
8. **Names and version.** Invented 4 letter consonant vowel symbols, `data_version="synthetic-1"`,
   bumped on any model change. Runner up: a content hash as the version (exact, but unreadable in
   the assumptions header).
9. **Determinism scope.** D-1 is promised for the same seed, the locked NumPy and Polars
   versions (`uv.lock`), and the same CPU architecture, not across library upgrades or between
   arm64 and x86 (`exp` and `log` may differ in the last bit, and a value near a rounding edge can
   flip). Golden files are generated on the build architecture (the image is `linux/amd64`,
   Lambda runs `x86_64`, CI runs on x86_64 runners); a laptop on arm64 may differ in rare bars. Runner up: a pure Python generator
   with its own PRNG (portable forever, but about 100 times slower and more code to own).

10. **Spec versus code differences found at ratification** (cross check and the DI lane verify,
    `docs/reviews/2026-10-08-verify-synthetic-market.md`, PR #19). For each, the recommended
    answer was to align the spec to the code (tested, already consumed by features 8 and 9; a
    code change would bump `synthetic-1` and churn goldens for no research gain):
    - Delist reason is an independent 0.6 coin flip per delisting, not an exact 60/40 split:
      spec aligned.
    - Mid sample listings start in sessions 252 to 1,008 (spec said 1,000): spec aligned.
    - Delistings land in sessions 202 to 1,239 (spec said 200 to 1,240): spec aligned.
    - The tests live in `engine/tests/dataset/`, not `engine/tests/data/`: spec aligned.
    - Several model constants sit in `generator.py`, not `SyntheticConfig`: spec aligned (they
      are listed below as fixed constants); moving them into the config is a follow-up.

## Code area

`engine/src/engine/synthetic/` (`config.py`, `generator.py`, `__main__.py`),
`engine/src/engine/data/` (`sanity.py`, `store.py`), `engine/tests/synthetic/`,
`engine/tests/dataset/`, `services/api/Dockerfile` (stage 1), `Makefile` (`data` target).

## Requirements

**User stories**:
- As a visitor, I want the demo to run on a believable market with no real prices, so I can try
  the scanner and backtester with no data licence and no cost.
- As the owner, I want the same seed to give the same market everywhere, so tests, golden files
  and the research note agree.

**Acceptance criteria** (the contract, from doc 01):
- **AC-1** (D-1): the same seed gives identical bars, securities and meta, frame for frame.
- **AC-2** (D-2): every bar has `low ≤ min(open, close)`, `high ≥ max(open, close)`,
  `volume > 0`, and no ticker has bars after its `delisted_on` (nor before its `listed_from`).
- **AC-3** (D-3): at least one bear segment, meaning `DEMO-INDEX` closes at least 20% below its
  running peak (owner ruling, `docs/qa/ac-questions.md`), and at least 20 delisted tickers. Both
  hold by construction: the bear's upper bound `bear_log_return_range[1] = −0.30` gives at least
  a 25.9% fall, and `min_delisted = 20` sets the floor. `generate` does not assert D-3 itself; the
  tests check it at seed 42 and seeds 0 to 7.
- **AC-4**: `python -m engine.synthetic --seed 42 --out DIR` writes `bars.parquet`,
  `securities.parquet` and `meta.json`; `engine.data.read_market(DIR)` loads and checks them, and
  `market_dir()` reads `SYNTHETIC_DATA_DIR` (default `data/synthetic`).
- **AC-5**: the planted momentum edge is real and switchable: pooled over every non index
  ticker and session at seed 42, the Pearson correlation of the trailing 63 session log return
  with the next 21 session log return is above 0, and `momentum_coef=0` changes the output. The
  effect is small by design (at most 0.10 × 0.5 / 63, about 0.08% a day); no larger threshold is
  promised.

## Decision

**Chosen option**: Option 1: a seeded NumPy factor model, generated at build time.

`engine.synthetic.generate(seed: int = 42, config: SyntheticConfig | None = None) -> Market` is a
pure function (no I/O, no clock, no global random state) that checks its own output with
`engine.data.check_market` before returning.

**Implementation skills**: `python-testing-patterns` (`wshobson/agents`,
`.claude/skills/python-testing-patterns/`) · `multi-stage-dockerfile` (`github/awesome-copilot`,
`.agents/skills/multi-stage-dockerfile/`)

## Rationale

Reasoning and options: see [rationale.md](rationale.md).

## Feature design

**Data model** (contract from spec 0002; this spec fills the values):

| Output | Rows | Content |
|---|---|---|
| `bars` | 602,776 at seed 42 | `ticker, date, open, high, low, close, volume`, sorted by ticker then date |
| `securities` | 501 | 500 tickers plus `DEMO-INDEX` (sector `Index`, never delisted) |
| `meta` | 1 | `data_mode="synthetic"`, `seed`, `data_version="synthetic-1"`, `start`, `end`, `n_tickers=500`, `survivors_only=false`, `benchmark="DEMO-INDEX"` |

**Model, per session t and ticker i**:
`r[i, t] = beta_i × market[t] + sector[s_i, t] + idio_vol_i × t4 + momentum[i, t]`, then the
delisting overrides below. The tunable numbers live in `SyntheticConfig` (`config.py`); the
ones marked *fixed* are constants in `generator.py`. A change to either kind bumps the version.
`σ` below is a ticker's typical daily vol, `sqrt((beta × 0.011)² + 0.007² + idio_vol²)`, and
0.011 for `DEMO-INDEX`.

| Part | Value |
|---|---|
| Regimes (drift, vol per day) | `bull` +0.06%, 0.9% · `chop` 0, 1.1% · `bear` −0.15%, 1.9% · `recovery` +0.10%, 1.4% |
| Calendar | 1,260 weekdays, Mon 2021-01-04 to Fri 2025-10-31 |
| Regime schedule | runs of 40 to 160 sessions (the first run after the bear and the runs cut by the bear or the end can be shorter); calm runs drawn bull 55%, chop 25%, recovery 20% (*fixed*); a recovery always follows the bear |
| Planted bear | length 0.095 to 0.143 of `n_sessions` (120 to 180), start 0.24 to 0.55 (302 to 693), noise demeaned, total log return in [−0.45, −0.30] |
| Sectors | 10 invented, round robin after a seeded shuffle, factor vol 0.7% |
| Beta | uniform [0.6, 1.6] |
| Idiosyncratic | Student t, 4 degrees of freedom, scaled to unit variance, then to a vol in [1.0%, 3.0%] |
| Momentum | coef 0.10, lookback 63, clip ±0.5; on from session `listed + 64` (64 for tickers there from the start); off after an acquired ticker's announcement day. A per ticker time series effect (it includes the market and sector parts of the trailing return), not a cross sectional one |
| Start price | log normal, median $40, sigma 0.9 (*fixed*), clipped to [$2, $400]; floor $0.05 after rounding |
| Open | previous close × exp(0.3 × return + 0.25 σ × normal) (*fixed*) |
| High, low | past max/min(open, close) by a half normal wick of 0.5 σ (*fixed*), then clamped exact |
| Volume | base log normal (median 1M, sigma 0.8; index 500M) × exp(0.35 × normal) × (1 + 3 × abs(return) / σ), at least 1 (sigmas, 0.35 and 3 *fixed*) |
| Listings | round(5% × 500) = 25, first bar in sessions round(0.2n) to round(0.8n), 252 to 1,008 inclusive (*fixed* fractions) |
| Delistings | max(20, round(5% × 500)) = 25, disjoint, last bar in round(0.16n) to n − 21, 202 to 1,239 inclusive (*fixed* bounds); each is `bankruptcy` with probability 0.6, else `acquired` |
| `bankruptcy` | extra −0.6% a day over the last 40 sessions |
| `acquired` | jump of +25% to +40% at 20 sessions before the last bar, then 0.2% daily noise (*fixed*), no momentum |
| Tickers | 4 letters, consonant vowel consonant vowel (18 × 5 × 18 × 5 = 8,100 possible), drawn without replacement |
| Names | capitalized symbol plus a seeded suffix (`Labs`, `Holdings`, ...) |

**Interface**:

| Surface | Inputs | Outputs | Errors |
|---|---|---|---|
| `generate(seed, config)` | `int`, optional `SyntheticConfig` | `Market` | `ValueError` for an impossible config, `MarketError` if the check fails |
| `python -m engine.synthetic` | `--seed` (42), `--out` (required) | 3 files, one summary line | non zero exit on error |
| `write_market(market, dir)` | `Market`, path | the path | `MarketError` |
| `read_market(dir?)` | path or `SYNTHETIC_DATA_DIR` | `Market` | `FileNotFoundError` naming `make data`, `MarketError` |
| `check_market(market)` | `Market` | none | `MarketError` from `validate_market` first, else one listing every bar problem |

**Value sourcing**:

| Action | Value | Source |
|---|---|---|
| generate | every random draw | `default_rng(seed)`, fixed draw order in `generator.py` |
| generate | dates | `sessions(config.start, n_sessions)` |
| generate | `data_version` | `GENERATOR_VERSION` in `config.py` |
| build image | dataset | `services/api/Dockerfile` stage 1, seed 42, into `/data` |
| API start | dataset path | `SYNTHETIC_DATA_DIR` (`/data` in the image, `data/synthetic` locally) |
| D-3 threshold | 20% drawdown | owner ruling in `docs/qa/ac-questions.md` |

**Key invariants**:
- Same seed and config, same locked library versions and CPU architecture, equal frames and meta.
- `generate` never writes, reads the clock, or touches global random state.
- Nothing trades before `listed_from` or after `delisted_on`; listings and delistings are disjoint.
- Any change to a number in `SyntheticConfig`, a *fixed* constant in `generator.py`, or the draw
  order bumps `GENERATOR_VERSION`.
- The data is never committed (pre commit D-6 guard, `.gitignore`).

**Security model**: no secrets, no vendor calls, no real company data. Names are invented.

**Configuration required**:
- `SYNTHETIC_DATA_DIR`: where the API reads the dataset (already set in the image, spec 0001).

**Critical test scenarios** (`engine/tests/synthetic/test_generator.py`, `engine/tests/dataset/test_store_and_sanity.py`):
- Same seed twice gives equal frames and meta; different seeds differ, verifies **AC-1**
- Every bar sane, nothing after `delisted_on`, last bar equals `delisted_on`, verifies **AC-2**
- Drawdown at most −20% at seed 42, and at most −25.9% for seeds 0 to 7, at least 20 delisted with both reasons, verifies **AC-3**
- CLI writes the three files and `read_market` round trips them, verifies **AC-4**
- Momentum correlation positive, and `momentum_coef=0` changes the output, verifies **AC-5**

## Build plan

All tasks are built (feature 7, commit 6985f06); listed so each AC traces to code.

1. `SyntheticConfig` with every number and its validation, `GENERATOR_VERSION`, satisfies **AC-1**
2. Regime schedule, planted bear, market factor and `DEMO-INDEX`, satisfies **AC-3**
3. Ticker attributes, listings, delistings with their price paths, the momentum walk, OHLCV,
   satisfies **AC-2**, **AC-3**, **AC-5**
4. `check_market` (frozen `validate_market` plus D-2 bar checks), satisfies **AC-2**
5. `write_market`, `read_market`, `market_dir`, the CLI, `make data` and the Dockerfile stage,
   satisfies **AC-4**
6. Tests for D-1 to D-3, shape, calendar, listings, tickers and momentum, satisfies **AC-1** to **AC-5**

## Consequences

**Positive**:
- $0, no vendor, no licence, and every number is in two files (`config.py` and the *fixed* constants in `generator.py`).
- A known planted edge lets the research note show the tools can find a real effect.
- The bear and the delistings are planted, so D-3 holds by construction for any seed, not just 42
  (tested on seeds 0 to 7).

**Negative / tradeoffs**:
- Determinism rests on the locked NumPy and Polars versions. A NumPy upgrade may change the
  random stream; then golden files must be regenerated and `GENERATOR_VERSION` bumped.
- The planted momentum term means momentum rules look better here than on real data. The
  research note and README must say so (doc 02 §3).
- The walk forward loop over 1,260 sessions runs in Python (about 0.3 s for seed 42 on a
  laptop). Fine at build time and in tests; still not something to call per request.
- No holidays: the calendar is regular, unlike a real exchange.

**Neutral**:
- Changing any number is a data change: bump `synthetic-1`, rerun `make data`, refresh goldens.

## Follow-up

- [ ] Owner sign-off on the nine assumed decisions above, then the status follows the feature
  lifecycle (`In Progress` until feature 7 is `done`, then `Accepted`).
- Text corrected to match the code (no code change needed): the assumed spec said the bear starts
  between sessions 300 and 700 (code: 302 to 693), listings land in sessions 252 to 1,000 (code:
  252 to 1,008), and delistings in 200 to 1,240 (code: 202 to 1,239). It also left out the regime
  run lengths and weights, the forced recovery, the $0.05 price floor, the volume and wick
  constants, and that momentum is off while an acquired ticker is pinned; all are now listed above.
- [ ] Feature 16 (research note and README) states the planted momentum edge, its size, and that
  it is a per ticker time series effect, not a cross sectional one.
- [ ] DI lane, optional: move the *fixed* constants from `generator.py` into `SyntheticConfig`
  (bump `synthetic-1` only if a value changes).
- [ ] DI lane, optional: have `generate` assert D-3 (drawdown and delisted count) next to
  `check_market`, so a config change that breaks it fails at generation, not only in tests.
