# 0010 · Live research mode (local)

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

## What the first real load showed (2026-10-15)

`make load-live` was run for real with the owner's keys, and D-4 and D-5 were verified at their
surfaces. Both criteria are now `required`. Three of the assumptions above need correcting when
this spec is ratified:

| Assumed | Measured |
|---|---|
| `feed=sip` (assumption 4, doc 02 A3, doc 01 §6.1) | The free plan has no `sip`; the shipped default is `iex` and `--feed sip` needs a paid plan |
| `data_version="alpaca-sip-all:<date>"` (assumption 3) | `alpaca-iex-all:2026-10-14` |
| History from 2016-01-04, ≈ 1.35M bars (doc 02 A3) | **2017-11-15 → 2026-10-14**, **770,552 bars**, 502 tickers plus SPY. The iex feed has no earlier history: asking for 2014 returns nothing at all, not even SPY |

The load: 1 missing symbol (DOW, not served under that ticker), 97 bars (0.013%) dropped by the
D-2 filter, about 90 seconds end to end. The dataset serves through the real API in live mode and
a 52 week breakout scan on it returns real hits.

D-4 still passes as written, because it asks for first bars "on or after 2016-01-04 (or its
listing date)" and 2017-11-15 clears that. The gap is in the assumption, not the criterion: there
is 22 months less history and 43% fewer bars than planned, over a window that is more bullish
than the one doc 02 A3 described. Anything that reads the live set should expect that.

Assumption 5 (the D-5 host rule) held exactly as written. Every path was driven against a real
uvicorn and each exited 1 before opening a port: `--host 0.0.0.0`, `--host=0.0.0.0`,
`UVICORN_HOST=0.0.0.0`, `CI=1` on loopback, `AWS_LAMBDA_FUNCTION_NAME` on loopback, and all three
at once (the message names every reason, not just the first). Loopback still starts. Two notes:
`localhost` and `::1` are refused too, since the compare is literal, and the error surfaces as a
raw Python traceback whose last line is the message, so it is clear but not tidy.

## Ratify

This decision was recorded by /develop, not deliberated. Run `/architect live research mode`
to deliberate and ratify it. Until then it stays flagged as an owed decision; it does not block marking the feature `done`.
