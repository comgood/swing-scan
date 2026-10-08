# 0009 · Live research mode (local)

**Status**: Assumed
**Date**: 2026-10-08
**Authorized by**: Kenneth Wu (owner), through the overnight lane rules, during /develop (DI lane). Proposed, pending owner sign off.

## Owed decision

Spec 0001 fixes the D-5 host rule and doc 02 A3 fixes the source (Alpaca free daily bars, `feed=sip`, `adjustment=all`, from 2016-01-04, about 500 current S&P 500 names plus SPY). Nothing named:

1. where the list of "current S&P 500 names" (and each name's company name and sector, which `securities.parquet` needs) comes from;
2. what happens to vendor bars that fail the D-2 checks `write_market` enforces;
3. how the API knows which address it is bound to;
4. where the live dataset lives and how the API is pointed at it.

## Assumed decisions (pending owner sign off)

1. **Universe**: you supply a CSV at `research/sp500.csv` (gitignored) with the header `ticker,name,sector`, one row per current member (for example copied from the Wikipedia S&P 500 list). The loader adds SPY itself (sector `Index`). No list is committed, so no stale membership ships in the repo, and the loader makes no extra vendor call for names.
2. **Bad bars**: bars that fail D-2 (non positive or non finite price or volume, `low` above `min(open, close)`, `high` below `max(open, close)`) are dropped, never repaired, and the load summary counts them.
3. **Listing and delisting**: `listed_from` is each ticker's first loaded bar; `delisted_on` is always null (the universe is today's survivors). `meta`: `data_mode="live"`, `seed=null`, `survivors_only=true`, `benchmark="SPY"`, `data_version="alpaca-sip-all:<last bar date>"`.
4. **Dates**: start 2016-01-04, end yesterday by default (the free plan blocks the latest 15 minutes of SIP data). A bar's date is the date part of Alpaca's `t` timestamp.
5. **Bound address (D-5)**: resolved the way uvicorn resolves it: `--host` on the command line, else `UVICORN_HOST`, else uvicorn's default `127.0.0.1`. Only exactly `127.0.0.1` passes (`localhost`, `::1` and `0.0.0.0` are refused). `AWS_LAMBDA_FUNCTION_NAME` or `CI` set also refuses. The check runs in `Settings.from_env()`, so the app fails at import, before serving anything. Limitation: a program that calls `uvicorn.run(host=...)` directly is not seen; the Lambda and CI checks still hold there.
6. **Location**: `data/live/` (gitignored, per the doc 02 diagram). `make dev-live` runs `make dev` with `DATA_MODE=live SYNTHETIC_DATA_DIR=data/live`, reusing the existing data dir variable instead of adding a new one.
7. **Code location**: `engine/src/engine/live/` (infrastructure, beside `synthetic/`), CLI `python -m engine.live`. Not `engine/src/engine/data/`, because agent permissions deny writes to any path containing `data/`.
8. **Transport**: the standard library (`urllib`), no new dependency; 100 symbols per request, 10 000 bars per page, exponential back off on HTTP 429. The transport is injected, so tests use a fake and never reach the network.

## Code area

`engine/src/engine/live/`, `engine/tests/live/`, `services/api/src/api/settings.py`, `services/api/tests/test_settings.py`, `Makefile` (`load-live`, `dev-live`), `.env.example`.

## Requirements

- **D-4**: `make load-live` with valid keys writes `data/live`; each ticker's first bar is on or after 2016-01-04 (or its listing date), SPY is present, and the summary reports the ticker count and the missing symbols.
- **D-5**: `DATA_MODE=live` refuses to start on Lambda, in CI, or bound to anything but `127.0.0.1`, with a clear error.
- `research/` and `data/` stay gitignored; keys come only from the environment (or a local `.env`).

## Ratify

This decision was recorded by /develop, not deliberated. Run `/architect live research mode`
to deliberate and ratify it. Until then it stays flagged as an owed decision; it does not block marking the feature `done`.
