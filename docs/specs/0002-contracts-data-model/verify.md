# Verify: Contracts & data model · spec 0002 · updated 2026-10-07
_Steps derived from spec 0002 acceptance criteria. `/check verify` runs these; `/test` locks the durable ones._

## Commands
- [x] `make openapi && make gen-client` → `contracts/openapi.json` has `info.version` `1.0.0`, no `servers`; `pnpm --filter @swing-scan/api-client typecheck` passes → AC-1
- [x] In a throwaway worktree, change one model field without regenerating, run `make contracts-check` → it fails and names the stale files → AC-1, AC-12
- [x] `make mocks` twice → no diff in `contracts/mocks/`; every file validates (`uv run pytest services/api/tests/test_contract_artifacts.py`) → AC-12
- [x] `uv run pytest engine/tests` → all contract, market and fixture tests pass (no ranged field uses `ge`/`le`) → AC-2, AC-5, AC-7 to AC-11, AC-14, AC-15
- [x] `make test` → Vitest calls `/scan` through the generated client and MSW, gets the typed mock, the 422 switch and the delay → AC-13

## API (run `make dev-api`, then send requests)
- [x] `POST /api/v1/scan` with `rsi` `n: 60` → 422, `loc` ends at `n`, `ctx` `{min: 2, max: 50}` → AC-2
- [x] `POST /api/v1/scan` with `macd`, with 9 conditions, with `offset: 21`, with `mult: 11`, with `close` plus `n`, with a missing `kind` → 422 with the right `type` and path → AC-2
- [x] `POST /api/v1/backtest` with 7 configs, a duplicate exit type, a duplicate config name, `pct: 31` → 422 with path and range → AC-3
- [x] `POST /api/v1/backtest` with `max_positions: 25`, `start` after `end`, `start: "2024/01/02"` → 422 → AC-4
- [x] `POST /api/v1/scan` with a valid rule → 501 naming feature 8; `POST /api/v1/backtest` with 2 configs → 501 naming feature 9 → AC-6
- [x] `POST /api/v1/scan` with `rs` and no `n` → body echoes nothing, but parsing fills `n: 126` (unit test) → AC-5, AC-7
- [x] `GET /api/v1/indicators` → 14 rows with `n_min`, `n_max`, `n_default`; `GET /api/v1/templates` → `breakout_52w`, `pullback_ema21` with `close > 5`; `GET /api/v1/meta` → `contract_version` `1.0.0`, `data: null` → AC-6, AC-7, AC-8

## UI / manual
- [ ] `pnpm --filter web dev:mock`, open the app → `mockServiceWorker.js` is served and API calls are answered from the mocks → AC-13
- [x] `make build-web` without `NEXT_PUBLIC_API_MOCK` → `apps/web/out/mockServiceWorker.js` does not exist → AC-13
- [ ] Owner signs off SO-2 (contracts, mocks) and SO-3 (fixture format) in the PR; merge commit tagged `contracts-v1` → AC-16

## Value sourcing
- [x] Scan `columns` follow the label grammar (golden cases `close`, `highest(252)[1]`, `1.5×avg_volume(50)`, `ema(21)[5]`, `1.01×ema(21)`, `rs(126)`) → scan columns row
- [x] `trial.structure_key` equal for `close > highest(252)[1]` and `close > highest(100)[1]`, different for `close > sma(50)`; `pair_keys` ignore names and exit order → trial rows
- [x] `entries.hash` is order independent → entries hash row
- [x] Trade lab mock: `random_*_count` equal `is_count`/`oos_count`; a no stop config has null R fields; one config raises `horizon_exits_over_10pct` → `entries.random_*_count`, R, warnings rows
- [x] `meta.contract_version` equals `CONTRACT_VERSION`; `/meta` `data` null until feature 7 → meta rows

## Acceptance-criteria coverage
- AC-1 · AC-12: drift and generation commands · AC-2 to AC-4: API 422 steps · AC-5: round trip tests · AC-6: 501 and GET steps · AC-7, AC-8: registry and templates · AC-9: trial step · AC-10, AC-11: engine tests · AC-13: Vitest and browser mock steps · AC-14: response rule tests · AC-15: boundary test and stub signatures · AC-16: owner sign off and tag
