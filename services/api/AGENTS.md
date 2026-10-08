# services/api

## Overview

The `swing-api` package (import name `api`): a thin FastAPI layer over `engine`, the presentation layer. It runs under uvicorn locally and on AWS Lambda through the Lambda Web Adapter, built from `services/api/Dockerfile` with the repo root as context.

## Key files

| File | Owns |
|---|---|
| `src/api/main.py` | App, middleware (GZip, CORS), the `/api/v1` router |
| `src/api/settings.py` | Environment settings, parsed once at import |
| `Dockerfile` | Two stage Lambda image (synthetic data generated in stage 1) |
| `tests/test_health.py` | Health route test |

## Commands

```bash
make dev-api                   # uvicorn on 127.0.0.1:8000 with reload
uv run pytest services/api/tests
make build-api                 # Lambda image, linux/amd64
make build-api-local           # arm64 copy for local smoke tests (not the deploy image)
make smoke-image               # run the built image, check health and one template scan
```

## Conventions

- All routes under `/api/v1`. Validation errors use FastAPI's default 422 body (the web app maps them to fields, U-7).
- Routers call `engine.api` use cases only; no trading logic here.
- New env vars go in `settings.py` and `.env.example` together.
- Logs are JSON lines with a request ID per call.
- Fully typed, checked with `mypy --strict`.

## Gotchas

- `DATA_MODE` is `synthetic` only until scope feature 14; live mode must refuse to start on Lambda, in CI, or bound to anything but `127.0.0.1` (D-5).
- Function URLs do not compress responses, so `GZipMiddleware` stays on.
- After any schema change run `make openapi` and `make gen-client` and commit both outputs; CI fails on a diff.
- The image generates the market into `/data` and sets `SYNTHETIC_DATA_DIR=/data`; routes load it with `engine.data.read_market()` (wired with feature 8, spec 0005).
- On Apple Silicon `make build-api` (linux/amd64) segfaults at the data step: Polars crashes under x86 emulation. Locally run `make build-api-local` then `make smoke-image API_IMAGE=swing-scan-api:local-arm64` (arm64 copy, not the deploy image); the real x86 build and smoke run in the CI `api-image` job on every PR.

## Related specs

- [0001 stack & architecture](../../docs/specs/0001-stack-architecture/index.md)

_Drafted by /audit from the repo, worth a quick human pass. Edit freely: once a line stops matching this draft, later runs treat it as curated and will flag rather than overwrite it._
