# engine

## Overview

The `swing-engine` Python package (import name `engine`): all trading logic, meaning data, indicators, rules, exits, the simulator, the random baseline and metrics. The API is a thin wrapper over it, and QA tests it directly through its public entry points.

## Key files

| File | Owns |
|---|---|
| `src/engine/__init__.py` | Package root and `__version__` |
| `tests/test_engine_boundary.py` | Proves the engine imports no web framework |

## Commands

```bash
uv run pytest engine/tests     # engine tests only
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

## Related specs

- [0001 stack & architecture](../docs/specs/0001-stack-architecture/index.md)

_Drafted by /audit from the repo, worth a quick human pass. Edit freely: once a line stops matching this draft, later runs treat it as curated and will flag rather than overwrite it._
