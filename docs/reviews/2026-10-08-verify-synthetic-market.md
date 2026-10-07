# /check verify synthetic market · PASS on D-1 to D-3 (one surface blocked)

**All 3 requirements (D-1, D-2, D-3) are met with runtime evidence. One specced surface, the API image build, is blocked: Docker was not running on the verify machine, so the in image generation step was read, not run.**

Next: `/test synthetic market` (the `Test it` box). When Docker is available, you may want to run `make build-api` once to close the blocked item.

- Feature: 7, Synthetic market (lane DI, workflow Beta)
- Spec: [0006](../specs/0006-synthetic-market/index.md), status `Assumed` (owes `/architect synthetic market` to ratify; that does not block `done`)
- Criteria: D-1 to D-3 in `docs/01-market-research-and-product-spec.md`
- Build approach: Tracer Bullet. This slice promises a real, seeded market on disk that the scan and backtest can read. Nothing in it is allowed to be faked.
- Branch: `di/7-synthetic-market-verify` from `origin/main` at `f8e1c81`
- Ran on: 2026-10-08, macOS, `uv` Python 3.12

## How it was run

1. `make data SEED=42` (exit 0, 4.7 s wall): `wrote 602776 bars for 500 tickers plus DEMO-INDEX (2021-01-04 to 2025-10-31, 25 delisted, seed 42) to data/synthetic`. Output is `bars.parquet` (12.0 MB), `securities.parquet`, `meta.json`.
2. A second, independent run into a scratch folder: `uv run python -m engine.synthetic --seed 42 --out <scratch>/run2`.
3. An independent checker (scratch script, reads the Parquet with Polars directly and does **not** reuse `engine.data.check_market`) compared both runs and checked every bar.
4. The public API path: `SYNTHETIC_DATA_DIR=data/synthetic`, `market_dir()`, `read_market()`, `generate(42)`, and `generate(seed)` for seeds 0 to 19.
5. The sanity gate on bad data: three corrupted copies of the `make data` output fed to `read_market()`.
6. `make data-check` (the CI target) and `git check-ignore`.

The scratch scripts live outside the repo, in the session scratchpad (`scratchpad/di/verify_synth.py`, `verify_seeds.py`, `verify_reject.py`).

## Spec conformance

| Item | Verdict | Evidence |
|---|---|---|
| D-1 same seed, identical bars, securities and meta | met ✅ | SHA256 equal across the two runs: `bars.parquet` `158dee1f298d94b3…`, `securities.parquet` `0dc6a3bf9e2f778d…`, `meta.json` `5924240c236df0f5…`. `DataFrame.equals` true for both frames (602,776 × 7 and 501 × 6); meta dicts equal. `generate(42)` in memory equals the `make data` files. `make data-check` printed the same three hashes, exit 0. A different seed (7) gives different bars. |
| D-2 bar sanity | met ✅ | Over all 602,776 bars: 0 rows with `low > min(open, close)`, 0 with `high < max(open, close)`, 0 with `volume <= 0`, 0 non positive prices, 0 non finite prices, 0 nulls, 0 duplicate `(ticker, date)`. 0 bars after `delisted_on`, 0 bars before `listed_from`. All 25 delisted tickers have their last bar exactly on `delisted_on`. |
| D-2 the gate rejects bad data | met ✅ | `read_market` raised `MarketError` for each corrupted copy: `1 rows with low above min(open, close), first BAGU 2021-01-18`; `1 rows with volume not positive, first BAGU 2021-01-18`; `1 rows after delisted_on, first BICU 2023-05-03`. |
| D-3 a bear segment and at least 20 delisted tickers | met ✅ | Seed 42: `DEMO-INDEX` (1,260 bars) max drawdown **−38.9%** on 2023-07-10, past the 20% bar from the owner's D-3 ruling. **25** delisted tickers. Seeds 0 to 19 all hold too: worst drawdown between −32.0% (seed 11) and −66.4% (seed 7), 25 delisted and 25 mid sample listings every time. |
| Surface: `generate(seed, config)` | met ✅ | Called for seeds 0 to 19 and 42 above. |
| Surface: CLI `python -m engine.synthetic --seed --out` | met ✅ | Runs 1 and 2 above. |
| Surface: `read_market(DIR)`, `market_dir()` with `SYNTHETIC_DATA_DIR` | met ✅ | `market_dir()` returned `data/synthetic`; `read_market` loaded 602,776 bars and 501 securities. |
| Surface: `meta.json` fields | met ✅ | `data_mode=synthetic`, `seed=42`, `data_version=synthetic-1`, `start=2021-01-04`, `end=2025-10-31`, `n_tickers=500`, `survivors_only=false`, `benchmark=DEMO-INDEX`. |
| Surface: `make data` writes a gitignored folder | met ✅ | `git check-ignore -v data/synthetic/bars.parquet` → `.gitignore:2:data/`. Nothing under `data/` is staged. |
| Surface: CI runs the D-1 to D-3 check | met ✅ | `.github/workflows/ci.yml:38` runs `make data-check`; it passed locally. |
| Surface: API image generates seed 42 into `/data` | blocked ⚠️ | `services/api/Dockerfile:24` runs `python -m engine.synthetic --seed 42 --out /data` and sets `SYNTHETIC_DATA_DIR=/data`, but `docker info` failed (`failed to connect to the docker API … no such file or directory`), so `make build-api` was not run. Needed: a running Docker daemon, then `make build-api`. |

Missing surfaces: none. Not applied: none.

## Notes for the spec ratification (not failures)

These do not touch D-1 to D-3. They are worth a look when someone runs `/architect synthetic market` to ratify spec 0006.

- **Delisting reason split.** The spec says "60% are `bankruptcy` … and 40% are `acquired`". The generator draws each reason as an independent coin flip with p = 0.6 (`generator.py:180`), so seed 42 gives 12 bankruptcy and 13 acquired (48%). Either the spec should say "each with probability 60%", or the generator should assign exactly `round(0.6 × 25) = 15`. Changing the generator changes the data, so it would need a `data_version` bump.
- **Test folder name.** The spec's code area lists `engine/tests/data/`; the real folder is `engine/tests/dataset/` (per `engine/AGENTS.md`, because `.gitignore` ignores every folder named `data/`). The spec line is stale.
- **Session ranges.** Mid sample listings draw from sessions `[round(0.2n), round(0.8n)]` = [252, 1,008] (spec says [252, 1,000]), and delistings from `[round(0.16n), n − 20)` = [202, 1,239] (spec says [200, 1,240]). Small, harmless differences; the ratified spec should state whichever is intended.
- **QA acceptance hook owed.** `tests/acceptance/test_data.py` holds D-1 to D-3 as `pending`, failing with `owed: entry point that generates the synthetic market for seed 42 (feature 7)`. The entry point exists (`engine.synthetic.generate`, `engine.data.read_market`); the QA lane can now wire the hook and flip D-1 to D-3 to `required`.

## For /check review

- `make data` takes under 5 seconds and the bars file is about 12 MB, which is fine for a Lambda image layer.
- `bars.volume` is stored as `Float64` (whole numbers). The frozen bars schema (`engine/contracts/market.py`) defines it that way; just be aware if anything later expects an integer type.
