# QA traceability matrix

Every MUST criterion in [doc 01 section 6](../01-market-research-and-product-spec.md) maps to at least one acceptance test, a level, a fixture and a gate status. QA keeps this file in step with [`tests/acceptance/status.yaml`](../../tests/acceptance/status.yaml); `tests/acceptance/test_traceability.py` fails the build if the two disagree, if an ID is missing, or if a listed test file does not carry that ID.

## How the gate works

- Each acceptance test carries `@pytest.mark.ac("<ID>")`. A test with no ID fails collection.
- `status.yaml` marks each ID `pending` or `required`. Tests whose IDs are all `pending` run as non strict xfail: they run and report, but never fail CI. A failing test with any `required` ID fails `make test`, and so CI.
- The end of every run prints an `acceptance gate` section: the required and pending counts, any required ID that failed, and any pending ID whose tests all passed (ready to flip).
- QA flips an ID to `required` in a follow up PR once its tests pass on `main` (doc 02 section 15.4). Builders never edit QA files.
- A disputed reading goes to [`ac-questions.md`](ac-questions.md) and the ID stays `pending` until the ruling.
- Vitest UI acceptance tests for UI that is not on `main` yet go through `acIt` (`apps/web/tests/acceptance/gate.ts`), which reads the same `status.yaml`: while every ID of a test is `pending`, a failure is reported as skipped with its reason, and once any ID is `required` it fails the web suite like any other test. Tests written against UI already on `main` stay plain `it` and always block.
- `make test-acceptance` runs only the golden and acceptance suites. `make test` and `make ci` run them with everything else.

## Levels

- **contract**: the request and response models, the OpenAPI document, or the 422 shape, through `TestClient` or `engine.contracts`.
- **use case**: `engine.api.scan` or `engine.api.backtest` on a fixture built with `make_market` (spec 0002, AC-11).
- **golden**: the use case compared against QA's naive loop reference in `tests/golden/reference.py`.
- **guard**: a repo guard run as a black box.
- **UI**: the rendering half, in `apps/web/tests/acceptance/` (Vitest against the mocks, run by `pnpm --filter web test`, so it always blocks CI). A pending placeholder in `test_ui.py` (or the matching file) holds the ID in this gate until every part of the criterion is covered; parts whose UI is not built yet are named in the Fixture column.
- **local**: needs the owner's machine (live keys or data), never CI.

## Matrix

Test files are under `tests/acceptance/`. "Oracle" means the owner's protected suite in `tests/oracle/` (scope feature 6) also covers the ID.

