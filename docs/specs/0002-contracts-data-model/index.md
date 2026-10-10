# 0002. Freeze the shared contracts as Pydantic models in the engine

**Date**: 2026-10-07
**Status**: Accepted

## Summary

This spec freezes the shapes every lane builds against: the rule JSON, the exit configs, the backtest settings, every API request and response, the stored data files, and the format of the hand checked test fixtures. They are written once as Pydantic models (Python classes that validate data) in `engine/contracts/`. The OpenAPI file, the TypeScript types, and the mock responses are all generated from those models, so nothing can drift. The real `/scan` and `/backtest` routes validate requests fully from day one and answer 501 (not implemented) until the engine lands. The web app runs against the mocks through MSW (Mock Service Worker, a library that intercepts fetch calls). The work ends with your sign offs SO-2 and SO-3 and the `contracts-v1` git tag.

## Requirements

**User stories**:
- As the FE lane, I want generated types and realistic mock responses for every endpoint so that I can build the whole workspace before the engine exists.
- As the BE lane, I want one set of request and response models with the validation rules already in them so that the engine only implements behaviour, never shape.
- As QA, I want the public use case signatures, the error shape and the fixture format fixed so that I can write acceptance tests from the criteria and contracts alone.
- As the owner, I want a fixture format I can check by hand, bar by bar, so that approving oracles takes minutes per test, not hours.

**Acceptance criteria**:
- **AC-1**: `engine/contracts/` holds Pydantic v2 models for every shape in *Feature design*. `make openapi` writes `contracts/openapi.json` (sorted keys, no server URL) with `info.version` equal to `CONTRACT_VERSION` (`"1.0.0"`), and `make gen-client` regenerates `packages/api-client`, which typechecks under `strict`. CI reruns both and fails on any diff.
- **AC-2**: A bad rule returns 422 in FastAPI's default body, where `loc` points at the bad field and `ctx` carries the allowed range (`min`, `max`) or the allowed values. This covers every R-6 case: an unknown indicator, a missing or out of range `n` for that indicator, an `n` given to a price field, `offset` outside 0 to 20, `mult` outside 0.1 to 10, 0 or 9 conditions, and an unknown or missing `kind` tag. For an `n` error, `loc` ends at `"n"`, not at the operand. A unit test proves that no ranged field uses Pydantic's `ge`/`le`, because those report only the side that failed.
- **AC-3**: A bad exit setup returns 422 with a path and the allowed range or values: 0 or 7 configs (X-2), any exit param out of range, a duplicate exit `type` inside one config (the path points at the duplicate), duplicate config names, or a name outside 1 to 40 characters after trimming.
- **AC-4**: Bad backtest settings return 422 with a path and range: `max_positions`, `slippage_bps`, `horizon_bars` or `seed` out of range, or `start` not before `end`. A malformed `as_of`, `start` or `end` (not `YYYY-MM-DD`) returns 422.
- **AC-5**: Every request model round trips from canonical input. `Model.model_validate_json(m.model_dump_json())` equals `m`, and dumping again gives byte identical JSON. The canonical wire form always writes every field, defaults included, in model field order. Input that isn't canonical (for example `rs` without `n`) becomes canonical on the first parse (`n: 126` filled in) and is stable from then on.
- **AC-6**: `POST /api/v1/scan` and `POST /api/v1/backtest` validate the full request. Invalid input returns 422. Valid input returns 501 with `{"detail": "..."}` naming the scope feature that will implement it (8 or 9). `GET /api/v1/indicators` and `GET /api/v1/templates` return real data. `GET /api/v1/meta` returns `contract_version` and `data: null` until scope feature 7 loads data.
- **AC-7**: One indicator registry (`INDICATOR_SPECS`) drives both validation and `GET /indicators`. It lists all 14 indicators with `windowed`, `n_min`, `n_max` and `n_default`. When `n` is omitted, `rs` gets 126. Every other windowed indicator requires `n`.
- **AC-8**: `GET /templates` returns exactly the two templates from doc 02 §5.2 (`breakout_52w`, `pullback_ema21`). Each validates as a `Rule` and contains a visible `close > 5` condition (R-10).
- **AC-9**: `structure_key(rule)` is equal for rules that differ only in numbers (`n`, `offset`, `mult`, `value`) or name. It differs when an indicator, an operator, the right operand's kind, or the condition count differs (R-9). `pair_key(rule, config)` is equal exactly when the rule and config are identical, ignoring names and the order of exits.
- **AC-10**: `BARS_SCHEMA`, `SECURITIES_SCHEMA` and `DataMeta` are defined, and `validate_market(market)` raises a clear error for any of these: a missing or extra column, a wrong dtype, a duplicate `(ticker, date)`, bars not sorted by `(ticker, date)`, `delist_reason` set without `delisted_on` (or the reverse), a bars ticker missing from securities, or the benchmark ticker missing from bars.
- **AC-11**: `engine.data.fixtures.load_fixture(path)` turns an oracle CSV in the *Fixture format* below into a `Market`. Bar 1 is 2020-01-02 on a weekday only calendar. Listing and delisting are inferred from each ticker's first and last bar, and the optional sidecar overrides them. `make_market(...)` builds the same `Market` from Python lists for long fixtures (B-14 needs 261 bars).
- **AC-12**: `make mocks` runs a seeded script that writes every file in the *Mock set* below as real models with internally consistent numbers. Each 422 mock is produced by sending a bad request through the real app with `TestClient`. CI reruns it, validates every file against its model, and fails on any diff.
- **AC-13**: `apps/web` serves every mock through MSW handlers. These are on in the browser when `NEXT_PUBLIC_API_MOCK=1` and on by default in Vitest. A Vitest test calls `/scan` through the generated openapi-fetch client and receives the typed scan mock. A test can switch a handler to its 422 mock, or to a delayed response (U-5, U-7).
- **AC-14**: The response rules hold in the schema and in the mocks. An undefined number is `null`, never NaN or Infinity. Every model inherits a shared base config with `allow_inf_nan=False`, so building a model with a non finite float raises. Pydantic's default would otherwise write it as `null` without any error. Dates are `YYYY-MM-DD`. Percent values are percent numbers in fields ending `_pct`. `equity` and `benchmark` have at most 500 points, and the trade lists at most 2,000, with `*_total` and `*_truncated` beside them.
- **AC-15**: `engine/contracts/` imports only the standard library, `pydantic` and `polars` (the existing boundary test stays green). `services/api` routes use the contract models directly as request and response models, and `engine.api.scan(request, market)` and `engine.api.backtest(request, market)` exist as stubs with these signatures.
- **AC-16**: The owner signs off SO-2 (contracts, mocks) and SO-3 (fixture format) in the PR, and the merge commit is tagged `contracts-v1`.

