# services/api

## Overview

The `swing-api` package (import name `api`): a thin FastAPI layer over `engine`, the presentation layer. It runs under uvicorn locally and on AWS Lambda through the Lambda Web Adapter, built from `services/api/Dockerfile` with the repo root as context.

## Key files

| File | Owns |
|---|---|
| `src/api/main.py` | App, middleware (GZip, CORS, the store change check), the `/api/v1` router |
| `src/api/settings.py` | Environment settings, parsed once at import |
| `Dockerfile` | Two stage Lambda image (synthetic data generated in stage 1) |
| `tests/test_health.py` | Health route test |
| `src/api/state.py` | The one `Market`, read with `read_market()` and warmed at import; `None` (routes answer 501) only when no dataset exists. `refresh_if_changed()` is the store change check the middleware runs (spec 0011) |
| `src/api/routes/scan.py` | `POST /scan`, and the one JSON `api.scan` log line per successful scan |
| `src/api/routes/rules.py` | `POST`, `GET` and `DELETE /rules` (spec 0014): saved rules, answering 501 anywhere but the owner's machine |
| `src/api/routes/backtest.py` | `POST /backtest`; maps `range_outside_data` to a 422 like the scan route maps `as_of_not_session`; any other `ValidationError` (`engine.api.REQUEST_ERRORS` decides) stays a 500 |

## Commands

```bash
make dev-api                   # uvicorn on 127.0.0.1:8000 with reload
uv run pytest services/api/tests
make build-api                 # Lambda image, linux/amd64
make build-api-local           # arm64 copy for local smoke tests (not the deploy image)
make smoke-image               # run the built image, check health and one template scan
make migrate                   # local only: bring the database up to the latest migration (spec 0014)
```

## Conventions

- All routes under `/api/v1`. Validation errors use FastAPI's default 422 body (the web app maps them to fields, U-7).
- Routers call `engine.api` use cases only; no trading logic here.
- New env vars go in `settings.py` and `.env.example` together.
- Logs are JSON lines with a request ID per call.
- Fully typed, checked with `mypy --strict`.

## Gotchas

- `DATA_MODE` takes `synthetic` or `live` (feature 14, spec 0010). Live mode refuses to start on Lambda, in CI, or bound to anything but `127.0.0.1` (D-5), checked at import in `settings.py`.
- Saved rules need **both** gates to pass, `saved_rules_problems()` in `settings.py`: a `DATABASE_URL` must be configured **and** the D-5 host rules must hold. Either failing means every rules route answers 501, so a `DATABASE_URL` set on Lambda by accident cannot open an unauthenticated write endpoint. The check runs once at import (`routes/rules.py:ENABLED`), because nothing it reads changes while the process lives; tests monkeypatch that flag.
- CORS `allow_methods` includes `DELETE` for removing a saved rule. Drop it and the browser preflight fails before the request is ever made.
- `make dev-api` and `make migrate` source `.env`, so `DATABASE_URL` and `DATABASE_URL_UNPOOLED` reach the process without exporting anything by hand. Neither variable is ever set on the deployed function.
- Function URLs do not compress responses, so `GZipMiddleware` stays on.
- After any schema change run `make openapi` and `make gen-client` and commit both outputs; CI fails on a diff.
- `contracts/mocks/` is generated from the running app (`scripts/make_mocks.py`), so changing an error body, such as the 501 detail, changes a mock too. Run `make contracts` and commit the result; `make contracts-check` fails on a stale mock.
- The image generates the market into `/data/synthetic` with `--published`, so it never carries data past the market clock's cursor (spec 0012), and sets `MARKET_STORE_URI=/data`; routes load it with `engine.data.read_market()`, which resolves `$MARKET_STORE_URI/$DATA_MODE` (spec 0011). The bake is still there on purpose: it goes once a real bucket exists (feature 17's one way door).
- Always read the market as `state.market`, never `from .state import market`: a reload rebinds that attribute, so an imported name pins the first dataset forever. One `_read_and_warm()` is shared by the import time load and every reload, so a reload can neither skip the warm up nor serve live data off your machine (D-5 is checked on the dataset, not on `DATA_MODE`).
- The change check runs in one `@app.middleware("http")` on a 10 s floor, and the request that notices reloads before it is served. A failed reload logs and keeps the old market. Extend this hook rather than adding a second refresh mechanism.
- On Apple Silicon `make build-api` (linux/amd64) segfaults at the data step: Polars crashes under x86 emulation. Locally run `make build-api-local` then `make smoke-image API_IMAGE=swing-scan-api:local-arm64` (arm64 copy, not the deploy image); the real x86 build and smoke run in the CI `api-image` job on every PR.

## Agent skills

- [fastapi](../../.agents/skills/fastapi/): `fastapi/fastapi`, FastAPI and Pydantic conventions
- [neon-postgres](../../.agents/skills/neon-postgres/): `neondatabase/agent-skills`, pooled versus direct endpoints and psycopg
- MCP servers: `neondatabase/mcp-server-neon` (recommended, not connected)

## Related specs

- [0001 stack & architecture](../../docs/specs/0001-stack-architecture/index.md)
- [0011 market data store](../../docs/specs/0011-market-data-store/index.md) (`MARKET_STORE_URI`, the change check and the inline reload)
- [0014 saved rules](../../docs/specs/0014-saved-rules/index.md) (the rules routes and their two gates)

_Drafted by /audit from the repo, worth a quick human pass. Edit freely: once a line stops matching this draft, later runs treat it as curated and will flag rather than overwrite it._
