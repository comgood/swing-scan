# engine

## Overview

The `swing-engine` Python package (import name `engine`): all trading logic, meaning data, indicators, rules, exits, the simulator, the random baseline and metrics. The API is a thin wrapper over it, and QA tests it directly through its public entry points.

## Key files

| File | Owns |
|---|---|
| `src/engine/__init__.py` | Package root and `__version__` |
| `tests/test_engine_boundary.py` | Proves the engine imports no web framework |
| `src/engine/live/` | Local only Alpaca loader (feature 14, spec 0010): `python -m engine.live`, writing the same market schema to `data/live`. The HTTP transport is injected, so tests never call a vendor |
| `src/engine/synthetic/` | Seeded synthetic market: `generate(seed) -> Market`, CLI `python -m engine.synthetic --seed 42 --out DIR` (spec 0006) |
| `src/engine/data/store.py` | `read_market()`, `write_market()`, `market_dir()` (reads `SYNTHETIC_DATA_DIR`, default `data/synthetic`) |
| `src/engine/data/sanity.py` | `check_market()`: `validate_market` plus the D-2 bar checks |
| `src/engine/data/fixtures.py` | `load_fixture()` for bar numbered CSVs, `make_market()` from lists (spec 0002 fixture format) |
| `src/engine/api.py` | The use cases: `scan()`, `scan_timed()`, `backtest()`, `warm()` (pins the template columns at startup), and `NotYetImplemented` for 501s. 2 to 6 exit configs go to the private `_trade_lab()` (exit lab, spec 0009) |
| `src/engine/indicators/cache.py` | `IndicatorCache` via `cache_for(market)`: one locked LRU of 64 columns per market; pinned columns are never evicted (spec 0005) |
| `src/engine/rules/compile.py` | `compile_rule()`: the four comparisons, `offset`, `mult`, crosses; any null operand makes the rule false |
| `src/engine/rules/signals.py` | `entry_signals()`: the rising edge plus the chained 10 bar cooldown, shared by the scan and the backtest so their signals match (S-3) |
| `src/engine/exits/` | `Exit` protocol, `Position`, `BarView`, `Fill`, and `step()`, which holds the whole exit precedence (doc 02 §7.2, spec 0007). All six exits (`stop_pct`, `stop_atr`, `target`, `trail_pct`, `close_below_ma`, `time`) come from `build_exits(config, column)`; indicator columns arrive as NumPy arrays via `columns.py` and `BarView.row` |
| `src/engine/sim/` | `run_portfolio()`, the portfolio day loop, and `walk_trade()` plus `make_trade()`, the per trade walker the exit lab reuses (spec 0007). `sim/trade_mode.py`: `entry_points()` and `run_trade_mode()`, one shared entry list walked through every config (spec 0009) |
| `src/engine/metrics/` | Pure trade and curve metric functions (CAGR, max drawdown with the IS peak carried into OOS, Sharpe, exposure, thinning), with the spec's null cases. `metrics/trade_mode.py`: per trade metrics, `edge()`, `best_is()` (IS only), `guides_is()` (`configs[0]` IS trades only), `even_spread()` |
| `src/engine/baseline/random_entries.py` | The random entry baseline: `eligible_pool()` and `sample()`, one `default_rng(sim.seed)` drawing IS then OOS; it never sees a config or an exit type (spec 0009) |

## Commands

```bash
uv run pytest engine/tests     # engine tests only
make data                      # write the seed 42 market to data/synthetic
make data-check                # CI: rebuild twice, same hashes, D-1 to D-3 hold
make load-live                 # local only: Alpaca daily bars into data/live, keys from env
make dev-live                  # local only: the API in live mode on 127.0.0.1, with the web app
```

## Conventions

- Domain modules (BE lane): `indicators/`, `rules/`, `exits/`, `sim/`, `baseline/`, `metrics/`. Infrastructure (DI lane): `data/`, `synthetic/`. Contracts: `engine/contracts/`.
- Public use cases live in `engine.api` (`scan`, `backtest`); acceptance tests call only these, never internal modules.
- Polars for indicators and rules; NumPy and plain Python loops for the simulator. No Numba until profiling demands it (ADR-006).
- Fully typed, checked with `mypy --strict`.

## Gotchas

- Never import `fastapi`, `starlette` or `uvicorn` here; the boundary test fails.
- Every exit runs through one `step(position, bar)` function shared by both loops. Never special case an exit outside it.
- The portfolio loop aligns on session dates, never `row + 1`: a ticker with no bar on a session is not stepped (marked at its last close) and cannot be entered that day. Entries spend only the cash at the previous close; no exit on day d funds an entry on d.
- A ticker whose bars stop early without a `delisted_on` exits `end_of_test` on its last bar, mid window. A live loader must set `delisted_on` for real delistings.
- The per bar path is on a clock (spec 0009 AC-11: 6 configs plus the baseline under 10 s). `BarArrays` holds plain Python lists, `BarView` and `Position` are `slots=True` and deliberately not frozen, and `step()` uses plain comparisons rather than `min()` and `max()`. Keep it that way; `engine/tests/sim/test_lab_budget.py` is the check.
- The random baseline seed default changes only with an ADR.
- Change a `SyntheticConfig` default and bump `GENERATOR_VERSION` with it: `engine/tests/synthetic/test_generator.py` pins the defaults by digest, so it fails until both move. Otherwise every published number shifts under the same `data_version`.
- Alpaca's free Basic plan has no SIP history: `feed=sip` answers 403, so the loader reads the IEX feed. IEX is a small share of real volume, so volume rules (`vol_ratio`, `avg_volume`) are not comparable to a full tape.
- Rule compilation never uses `eval` or `exec`.
- Tests for `data/` live in `engine/tests/dataset/`, because `.gitignore` ignores every folder named `data/`.

## Related specs

- [0001 stack & architecture](../docs/specs/0001-stack-architecture/index.md)
- [0002 contracts & data model](../docs/specs/0002-contracts-data-model/index.md)
- [0005 template scan](../docs/specs/0005-template-scan/index.md) (indicators, rules, entry signals)
- [0006 synthetic market](../docs/specs/0006-synthetic-market/index.md)
- [0007 portfolio backtest core](../docs/specs/0007-portfolio-backtest-core/index.md) (exits, `step()`, the simulator, metrics)
- [0009 exit lab](../docs/specs/0009-exit-lab/index.md) (trade mode, the random baseline, edge)

_Drafted by /audit from the repo, worth a quick human pass. Edit freely: once a line stops matching this draft, later runs treat it as curated and will flag rather than overwrite it._