## Decision

**Chosen option**: Option 1: Pydantic models in `engine/contracts/` as the single source, with OpenAPI, TypeScript types and mocks all generated, and MSW in the web app (see `rationale.md`).

Write every shared shape once as a Pydantic v2 model in `engine/contracts/`, generate everything else from it, and check in CI that every generated file is current.

**Implementation skills**: `pydantic` (`pydantic/skills`, `.agents/skills/pydantic/`) · `fastapi` (`fastapi/fastapi`, `.agents/skills/fastapi/`) · `python-testing-patterns` (`wshobson/agents`, `.claude/skills/python-testing-patterns/`) · `pnpm` (`antfu/skills`, `.agents/skills/pnpm/`)

## Feature design

### Module layout and ownership

| Path | What | Lane |
|---|---|---|
| `engine/src/engine/contracts/__init__.py` | `CONTRACT_VERSION = "1.0.0"`, public re exports | BE |
| `engine/contracts/_errors.py` | `bounded()` helper and custom 422 errors (see *Validation errors*) | BE |
| `engine/contracts/indicators.py` | `IndName`, `IndicatorSpec`, `INDICATOR_SPECS` | BE |
| `engine/contracts/rule.py` | `IndOperand`, `ValueOperand`, `Condition`, `Rule`, `TEMPLATES` | BE |
| `engine/contracts/exits.py` | the six exit variants, `Exit` union, `ExitConfig` | BE |
| `engine/contracts/scan.py`, `backtest.py`, `meta.py` | requests, responses, `Assumptions`, metrics, `Trade`, `Warning` | BE |
| `engine/contracts/trial.py` | `structure_key`, `pair_key`, `entries_hash` | BE |
| `engine/contracts/market.py` | `BARS_SCHEMA`, `SECURITIES_SCHEMA`, `DataMeta`, `Market`, `validate_market` | BE (DI reviews) |
| `engine/src/engine/api.py` | `scan(request, market)`, `backtest(request, market)`, stubs raising `NotImplementedError` | BE |
| `engine/src/engine/data/fixtures.py` | `load_fixture`, `make_market` | DI |
| `services/api/src/api/routes/` | the five routes, the 501 mapping | BE |
| `scripts/make_mocks.py` | the seeded mock builder | BE |
| `contracts/openapi.json`, `contracts/mocks/*.json` | generated, committed | BE |
| `packages/api-client/` | generated types + `createClient` wrapper | BE generates, FE consumes |
| `apps/web/src/mocks/` | MSW handlers and browser/node setup | FE |
| `Makefile`, `.github/workflows/ci.yml` | `openapi`, `gen-client`, `mocks` targets and their CI diff checks | DI |

There are no separate JSON Schema files. `contracts/openapi.json` carries every component schema.

### Data model sketch

**Stored files** (Polars schema constants, checked by `validate_market`):

| Entity | Key | Fields (type, required unless `?`) | Relationships and rules |
|---|---|---|---|
| `bars.parquet` | PK (`ticker`, `date`), sorted by it | `ticker` String · `date` Date · `open` `high` `low` `close` Float64 (adjusted) · `volume` Float64 | N:1 to securities. The benchmark is an ordinary ticker here |
| `securities.parquet` | PK `ticker` | `name` String · `sector` String · `listed_from` Date · `delisted_on` Date? · `delist_reason` String? | 1:N to bars. `delist_reason` is null exactly when `delisted_on` is null |
| `meta.json` → `DataMeta` | one per dataset | `data_mode` `"synthetic"\|"live"` · `seed` int? (required when synthetic) · `data_version` str · `start` date · `end` date · `n_tickers` int (excluding the benchmark) · `survivors_only` bool · `benchmark` str | `benchmark` names a ticker in bars, which is excluded from the scan, backtest, `rs` and random baseline universe |
| `Market` (frozen dataclass, in memory) | | `bars` DataFrame · `securities` DataFrame · `meta` DataMeta | Passed into every use case. The API loads it once at import |

