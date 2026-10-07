# 0006 · Synthetic market

**Status**: Assumed
**Date**: 2026-10-07
**Authorized by**: owner's standing instruction to the DI lane agent, during /develop (lane agents cannot ask, so an owed decision is built as an assumed spec)

## Owed decision

Doc 02 (A2, §3, §5.1, D1/D2) and spec 0001 fix the shape of the synthetic market (500 invented tickers, about 5 years, regimes, sectors, fat tails, a documented planted momentum term, about 5% delistings with at least 20, about 5% mid sample listings, adjusted prices only, `DEMO-INDEX`, `python -m engine.synthetic --seed 42 --out /data`, `SYNTHETIC_DATA_DIR`). No doc fixes the numbers inside it: the calendar, the start date, how regimes are scheduled, how the bear segment is guaranteed, the exact planted momentum term, how `DEMO-INDEX` is built, the ticker and name scheme, the delisting reasons and their price paths, the price precision, and the `data_version` string. These decide values the D-1 to D-3 checks and every later scan and backtest read.

## Assumption built on

- **Entry point.** `engine.synthetic.generate(seed: int = 42, config: SyntheticConfig | None = None) -> Market`. Pure: no I/O, no clock, no global random state. It validates its own output (`engine.data.check_market`) before returning. The CLI `python -m engine.synthetic --seed 42 --out DIR` writes `bars.parquet`, `securities.parquet` and `meta.json` into `DIR` (doc 02 §5.1). `engine.data.read_market(DIR)` loads and validates them; `engine.data.market_dir()` reads `SYNTHETIC_DATA_DIR` (default `data/synthetic`).
- **Randomness.** One `numpy.random.default_rng(seed)` (PCG64), drawn in a fixed order. Prices are rounded to 4 decimals and volumes to whole shares, which keeps output identical run to run and absorbs last bit float noise across machines.
- **Calendar.** 1,260 sessions, every weekday (Monday to Friday) from Mon 2021-01-04, no holidays (the same weekday rule as the fixture calendar in spec 0002). The end date is fixed, never "today", so a seed always gives the same dates.
- **Regimes.** The market factor runs through a seeded sequence of regimes: `bull` (drift +0.06% a day, vol 0.9%), `chop` (0, 1.1%), `bear` (−0.15%, 1.9%), `recovery` (+0.10%, 1.4%). The schedule always holds exactly one planted bear segment of 120 to 180 sessions starting between session 300 and 700, with the other sessions split into seeded runs of the remaining regimes. Inside the planted bear, the noise is demeaned and the drift set so its total log return is a seeded value in [−0.45, −0.30]. That guarantees `DEMO-INDEX` closes at least 25% below its running peak (`exp(−0.30) − 1 ≈ −25.9%`), above the owner's D-3 ruling of 20% (docs/qa/ac-questions.md).
- **`DEMO-INDEX`.** The market factor itself: level 1,000 × exp(cumulative market log return), with open, high, low and volume built like any ticker's. It is a row in `securities.parquet` (sector `Index`, never delisted) and `meta.benchmark`.
- **Sectors.** 10 invented sectors (`Technology`, `Healthcare`, `Financials`, `Energy`, `Industrials`, `Consumer`, `Materials`, `Utilities`, `Telecom`, `Real Estate`), tickers assigned round robin after a seeded shuffle. Each sector has its own daily factor (vol 0.7%).
- **Ticker returns.** Daily log return = beta × market + sector factor + idiosyncratic shock + planted momentum term. Beta is seeded in [0.6, 1.6]. The idiosyncratic shock is Student t with 4 degrees of freedom, scaled to a seeded vol in [1.0%, 3.0%] (fat tails).
- **Planted momentum term (documented edge).** Each session adds `0.10 × clip(L63, −0.5, 0.5) / 63` to a ticker's expected log return, where `L63` is its own log return over the previous 63 sessions (zero until it has 63 sessions of its own history). Strong recent winners keep drifting up a little, so momentum rules have a real, planted edge. The published research note must say so (doc 02 §3).
- **Bars.** Open = previous close × exp(0.3 × today's return + a small gap shock). High and low extend past max(open, close) and min(open, close) by a half normal wick. Volume = a seeded base (log normal, median about 1M shares) × exp(normal noise) × a spike factor that grows with the size of the move. After rounding, high and low are clamped so `low ≤ min(open, close)` and `high ≥ max(open, close)` hold exactly, and `volume ≥ 1`.
- **Starting prices.** Log normal around $40, clipped to [$2, $400], so the `close > 5` template filter has work to do.
- **Listings.** `round(5% × 500) = 25` tickers list mid sample, at a seeded session in [252, 1,000]; `listed_from` is their first bar date.
- **Delistings.** `max(20, round(5% × 500)) = 25` tickers, disjoint from the mid sample listings, delist at a seeded session in [200, 1,240]. Their last bar is `delisted_on`. 60% are `bankruptcy` (a planted slide: an extra −0.6% a day over their last 40 sessions) and 40% are `acquired` (a +25% to +40% jump on the announcement session 20 sessions before the last bar, then a near flat drift). Nothing trades after `delisted_on`.
- **Tickers and names.** 4 letter consonant vowel consonant vowel symbols (for example `BALO`), drawn without replacement, sorted alphabetically for output. Names are the capitalized symbol plus a seeded suffix (`Labs`, `Holdings`, `Systems`, ...). They are invented and carry no real company data.
- **Meta.** `data_mode="synthetic"`, `seed`, `data_version="synthetic-1"` (bump on any change to the model), `start`, `end`, `n_tickers=500`, `survivors_only=False`, `benchmark="DEMO-INDEX"`.
- **Sanity checks.** `engine.data.check_market(market)` runs the frozen `validate_market` plus the D-2 bar checks: `low ≤ min(open, close)`, `high ≥ max(open, close)`, `volume > 0`, prices positive and finite, no bar before `listed_from` or after `delisted_on`. It raises `MarketError` listing every problem.
- **Image.** `services/api/Dockerfile` stage 1 runs `python -m engine.synthetic --seed 42 --out /data`; stage 2 copies `/data` and sets `SYNTHETIC_DATA_DIR=/data` (spec 0001). `make data` writes `data/synthetic/` locally (gitignored).

## Code area

`engine/src/engine/synthetic/`, `engine/src/engine/data/` (`sanity.py`, `store.py`), `engine/tests/data/`, `engine/tests/synthetic/`, `engine/pyproject.toml` (adds `numpy`), `services/api/Dockerfile`, `Makefile` (`data` target).

## Requirements

- D-1: the same seed gives identical bars, securities and meta, frame for frame.
- D-2: every bar has `low ≤ min(open, close)`, `high ≥ max(open, close)`, `volume > 0`, and no ticker has bars after its `delisted_on`.
- D-3: at least one bear segment (the benchmark closes at least 20% below its running peak) and at least 20 delisted tickers.

## Ratify

This decision was recorded by /develop, not deliberated. Run `/architect synthetic market`
to deliberate and ratify it. Until then it stays flagged as an owed decision; it does not block marking the feature `done`.