| ID | Criterion | Level | Test file | Fixture | Also covered by | Status | Verified |
|---|---|---|---|---|---|---|---|
| D-1 | Same seed gives identical frames | use case | `test_data.py` | `engine.synthetic.generate` seeds 42 (twice) and 7; the `python -m engine.synthetic` output read back by `read_market` (spec 0006) | `make data-check` | required | 2026-10-08 |
| D-2 | Every bar sane, no bars after delisting | use case | `test_data.py` | `generate(42)`: bar bands, volume, positive finite prices, no bar outside `listed_from` to `delisted_on` | `make data-check` | required | 2026-10-08 |
| D-3 | A bear segment and at least 20 delistings | use case | `test_data.py` | `generate(42)`: benchmark drawdown of at least 20%, 20 or more delistings | `make data-check` | required | 2026-10-08 |
| D-4 | Live load from 2016-01-04, SPY present | local | `test_data.py` | local live data (owed hook) | owner run of `make load-live` | pending | |
| D-5 | Live mode refuses a non localhost host | use case | `test_data.py` | owed: host detection rule | | pending | |
| D-6 | Data and keys are blocked at commit | guard | `test_data.py` | temp files under `data/` and a runtime built fake key | CI guards job | required | 2026-10-07 |
| R-1 | Rule JSON and URL round trip | contract, UI | `test_rules.py`; Vitest `apps/web/tests/acceptance/rule-builder.test.tsx` | both templates plus one rule using every operand shape; on `/`, an edit switching the link to `?r=` and a reload of it, and a `?r=` in spec 0008's encoding (spec 0008 AC-1, AC-2) | | required | 2026-10-08 |
| R-2 | Templates equal the golden reference on every date | golden | `test_rules.py` | 24 ticker seeded random walk, 330 bars, with listings and delistings | Oracle | required | 2026-10-08 |
| R-3 | Crosses are true only on the crossing bar | use case | `test_rules.py` | closes 9, 9, 11, 11 against 10 | Oracle | required | 2026-10-08 |
| R-4 | `highest(5)[1]` excludes today | use case | `test_rules.py` | hand built highs, bar 8 | Oracle | required | 2026-10-08 |
| R-5 | Warm up bars are never hits | use case | `test_rules.py` | 30 bars, `close > sma(50)` | Oracle | required | 2026-10-08 |
| R-6 | Bad rules return 422 with a path and range | contract | `test_rules.py` | seven bad rule shapes | engine unit tests | required | 2026-10-07 |
| R-7 | `rs` lies in 0 to 99, top return gets 99 | use case | `test_rules.py` | 12 tickers with distinct 126 bar returns | Oracle | required | 2026-10-08 |
| R-8 | Builder rows match the request JSON | UI | `test_rules.py` (pointer); Vitest `apps/web/tests/acceptance/rule-builder.test.tsx` | edits, an added and a removed row against the captured `POST /scan` body; a rule loaded from the JSON panel (spec 0008 AC-4) | | required | 2026-10-08 |
| R-9 | Structure key ignores numbers only | contract | `test_rules.py` | rule pairs differing in numbers, indicator, operator, kind, count | engine unit tests | required | 2026-10-07 |
| R-10 | Visible `close > 5`, no hidden price filter | contract, use case, UI | `test_rules.py`; Vitest `apps/web/tests/acceptance/template-scan.test.tsx` (conditions text) | `/templates`, a penny stock fixture, a penny breakout with and without the template's `close > 5` (spec 0005 AC-13) | | required | 2026-10-08 |
| S-1 | Scan returns exactly the alive, valid and true tickers | use case, contract, UI | `test_scan.py`; Vitest `apps/web/tests/acceptance/template-scan.test.tsx` (results table) | rising, falling, young and late listed tickers; row order, hand computed operands, `chg_pct` and `vol_ratio`, cold equals warm, `as_of` 422; `/scan` on a generated seed 42 market in a subprocess (spec 0005 AC-5, AC-6, AC-8); table columns, New badges, 50 row pages, empty and error states (AC-11, AC-12) | | required | 2026-10-08 |
| S-2 | Delisted tickers never appear | use case | `test_scan.py` | a ticker delisted on bar 20; one listed after `as_of`, one delisted on `as_of` (spec 0005 AC-1) | | required | 2026-10-08 |
| S-3 | `new_today` equals the backtest signals | golden | `test_scan.py` | 20 ticker random walk, 120 bars; chained cooldown with edges on bars 100, 108, 115; an edge on a ticker's real last bar (spec 0005 AC-4) | Oracle | pending | |
| S-4 | Warm scan of 500 tickers under 1 s | use case | `test_scan.py` | 500 ticker, 1,260 bar random walk, template and 8 conditions (spec 0005 AC-7); the scan log line on the generated market (AC-8); deployed number via verify | `make smoke` | required | 2026-10-08 |
| B-1 | Percent stop fill | use case | `test_backtest.py` | one ticker, signal bar 3, low below the stop on bar 5 | Oracle | required | 2026-10-08 |
| B-2 | Gap through the stop fills at the open | use case | `test_backtest.py` | bar 5 opens below the stop | Oracle | required | 2026-10-08 |
| B-3 | ATR stop is fill minus k times ATR | use case | `test_backtest.py` | true range fixed at 2.0, signal bar 20 | Oracle | required | 2026-10-08 |
| B-4 | Percent target, gap target, stop beats target | use case | `test_backtest.py` | three one bar setups | Oracle | required | 2026-10-08 |
| B-5 | Trailing stop levels 9.0 then 10.8 | use case | `test_backtest.py` | highs 10, 12, 11 after a fill of exactly 10 | Oracle | required | 2026-10-08 |
| B-6 | Close below SMA exits at the next open | use case | `test_backtest.py` | close 9 against SMA(21) 9.952 | Oracle | required | 2026-10-08 |
| B-7 | Time exit at the close of bar N | use case | `test_backtest.py` | N = 3 | Oracle | required | 2026-10-08 |
| B-8 | Delisting exits at the last close | use case | `test_backtest.py` | ticker ends on bar 8, data on bar 20 | Oracle | required | 2026-10-08 |
| B-9 | MAE and MFE with the exit bar capped | use case | `test_backtest.py` | stop, target and time trades | Oracle | required | 2026-10-08 |
| B-10 | A poisoned future changes nothing up to T | use case | `test_backtest.py` | 30 ticker random walk, garbage after bar 400, all six exits | Oracle | pending | |
| B-11 | Top 10 by `rs` fill 10 slots at equity over 10 | use case | `test_backtest.py` | 15 tickers signalling on bar 200 | | required | 2026-10-08 |
| B-13 | Deterministic, under 3 s and 6 MB | use case | `test_backtest.py` | 20 ticker and 500 ticker random walks | | pending | |
| B-14 | No signal on the first valid bar or a listing day | golden | `test_backtest.py` | 270 bar `highest(252)[1]` path; late listings | Oracle, golden self tests | pending | |
| B-15 | No entry on a last bar | use case | `test_backtest.py` | edge on a delisting bar and on the data's last bar | Oracle, golden self tests | pending | |
| B-16 | Cooldown accepts 100 and 112 in every config | use case | `test_backtest.py` | edges on bars 100, 105, 112 | Oracle, golden self tests | pending | |
| X-1 | Entries identical across configs | golden | `test_exit_lab.py` | 30 ticker random walk, 500 bars, configs reordered | Oracle | pending | |
| X-2 | One config runs a portfolio, seven return 422 | contract, use case | `test_exit_lab.py` | 7 time configs; 1 time config | | required | 2026-10-08 |
| X-3 | IS and OOS columns, best IS only | use case, UI | `test_exit_lab.py` | five default configs | | pending | |
| X-4 | No stop means percent expectancy and null R | use case, UI | `test_exit_lab.py` | baseline time only config | | pending | |
| X-5 | Guides from baseline IS trades only | use case | `test_exit_lab.py` | five configs, guides recomputed from baseline trades | | pending | |
| X-7 | Six configs plus baseline under 10 s and 6 MB | use case | `test_exit_lab.py` | 500 ticker, 1,260 bar random walk (deployed number via verify) | `make smoke` | pending | |
| X-8 | Per trade metrics only, hand checked | use case | `test_exit_lab.py` | metrics recomputed from baseline trades | | pending | |
| X-9 | Horizon exit at bar 60 and the warning | use case, UI | `test_exit_lab.py` | steady climb that never trips a 10% trail | Oracle | pending | |
| X-10 | Random baseline counts, seed and edge | use case | `test_exit_lab.py` | five configs, seeds 42 and 7 | BE unit tests and Oracle B-10 (alive, never on a last bar; ruled 2026-10-07) | pending | |
| U-1 | First visit: Breakout, results, synthetic banner | contract, UI | `test_ui.py`; Vitest `apps/web/tests/acceptance/data-mode-banner.test.tsx` (banner part), `apps/web/tests/acceptance/template-scan.test.tsx` (workspace), `apps/web/tests/acceptance/rule-builder.test.tsx` (builder) | `/meta`, `/templates` and a Breakout `/scan` on a generated seed 42 market in a subprocess; health mock held, synthetic and failing, on every page; `/` on the mocks with `next/navigation` emulated: Breakout, conditions, "Hits on", the table, `?template` links, no scan before templates load, templates failure (spec 0005 AC-9, AC-10, AC-12); the builder's rows holding Breakout's rule (spec 0008) | | required | 2026-10-08 |
| U-2 | Survivors badge in live mode | UI | `test_ui.py` (pointer); Vitest `apps/web/tests/acceptance/data-mode-banner.test.tsx` | health mock `live`, on every page (spec 0004 AC-8: the shell banner) | | required | 2026-10-08 |
| U-3 | Assumptions header lists every field | contract, UI | `test_ui.py` | OpenAPI `Assumptions`; Vitest owed | | pending | |
| U-4 | Trial counter by structure, warning at 10 | use case, UI | `test_ui.py`; Vitest `apps/web/tests/acceptance/honesty.test.tsx` | trial keys from a trade lab run; `RunTrialCounter` on the mock `trial` blocks and seeded storage (spec 0004 AC-1 to AC-6, AC-9); counter inside the reports owed (features 9, 12) | | pending | |
| U-5 | Warming up state after 1.5 s | UI | `test_ui.py` (pointer); Vitest `apps/web/tests/acceptance/warmup.test.tsx`, `apps/web/tests/acceptance/template-scan.test.tsx` (scan) | health mock delayed 2.5 s and held; `WarmupNotice` on fake timers (1,499 and 1,500 ms); the scan held 2.5 s on `/` (spec 0005 AC-12) | | required | 2026-10-08 |
| U-6 | Layout holds at 375 px | UI | `test_ui.py`; Vitest `apps/web/tests/acceptance/layout-375.test.tsx` (structure only) | every page, a 12 column `DataTable`, `FormRow` with 2 to 4 columns; builder rows owed (feature 10) | browser pass in `/check verify` (scroll width, real stacking) | pending | |
| U-7 | 422 shows inline on the row or field | contract, UI | `test_ui.py`; Vitest `apps/web/tests/acceptance/errors-422.test.tsx` (shared helpers), `apps/web/tests/acceptance/rule-builder.test.tsx` (pages) | bad `n` on row 2, bad exit param; the 422 mocks through `fieldErrorsFrom422`; real API paths on the builder rows and the `/backtest` exit form; a right side path waits on [U-7-loc](ac-questions.md#U-7-loc); exit lab editor owed (feature 12) | | pending | |
| U-8 | Procedure note under the exit lab table | UI | `test_ui.py`; Vitest `apps/web/tests/acceptance/honesty.test.tsx` (words) | `ProcedureNote` and the `/ui` gallery (spec 0004 AC-7, AC-9); placement under the exit lab table owed (feature 12) | | pending | |

**Totals:** 52 MUST criteria, 31 required, 21 pending. Stretch criteria (S-5, B-4R, B-12, X-5S, X-6) get a row when they are picked up.

## Golden reference

`tests/golden/reference.py` is a plain loop implementation of rule evaluation and the entry signal (rising edge, last bar rule, 10 bar cooldown), written from doc 01 and doc 02 section 6 only. `tests/golden/test_reference.py` checks it against the worked examples for R-3, R-4, R-5, B-14, B-15 and B-16. It is not gated: it is QA's own code, so it always blocks.