**Rule** (all models inherit `ContractModel`, a base with `extra="forbid"` (an unknown key is a 422) and `allow_inf_nan=False`. Every discriminator field (`kind`, `type`, `mode`) is a required `Literal` with no default, so the generated TypeScript keeps it required and narrowing works):

| Model | Fields |
|---|---|
| `IndOperand` | `kind: "ind"` · `ind: IndName` · `n: int?` (declared after `ind`, and checked by a field validator on `n` that reads `ind`) · `offset: int` 0 to 20 (0) · `mult: float` 0.1 to 10 (1.0) |
| `ValueOperand` | `kind: "value"` · `value: float` (finite) |
| `Condition` | `left: IndOperand` · `op: ">" \| "<" \| ">=" \| "<=" \| "crosses_above" \| "crosses_below"` · `right: IndOperand \| ValueOperand` (discriminator `kind`) |
| `Rule` | `name: str` 1 to 40 after trim · `conditions: list[Condition]` 1 to 8, AND only |

**Indicator registry** (`IndicatorSpec`: `name`, `label`, `windowed`, `n_min`, `n_max`, `n_default?`):

| Indicators | `n` rule |
|---|---|
| `open`, `high`, `low`, `close`, `volume` | not windowed, `n` must be null |
| `sma`, `ema`, `atr`, `highest`, `lowest`, `avg_volume`, `ret` | required, 2 to 252 |
| `rsi` | required, 2 to 50 |
| `rs` | optional, 2 to 252, default 126 (the validator fills it in) |

**Exits** (`ExitConfig`: `name` 1 to 40, `exits` 1 to 6, discriminator `type`, no duplicate type):

| Variant | Params (default, range) |
|---|---|
| `{"type":"stop_pct"}` | `pct` 8 (1 to 30) |
| `{"type":"stop_atr"}` | `k` 2 (0.5 to 6), `n` 14 (2 to 50) |
| `{"type":"target"}` | `pct` 15 (1 to 100) |
| `{"type":"trail_pct"}` | `pct` 10 (2 to 30) |
| `{"type":"close_below_ma"}` | `ma` `"sma"\|"ema"` (`"sma"`), `n` 21 (5 to 200) |
| `{"type":"time"}` | `bars` 10 (1 to 120) |

**Requests**:

| Model | Fields |
|---|---|
| `ScanRequest` | `rule: Rule` · `as_of: date?` (default: the last session) |
| `SimParams` | `max_positions` 1 to 20 (10) · `slippage_bps` 0 to 50 (10) · `horizon_bars` 5 to 252 (60) · `seed` 0 to 2³¹−1 (42) · `start: date?` · `end: date?` (`start < end` when both are set) |
| `BacktestRequest` | `rule: Rule` · `configs: list[ExitConfig]` 1 to 6, names unique · `sim: SimParams` (all defaults if omitted). `configs[0]` is the baseline config |

**Responses**:

