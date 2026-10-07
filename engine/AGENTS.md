# engine

## Overview

The `swing-engine` Python package (import name `engine`): all trading logic, meaning data, indicators, rules, exits, the simulator, the random baseline and metrics. The API is a thin wrapper over it, and QA tests it directly through its public entry points.

## Key files

| File | Owns |
|---|---|
| `src/engine/__init__.py` | Package root and `__version__` |
| `tests/test_engine_boundary.py` | Proves the engine imports no web framework |
| `src/engine/synthetic/` | Seeded synthetic market: `generate(seed) -> Market`, CLI `python -m engine.synthetic --seed 42 --out DIR` (spec 0006) |
| `src/engine/data/store.py` | `read_market()`, `write_market()`, `market_dir()` (reads `SYNTHETIC_DATA_DIR`, default `data/synthetic`) |
| `src/engine/data/sanity.py` | `check_market()`: `validate_market` plus the D-2 bar checks |
| `src/engine/data/fixtures.py` | `load_fixture()` for bar numbered CSVs, `make_market()` from lists (spec 0002 fixture format) |

## Commands

```bash
uv run pytest engine/tests     # engine tests only
make data                      # write the seed 42 market to data/synthetic
make data-check                # CI: rebuild twice, same hashes, D-1 to D-3 hold
```

## Conventions

- Domain modules (BE lane): `indicators/`, `rules/`, `exits/`, `sim/`, `baseline/`, `metrics/`. Infrastructure (DI lane): `data/`, `synthetic/`. Contracts: `engine/contracts/`.
- Public use cases live in `engine.api` (`scan`, `backtest`); acceptance tests call only these, never internal modules.
- Polars for indicators and rules; NumPy and plain Python loops for the simulator. No Numba until profiling demands it (ADR-006).
- Fully typed, checked with `mypy --strict`.

## Gotchas

- Never import `fastapi`, `starlette` or `uvicorn` here; the boundary test fails.
- Every exit runs through one `step(position, bar)` function shared by both loops. Never special case an exit outside it.
- The random baseline seed default changes only with an ADR.
- Rule compilation never uses `eval` or `exec`.
- Tests for `data/` live in `engine/tests/dataset/`, because `.gitignore` ignores every folder named `data/`.

## Related specs

- [0001 stack & architecture](../docs/specs/0001-stack-architecture/index.md)
- [0002 contracts & data model](../docs/specs/0002-contracts-data-model/index.md)
- [0005 template scan](../docs/specs/0005-template-scan/index.md) (indicators, rules, entry signals)
- [0006 synthetic market](../docs/specs/0006-synthetic-market/index.md)

_Drafted by /audit from the repo, worth a quick human pass. Edit freely: once a line stops matching this draft, later runs treat it as curated and will flag rather than overwrite it._