| Model | Fields |
|---|---|
| `ScanRow` | `ticker` · `close` · `chg_pct?` · `vol_ratio?` · `operands: list[float]` (aligned to `columns`, never null, because a hit row is valid) · `new_today: bool` |
| `ScanResponse` | `as_of: date` · `columns: list[str]` · `rows: list[ScanRow]` (≤ 500) |
| `Trade` | `ticker` · `entry_date` · `entry_price` · `exit_date` · `exit_price` · `return_pct` · `bars_held` · `exit_reason` · `r_multiple?` · `mae_pct` (≤ 0) · `mfe_pct` (≥ 0) · `mae_r?` · `mfe_r?` · `segment: "is"\|"oos"` |
| `ExitReason` | `stop_pct` · `stop_atr` · `trail_pct` · `target` · `time` · `ma` · `delisted` · `horizon` · `end_of_test` |
| `Point` | `date` · `value` |
| `PortfolioMetrics` | `n_trades` · `cagr_pct?` · `max_dd_pct?` · `sharpe?` · `win_rate_pct?` · `avg_win_pct?` · `avg_loss_pct?` · `expectancy_pct?` · `expectancy_r?` · `profit_factor?` · `avg_bars_held?` · `exposure_pct?` |
| `BenchmarkMetrics` | `cagr_pct?` · `max_dd_pct?` |
| `TradeMetrics` | `n_trades` · `distinct_weeks` · `win_rate_pct?` · `avg_win_pct?` · `avg_loss_pct?` · `expectancy_pct?` · `expectancy_r?` · `expectancy_per_bar_pct?` · `profit_factor?` · `avg_bars_held?` · `avg_mae_pct?` · `avg_mfe_pct?` · `horizon_exit_pct?` |
| `EdgeMetrics` | `expectancy_pct?` · `expectancy_r?` · `expectancy_per_bar_pct?` · `win_rate_pct?` (each strategy minus random) |
| `PortfolioSplit`, `BenchmarkSplit`, `TradeSplit`, `EdgeSplit` | Four concrete classes (not one generic, which would give ugly TS names), each `is_` (JSON key `is`, via `Field(alias="is")` with `populate_by_name=True`) · `oos` |
| `ConfigRow` | `name` · `strategy: TradeSplit` · `random: TradeSplit` · `edge: EdgeSplit` |
| `Entries` | `count` · `is_count` · `oos_count` · `distinct_weeks` · `hash` · `random_is_count` · `random_oos_count` (one seeded draw. X-10 requires these to equal `is_count` and `oos_count`) |
| `BestIs` | One optional `int` per ranked metric (`win_rate_pct`, `avg_win_pct`, `avg_loss_pct`, `expectancy_pct`, `expectancy_r`, `expectancy_per_bar_pct`, `profit_factor`, `avg_mae_pct`, `avg_mfe_pct`, `horizon_exit_pct`). Null when no config has an IS value |
| `Guides` | `winner_mae_p75_pct?` · `winner_mae_p90_pct?` · `mfe_median_pct?` |
| `Trial` | `structure_key` · `pair_keys: list[str]` (one per config, same order) |
| `Warning` | `code: WarningCode` · `config_index: int?` · `message: str` |
| `WarningCode` | `no_entries` · `horizon_exits_over_10pct` · `trades_truncated` |
| `Assumptions` | `fill_model: "signal_close_entry_next_open"` · `slippage_bps` · `commission_bps` (0) · `sizing: "equal_weight"\|"unit_notional"` · `max_positions?` · `entry_rising_edge: true` · `cooldown_bars` (10) · `cooldown_basis: "signal"` · `no_last_bar_entry: true` · `same_ticker_overlap: bool` · `horizon_bars?` · `seed?` · `configs: list[ExitConfig]` · `baseline_config_index` (0) · `delisting_rule: "exit_last_close"` · `oos_start` · `oos_fraction` (0.3) · `data_mode` · `data_version` · `data_seed?` |
| `PortfolioResult` | `mode: "portfolio"` · `assumptions` · `oos_start` (always equal to `assumptions.oos_start`) · `trial` · `warnings` · `metrics: PortfolioSplit` · `benchmark_metrics: BenchmarkSplit` · `equity: list[Point]` (≤ 500) · `benchmark: list[Point]` (≤ 500) · `trades: list[Trade]` (≤ 2,000) · `trades_total` · `trades_truncated` |
| `TradeLabResult` | `mode: "trade"` · `assumptions` · `oos_start` · `trial` · `warnings` · `entries` · `rows: list[ConfigRow]` · `best_is: BestIs` · `guides_is: Guides` · `baseline_trades: list[Trade]` (≤ 2,000) · `baseline_trades_total` · `baseline_trades_truncated` |
| `BacktestResponse` | `PortfolioResult \| TradeLabResult`, discriminator `mode` |
| `MetaResponse` | `contract_version` · `data: DataMeta?` · `oos_start: date?` |
| `TemplateOut` | `id` · `name` · `description` · `rule: Rule` |

### State transitions

None. Every request is stateless. The only lifecycle is the contract's own version: `1.0.0` at `contracts-v1`. Additive optional fields bump the minor version. A breaking change bumps the major version and the tag to `contracts-v2`, and is allowed only before the Day 4 checkpoint (doc 02 §15.6).

### API surface

All routes sit under `/api/v1`. All are public (no auth).

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/health` | GET | none | `status`, `data_mode`, `version` | public | none (exists) |
| `/meta` | GET | none | `MetaResponse` (`data` null until feature 7) | public | none |
| `/indicators` | GET | none | `list[IndicatorSpec]` | public | none |
| `/templates` | GET | none | `list[TemplateOut]` | public | none |
| `/scan` | POST | `ScanRequest` | `ScanResponse` (feature 8) | public | 422 invalid, 501 until feature 8 |
| `/backtest` | POST | `BacktestRequest` | `BacktestResponse` tagged by `mode` (feature 9) | public | 422 invalid (including 7 configs), 501 until feature 9 |

Two data dependent checks arrive later, in the same 422 shape with fixed types. Feature 8 adds `as_of_not_session` (`loc` `["body","as_of"]`, `ctx` `{min, max}` as the data's first and last session). Feature 9 adds `range_outside_data` (`loc` at `start` or `end`, same `ctx`).

The 501 is raised by a dedicated `NotYetImplemented(feature: int)` exception from the `engine.api` stubs, and only that type maps to 501. A stray `NotImplementedError` from a real bug stays a 500.

**Validation errors.** The body is FastAPI's default `{"detail": [{"type", "loc", "msg", "input", "ctx"}]}` (spec 0001). Every ranged number and every bounded list uses the shared `bounded(min, max)` helper. It puts `minimum`/`maximum` (or `minItems`/`maxItems`) into the JSON Schema, and on failure raises `PydanticCustomError("out_of_range", "must be between {min} and {max}", {"min": .., "max": ..})`. A bad literal keeps Pydantic's `literal_error` (`ctx.expected`), and a bad tag keeps `union_tag_invalid` (`ctx.expected_tags`). A missing tag keeps `union_tag_not_found`. The `n` check runs as a field validator on `n` (so `loc` ends at `"n"`) and raises `out_of_range` with that indicator's bounds, `n_required` when it's missing, or `n_not_allowed` for a price field. Duplicates raise `duplicate_exit_type` or `duplicate_config_name` at the duplicate's index. The web app maps `loc` to the builder row or exit field (U-7).

**Use cases** (the public engine API that QA calls): `engine.api.scan(request: ScanRequest, market: Market) -> ScanResponse` and `engine.api.backtest(request: BacktestRequest, market: Market) -> BacktestResponse`. Routes hold one `Market`, loaded at import once feature 7 exists. Until then the stubs raise `NotYetImplemented`, which routes map to 501.

### Value sourcing

| Action | Value produced / displayed | Source |
|---|---|---|
| scan | `as_of` | `ScanRequest.as_of`, else the last session in `market.bars` |
| scan | `columns` | Derived from the rule: one label per distinct `IndOperand` (distinct by `ind`, `n`, `offset`, `mult`) in order of first appearance, with value operands excluded. The grammar is `[{mult}×]{ind}[({n})][[{offset}]]`. `{mult}×` appears only when mult ≠ 1, written as Python's shortest float repr (`1.5`, `0.25`). `({n})` appears whenever `n` is set, including the filled in `rs(126)`. `[{offset}]` appears only when offset > 0. Golden cases: `close`, `highest(252)[1]`, `1.5×avg_volume(50)`, `ema(21)[5]`, `1.01×ema(21)`, `rs(126)` |
| scan | `chg_pct` | `(close / previous close − 1) × 100` from bars. Null on a ticker's first bar |
| scan | `vol_ratio` | `volume / avg_volume(50)` from the indicator cache. Null in warm up |
| scan | row set and order | Alive, non benchmark tickers whose rule is valid and true on `as_of` (S-1). Sorted with `new_today` first, then ticker A to Z. At most 500 rows, because the universe is 500 tickers |
| scan | `new_today` | The entry signal on `as_of`, **including the 10 bar cooldown**, with only the last bar term ignored (doc 02 §6). **Ruling:** doc 01 S-3 says "raw signals, before cooldown and last bar filtering", but this spec freezes doc 02's version, and QA writes S-3 to it (see Follow-up) |
| backtest | `mode` | Derived from `len(configs)`: 1 means `portfolio`, 2 to 6 means `trade`. No request field picks the mode, and a single config trade lab can't be requested |
| backtest | baseline config | `configs[0]`, echoed as `assumptions.baseline_config_index = 0` |
| backtest | run range | `sim.start` / `sim.end`, defaulting to the data's first and last session |
| backtest | `oos_start` | The first date of the last 30% of sessions in the run range (`oos_fraction` 0.3, doc 02 §7.1) |
| backtest | `segment` per trade | The entry date compared with `oos_start`. A trade cut at `end_of_test` still counts in its entry segment |
| backtest | `assumptions.sizing`, `same_ticker_overlap`, `max_positions`, `horizon_bars`, `seed` | Portfolio mode: `equal_weight`, `false`, `sim.max_positions`, `null`, `null`. Trade mode: `unit_notional`, `true`, `null`, `sim.horizon_bars`, `sim.seed` (doc 02 §7.3) |
| backtest | `equity`, `benchmark` values | Both indexed to 100 at the first session of the run range. Equity is marked at each close, with cash at 0% |
| backtest | `return_pct` | `(exit_price / entry_price − 1) × 100`, where both prices are fills that already include slippage |
| backtest | `mae_pct`, `mfe_pct` | From the entry fill to the min low (MAE, ≤ 0) and max high (MFE, ≥ 0) over the bars held, with the exit bar limited per doc 02 §7.2 (exit at open: open only. Intraday stop: MAE at the stop level, MFE at the open. Intraday target: MFE at the target level, MAE at the open. Close based exits: the full bar) |
| backtest | R (`r_multiple`, `mae_r`, `mfe_r`, `expectancy_r`) | `R = entry_fill − initial_stop`, where `initial_stop` is the highest (tightest) stop level at entry among the config's stops. A trailing stop's starting level is `fill × (1 − p)`. The value is `move / R` |
| backtest | `exit_reason` tie | When two stops share the winning level, report the first in the order `stop_pct`, `stop_atr`, `trail_pct` |
| backtest | `trial.structure_key` | `sha256` hex of the canonical JSON array `[[left.ind, op, right.ind or "value"], ...]` (numbers and names stripped, count implied by length) |
| backtest | `trial.pair_keys[i]` | `sha256` hex of canonical JSON `{"rule": conditions, "config": exits sorted by type}`, names excluded. Canonical means `model_dump(mode="json")`, `sort_keys=True`, `separators=(",", ":")` |
| backtest | `entries.hash` | `sha256` hex of the sorted `"ticker|entry_date"` lines |
| backtest | `distinct_weeks` | The count of distinct ISO `(year, week)` pairs over entry dates |
| backtest | `expectancy_r`, `r_multiple`, `mae_r`, `mfe_r` | Only when the config has a stop (`stop_pct`, `stop_atr` or `trail_pct`). Otherwise null, so the UI shows "n/a" (X-4). A trade with no stop level (e.g. `stop_atr` entered during ATR warm up) has a null `r_multiple`; `expectancy_r` averages only the trades that have one, and is null when none does (owner ruling 2026-10-09) |
| backtest | `edge.*` | `strategy` minus `random` per segment. Null when either side is null |
| backtest | `best_is` | One `BestIs` field per metric, holding the config index of the best non null IS value, ties to the lowest index. Higher is better: `win_rate_pct`, `avg_win_pct`, `avg_loss_pct` (closer to 0), `expectancy_pct`, `expectancy_r`, `expectancy_per_bar_pct`, `profit_factor`, `avg_mae_pct` (closer to 0), `avg_mfe_pct`. Lower is better: `horizon_exit_pct`. Never ranked: `n_trades`, `distinct_weeks`, `avg_bars_held`. OOS is never ranked (X-3) |
| backtest | `guides_is` | Computed from `configs[0]`'s strategy trades with `segment = "is"` only (X-5). `winner_mae_p75_pct` and `winner_mae_p90_pct` are percentiles (NumPy linear interpolation) over winners (`return_pct > 0`) on adverse depth (`-mae_pct`), reported back as signed `mae_pct`, so p90 is deeper than p75: p90 ≤ p75 ≤ 0 (owner ruling 2026-10-09). `mfe_median_pct` is the median `mfe_pct` over all baseline IS trades. Each is null when its set is empty |
| backtest | `entries.random_*_count` | The single seeded random draw (`sim.seed`), stratified to the strategy's IS and OOS counts (doc 02 §7.4) |
| backtest | warnings | `no_entries` when there are zero entry signals. `horizon_exits_over_10pct` per config whose `horizon_exit_pct` is over 10 (X-9). `trades_truncated` when a trade list hits its cap |
| backtest | `equity`, `benchmark` | Daily values, evenly strided to ≤ 500 points, always keeping the first point, the last point and `oos_start` |
| backtest | `trades` / `baseline_trades` | Sorted by entry date, then ticker. Over 2,000, keep 2,000 evenly spread through that order (indices `round(i × (total − 1) / 1999)`), so the IS and OOS trades both stay visible. `*_total` is the full count, and metrics always use every trade |
| backtest | `assumptions.data_*` | `market.meta` |
| meta | `contract_version` | `CONTRACT_VERSION` |
| meta | `data`, `oos_start` | `market.meta` and the full range split. Both null until feature 7 |
| indicators | every row | `INDICATOR_SPECS` |
| templates | every row | `TEMPLATES` (doc 02 §5.2 verbatim) |
| web | mock vs real API | `NEXT_PUBLIC_API_MOCK` (browser). Vitest sets MSW on by default |

### Metric definitions (frozen so QA and BE compute the same thing)

| Metric | Definition |
|---|---|
| win | A trade with `return_pct > 0`. A 0% trade is a loss for `win_rate_pct` and `avg_loss_pct` |
| `win_rate_pct` | wins / `n_trades` × 100 |
| `avg_win_pct`, `avg_loss_pct` | Mean `return_pct` of wins, and of the others (≤ 0) |
| `expectancy_pct` | Mean `return_pct`. `expectancy_r` is the mean `r_multiple` (null without a stop) |
| `expectancy_per_bar_pct` | Sum of `return_pct` / sum of `bars_held` |
| `profit_factor` | Sum of wins / abs(sum of losses). Null when there are no losses or no trades |
| `avg_bars_held`, `avg_mae_pct`, `avg_mfe_pct` | Means over the segment's trades |
| `horizon_exit_pct` | Trades with `exit_reason = horizon` / `n_trades` × 100 |
| `cagr_pct` | `(last / first) ^ (365.25 / calendar days) − 1`, × 100, over the segment's equity |
| `max_dd_pct` | The largest peak to trough fall of equity in the segment, as a number ≤ 0 |
| `sharpe` | Mean / standard deviation (ddof 1) of daily equity returns × √252, with a risk free rate of 0. Null with fewer than 2 returns or zero deviation |
| `exposure_pct` | Sessions holding at least one position / sessions in the segment × 100 |

Every metric with no trades (or no sessions) in its segment is null, except `n_trades` and `distinct_weeks`, which are 0.

### Fixture format (SO-3)

For hand checked oracle fixtures in `tests/oracle/fixtures/`, and any other test that wants a small CSV:

- **File** `<name>.csv`, UTF-8. The header is exactly `ticker,bar,open,high,low,close,volume`. Lines starting with `#` are comments (use them for the hand math). Plain decimals with `.`, no thousands separators.
- **`bar`** is a 1 based integer. Each ticker's bars must be contiguous (no gaps) and may start after bar 1 (a later listing).
- **Calendar**: bar k maps to the k-th weekday counting from 2020-01-02 (bar 1 = Thu 2020-01-02, bar 3 = Mon 2020-01-06). There are no holidays. The dataset's last bar is the highest `bar` in the file.
- **Listing**: `listed_from` is the ticker's first bar date. **Delisting**: `delisted_on` is its last bar date, unless that is the dataset's last bar (then it's null, meaning end of data, not a delisting). `delist_reason` is `"fixture"` when delisted. Each security's `name` is its ticker, and its `sector` is `"fixture"`.
- **Load errors** (raised as one error listing every problem): a blank or non numeric value in any column (volume included), a gap in a ticker's bars, a `FIXTURE-INDEX` in the CSV that doesn't cover the whole calendar, or a sidecar row whose `listed_bar` comes after the ticker's first bar, whose `delisted_bar` comes before its last bar, or which names an unknown ticker.
- **Override sidecar** (optional) `<name>.securities.csv`, with header `ticker,listed_bar,delisted_bar,delist_reason`. Use it only when a test needs something inference can't express, such as a delisting on the final bar.
- **Benchmark**: the loader adds `FIXTURE-INDEX` with every price at 100 across the calendar and sets `meta.benchmark` to it, unless the CSV already contains `FIXTURE-INDEX`. `meta` is `data_mode="synthetic"`, `seed=None` is allowed for fixtures (`data_version="fixture:<name>"`), and `survivors_only=False`.
- **Expected values** live in the test as literals with the arithmetic written out, e.g. `pytest.approx(10.8 * 0.999, abs=1e-9)`. There are no expected value sidecars.
- **Builder**: `make_market(tickers: dict[str, FrameSpec], end_bar: int | None = None) -> Market`, where `FrameSpec` takes `start_bar` and either `close` alone (open, high and low default to close, volume to 1,000,000) or full `open`/`high`/`low`/`close`/`volume` lists. It follows the same calendar and inference rules.

### Mock set (`contracts/mocks/`, generated by `make mocks`)

`meta.json` (with data) · `indicators.json` · `templates.json` · `scan.json` (about 40 rows, some `new_today`) · `scan.empty.json` · `backtest.portfolio.json` (5 years, strided equity, about 150 trades) · `backtest.portfolio.truncated.json` (`trades_truncated: true`) · `backtest.trade_lab.json` (5 configs, one with no stop so its R fields are null, one over the horizon threshold) · `backtest.no_entries.json` · `422.rule.unknown_indicator.json` · `422.rule.n_out_of_range.json` · `422.rule.too_many_conditions.json` · `422.exits.duplicate_type.json` · `422.exits.too_many_configs.json` · `422.sim.out_of_range.json` · `501.scan.json`.

Numbers come from a seeded generator inside the script (seed 42). Counts agree (`is_count + oos_count = count`, each `n_trades` matches its trade list where one exists), win rates agree with the trades, and the trade lab rows include a mix of better and worse than random. The script uses no market data. Every float is rounded to 6 decimal places before dumping, so output is byte identical on macOS and the Linux CI.

### Key invariants

- The contract models are the only definition of these shapes. Nothing in `services/api` or `apps/web` redefines a field. The TypeScript types come only from `packages/api-client`.
- `configs[0]` is always the baseline config.
- Undefined numbers are `null`. NaN and Infinity never reach JSON.
- Percent values are percent numbers (8 means 8%) in fields ending `_pct`. Basis points end `_bps`.
- `structure_key` ignores every number and the name. `pair_key` ignores names and exit order.
- Trade mode responses carry no CAGR, max DD or Sharpe fields at all (X-8). Those exist only on `PortfolioMetrics`.
- The validation constraints in the models are the constraints the engine relies on. The engine never re validates ranges.
- Generated files (`openapi.json`, `packages/api-client`, `contracts/mocks/`) are never edited by hand.

### Security model

The API stays public with no auth (ADR-009, spec 0001), serving synthetic data only. The validation bounds also cap the work one request can ask for: at most 8 conditions, 6 configs and 40 character names, plus `extra="forbid"`. Beyond that, abuse protection stays as spec 0001 accepted it (reserved concurrency, budget and throttle alarms, no per client rate limit). Mocks are built from a seeded generator, never from vendor or live data, so they are safe to commit (D-6). Fixture CSVs live under `tests/`, never `data/`. No personal or regulated data is involved.

### Configuration required

- `NEXT_PUBLIC_API_MOCK`: `1` makes the browser build use the MSW handlers instead of `NEXT_PUBLIC_API_URL`. Unset or `0` in production. Add it to `.env.example`.

### Critical test scenarios

- Happy path: each mock request round trips byte for byte, and the scan mock reaches a Vitest test through MSW and the generated client, typed. Verifies **AC-5**, **AC-13**
- Validation: each R-6 case and each exit or sim range case returns 422 with the right `loc` and `ctx` range. Verifies **AC-2**, **AC-3**, **AC-4**
- Stub: a valid backtest with 2 configs returns 501, and the same request with 7 configs returns 422. Verifies **AC-6**, **AC-3**
- Drift: changing a model field without regenerating fails CI in `openapi`, `gen-client` and `mocks`. Verifies **AC-1**, **AC-12**
- Trial keys: `close > highest(252)[1]` and `close > highest(100)[1]` share a key, while `close > sma(50)` does not. Verifies **AC-9**
- Data: a market with duplicate `(ticker, date)` or a missing benchmark fails `validate_market`, and a 3 ticker fixture CSV loads with the inferred listing and delisting dates. Verifies **AC-10**, **AC-11**
- Non finite: building a response with `profit_factor = inf` raises at construction, so it never serialises. Verifies **AC-14**
- Generated types: in the generated TS, `kind`, `type` and `mode` are required properties, and a `switch` on `mode` narrows to `PortfolioResult` or `TradeLabResult`. Verifies **AC-1**
- Auth: not applicable. Every route is public by design (ADR-009).

## Build plan

Tracer Bullet: first one thin thread through every layer (models, route, OpenAPI, generated client, mock, MSW, Vitest) for `/scan`, then thicken it shape by shape. BE does tasks 1 to 5 and 7, DI does 6 and the Makefile/CI parts, FE does the MSW parts.

1. **Thread for `/scan`.** Add `engine/contracts/` with `CONTRACT_VERSION`, `bounded()`, `INDICATOR_SPECS`, the rule models, `ScanRequest` and `ScanResponse`. Add `engine.api.scan` (stub) and `Market` (fields only). Add the `/scan` route (422, then 501). Implement `make openapi` and `make gen-client`, set `info.version`, generate `packages/api-client` with a `createClient` wrapper. Hand write one `scan.json`. Add the MSW setup in `apps/web/src/mocks/` with a Vitest test through the client. Satisfies **AC-1**, **AC-2**, **AC-6**, **AC-13**, **AC-15**
2. **Exits and backtest shapes.** Add the exit variants, `ExitConfig`, `SimParams`, `BacktestRequest`, every response model, the `mode` union, the null and non finite rules, and the caps. Add the `/backtest` route (422, then 501) and the `engine.api.backtest` stub. Satisfies **AC-3**, **AC-4**, **AC-6**, **AC-14**, **AC-15**
3. **Static GET routes.** Add `/indicators`, `/templates` (with `TEMPLATES`) and `/meta` (`MetaResponse` with `data: null`). Satisfies **AC-6**, **AC-7**, **AC-8**
4. **Canonical form and trial keys.** Add `trial.py` (`structure_key`, `pair_key`, `entries_hash`) and the round trip tests over every model and both templates. Satisfies **AC-5**, **AC-9**
5. **Market schema.** Add `BARS_SCHEMA`, `SECURITIES_SCHEMA`, `DataMeta`, `Market` and `validate_market`, with unit tests for each failure. Satisfies **AC-10**
6. **Fixtures (DI).** Add `engine/data/fixtures.py` (`load_fixture`, `make_market`), plus a sample CSV and sidecar under `engine/tests/fixtures/` that prove the calendar and inference rules. Confirm the D-6 guard ignores `tests/**.csv`. Satisfies **AC-11**
7. **Mocks everywhere.** Add `scripts/make_mocks.py` and `make mocks` (replacing the hand written `scan.json`), and every file in the *Mock set*. FE adds a handler per route with switchable 422 and delay variants. Satisfies **AC-12**, **AC-13**, **AC-14**
8. **Freeze.** Add CI jobs that rerun `openapi`, `gen-client` and `mocks` and validate the mocks. Record SO-2 and SO-3 in the PR. Merge, then tag `contracts-v1`. Satisfies **AC-1**, **AC-12**, **AC-16**

## Consequences

**Positive**:
- One definition per shape. FE, BE and QA can't disagree on a field name, unit or range, and CI catches stale generated files.
- FE and QA start on Day 1 against realistic mocks, including the empty, truncated, no stop and 422 states.
- Validation is real from the first merge, so R-6, X-2 and U-7 are testable before any engine code exists.
- Server side trial keys, `best_is` and warnings keep the judgment rules in Python, where pytest and the oracles cover them.
- The bar numbered fixtures let the owner approve an oracle by reading one file.

**Negative / tradeoffs**:
- The engine now depends on Pydantic (allowed, but it's a third library in the domain package beside Polars and NumPy).
- Three generated artefacts mean every contract PR carries regenerated files and a bigger diff.
- The `kind` and `type` tags and full canonical form make the URL longer (a full 8 condition rule plus 6 configs is roughly 2 to 3 KB base64url). That's well under browser limits, but not pretty.
- MSW is a new dev dependency and needs a service worker file in `public/`, which the static export must ship only when mocks are enabled.
- `best_is` direction rules and warning thresholds sit in the API, so changing one is a contract change, not a UI tweak.
- Weekday fixture calendars have no holidays, so a fixture can't test holiday gaps. That's acceptable, since no criterion depends on them.

**Neutral**:
- `info.version` stops tracking `engine.__version__`. The `/health` version still reports the engine.
- `/meta` returns `data: null` until feature 7, and the FE must handle that state.
- The installed `pydantic` skill is not in `AGENTS.md` yet (see Follow-up).

## Follow-up

- [ ] `pydantic` skill (`.agents/skills/pydantic/`): it's not yet listed in the root `AGENTS.md` `## Agent skills` section, and it applies to `engine` and `services/api`, so it belongs at root level. `/sync` can add it.
- [ ] Record the declined MCP server for `/sync` to add to the root `AGENTS.md` `Declined:` line: `msw-mcp` (MSW). Also record the community MSW skill `agents-inc/skills@web-mocks-msw` as not installed.
- [ ] `apps/web/AGENTS.md` should gain the MSW convention (handlers in `src/mocks/`, the `NEXT_PUBLIC_API_MOCK` switch) once task 7 lands.
- [ ] Record the S-3 ruling for QA in `docs/qa/ac-questions.md#S-3`: `new_today` includes the cooldown (doc 02 §6), unlike doc 01's "raw signals" wording. Then fix doc 01's S-3 text to match.
- [ ] X-6 (portfolio mode exit lab, Stretch #4) has no slot in `PortfolioResult`. When it's picked up, add the per config CAGR, max DD and "% of entries shared with baseline" as optional fields (an additive minor bump, `1.x`).
- [ ] Doc 02 §5.4 still shows the untagged operand, the `exits` list without `type`, and fractions in places. Add a one line pointer there to this spec as the frozen source.
- [ ] `skills-lock.json` changed when the `pydantic` skill was installed. Commit it with this spec, or with the first build PR.

## Rationale

Reasoning, options and the full decision log: see [`rationale.md`](rationale.md).
