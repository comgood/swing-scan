# /check verify template scan · PASS (on the integration of #29 and #21)

**PASS: all 14 acceptance criteria of spec 0005 are met, and every specced surface is built.** Four checks ran only against the mocks (Vitest), not the live app; they are listed below so you can decide whether that is enough.

- **What was verified:** a local only branch (never pushed) built from `origin/be/8-template-scan-contract` (top of #22 ← #24 ← #29) merged with `origin/fe/8-template-scan-finish` (top of #18 ← #21). QA's pending tests from #23 were merged in too, so the acceptance run could exercise them.
- **Merge conflicts:** none. `git merge origin/fe/8-template-scan-finish` into the BE branch was clean, and so was the merge of #23.
- **Data:** `make data` (seed 42, 500 tickers plus `DEMO-INDEX`, 2021-01-04 to 2025-10-31, 25 delisted).
- **App:** `make dev-api` (127.0.0.1:8000) and `make dev-web` (localhost:3000), driven as a black box. The API was hit over HTTP. The web app ran in real headless Chrome through the DevTools protocol, at 1280, 375 and 320 px. Builder folders were not opened.
- **Build approach:** Tracer Bullet. This slice promised a real path from the generated market through `/scan` to the table on `/`, and that path is real end to end.

Nothing is flipped to `required` here, because the feature is not on `main` yet. The scope box is not ticked for the same reason: once #22/#24/#29 and #18/#21 merge, rerun `make test-acceptance` on `main` and flip the IDs listed below.

## Acceptance run on the integration branch

`make test-acceptance`: 40 passed, 53 xfailed, 34 xpassed. The gate reports **pending and fully passing: R-2, R-3, R-4, R-5, R-7, R-10, S-1, S-2, S-4**.

| ID | State on the integration branch |
|---|---|
| R-2, R-3, R-4, R-5, R-7 | every test passes (golden template parity, crosses, `highest(5)[1]`, warm up, `rs` range) |
| R-10 | every test passes (visible `close > 5` in both templates, no hidden price filter, penny breakout) |
| S-1, S-2 | every test passes, including `/scan` on a generated seed 42 market in a subprocess (200, the 422 `as_of_not_session`, row order, values) |
| S-4 | every test passes (template and 8 conditions on 500 × 1,260 under 1 s in process, the scan log line) |
| S-3 | the scan side passes (chained cooldown 100/108/115, an edge on a ticker's real last bar). `test_new_today_equals_the_backtest_entry_signals` still xfails because it needs the backtest (feature 9), so S-3 cannot flip yet |
| U-1 | `test_first_visit_data_is_the_synthetic_market` passes here only because `make data` ran locally; its UI placeholder in `test_ui.py` is still owed. The Vitest workspace tests pass (see below) |
| U-5 | the workspace warm up Vitest test passes. The pytest placeholder is still owed |

Full suites on the integration branch: `uv run pytest`: 385 passed, 53 xfailed, 34 xpassed. `pnpm --filter web test`: 305 passed, 2 skipped (both explained in the next section).

**Vitest `template-scan.test.tsx` (#23):** 13 passed, 2 skipped by the pending gate:
- *an unknown ?template falls back to Breakout and drops the parameter*
- *switching templates replaces the URL and scans the new rule*

Both behaviors **work in the real browser** (evidence below). The tests skip because their emulated `next/navigation` router never sees a `replace` call, so the URL change goes some other way. That is a flaw in the QA test, not the app. It is logged in [ac-questions.md#AC-10-url](../qa/ac-questions.md#AC-10-url) and needs fixing in #23 before U-1 flips.

## Spec conformance (spec 0005)

| AC | Verdict | Evidence |
|---|---|---|
| AC-1 alive, non benchmark, valid and true | met ✅ | `POST /api/v1/scan` with each template returned 200: `DEMO-INDEX` absent and tickers unique. The S-1/S-2 acceptance tests pass (late listing, delisting on `as_of`, benchmark) |
| AC-2 14 indicators, null warm up | met ✅ | An 8 condition rule with `sma`, `ema`, `rsi(14)`, `atr(14)` and `rs(126)` returned 200 with 10 columns. The R-5, R-7 and R-2 golden tests pass |
| AC-3 operators, offset, mult | met ✅ | `close crosses_above sma(20)` returned 200 with 9 rows. The R-3 and R-4 tests pass |
| AC-4 shared entry signal, chained cooldown | met ✅ (scan side) | The cooldown chain and last bar tests pass, and so does the golden parity test with the last bar ignored. Backtest reuse waits for feature 9 |
| AC-5 response values and order | met ✅ | Breakout on 2025-10-31: `columns` = `close, highest(252)[1], volume, 1.5×avg_volume(50)`; rows CADE and CIRU, both `new_today`, with unrounded values (`chg_pct` 5.954117783075219). Pullback: 84 rows, 24 new, sorted new first then A to Z (checked on the full body), operands aligned |
| AC-6 `as_of` default and 422 | met ✅ | No `as_of` gave `as_of` = `2025-10-31`. A weekend (`2024-03-16`), a date before the data (`2020-01-02`) and one after it (`2026-01-05`) each returned 422 with `type: as_of_not_session`, `loc: ["body","as_of"]` and `ctx: {min: 2021-01-04, max: 2025-10-31}`. A real session (`2024-03-15`) returned 200 |
| AC-7 warm under 1 s | met ✅ | Over HTTP, an 8 condition rule took 89 ms cold, then 12.3 ms and 11.7 ms warm. Templates took 8.8 to 24 ms. The in process 500 × 1,260 tests pass |
| AC-8 route and scan log | met ✅ | Server stdout showed one JSON line per successful scan (12 lines for 12 successes), e.g. `{"event": "scan", "duration_ms": 22.171, "n_conditions": 3, "n_rows": 2, "cache": "warm", "as_of": "2025-10-31"}`. The first 8 condition scan logged `cold`, later ones `warm`, and the 422s logged nothing. The 501 without a market was not exercised live; it is covered by the earlier `main` run |
| AC-9 workspace on `/` | met ✅ | Browser at `/`: a `Template` select showing "52 week high breakout on volume", the conditions as text, "Hits on 2025-10-31", the table with 2 rows, the synthetic banner as `main`'s first child, no sign up. Screenshot `01-first-visit-1280.png` |
| AC-10 `?template` in the URL | met ✅ | `/?template=pullback_ema21` opened Pullback (5 conditions, 50 rows on page 1). `/?template=nope` showed Breakout, and the URL became `/`. Choosing Pullback in the select changed the URL to `/?template=pullback_ema21` with `history.length` unchanged (6 → 6), so it is a replace, not a push, and the new scan ran. Choosing Breakout went back to `/`. No scan before the templates load: Vitest against the mocks only |
| AC-11 table, formats, paging, sorting | met ✅ | Headers: `Ticker, Close, % change, Volume ratio`, one per operand with `close` skipped, then `New`. Formats: `38.49`, `+5.95%`, `2.32`, `4,974,650`. Pullback paged 50 then 34 ("Page 1 of 2"). Sorting by Ticker went back to page 1. `n/a` was not seen live, because the live hits have no nulls |
| AC-12 states | met ✅ | Scan held 3 s with the request intercepted: no notice at 1.2 s, "Warming up the engine…" at 2.1 s, gone once the rows landed (`09-warming-up.png`). Scan failed: "Can't reach the engine" with Try again, and clicking it loaded the rows (`10-scan-failed.png`). Templates failed: same `ErrorState`, and Try again recovered the workspace. Zero hits ("No hits on …", "Try the other template.") and the 501 "Not built yet" without retry: Vitest against the mocks only |
| AC-13 no hidden filter | met ✅ | The conditions text shows `close > 5` for both templates. `POST /scan` with only `close < 5` returned 12 rows (e.g. DULE 3.2052) |
| AC-14 375 px, 320 px, keyboard, axe | met ✅ | At 375 and 320 px the page `scrollWidth` equals the viewport width, and the table scrolls inside its own `overflow-x: auto` box (341 px wide, 808 px content). Screenshots `07-first-visit-375.png` and `07-first-visit-320.png`. Tab reaches the native `select`. axe-core 4.14 (WCAG 2.0/2.1 A and AA) found 0 violations |

**Specced surfaces:** `POST /api/v1/scan` on the loaded market, the `api.scan` log line, `/` as the workspace (`Template` select, conditions, "Hits on", results table, warm up, error and empty states). All exist. Missing: none. Not applied: none.

**Console:** no browser console errors or exceptions during the run. No server tracebacks.

## Ran only against the mocks, not live

- AC-10: no scan before `GET /templates` loads (the pending gate showed it passing in Vitest).
- AC-11: `n/a` for nulls.
- AC-12: the empty state and the 501 state.
- AC-14: choosing an option with the keyboard. Headless Chrome on macOS opens the native select popup at the OS level, so the driver set the value and fired `input` and `change` instead. A native select is keyboard operable by the platform, but a manual keyboard pass in a headed browser would close this.

## For /check review

- The Next dev indicator overlaps the footer at 375 px. That is dev only, but worth a glance on the static build.
- "Hits on 2025-10-31" shows the date in ISO form. That is fine if `formatDate` is meant to give ISO; check it against spec 0003 if not.

## Evidence

The DevTools driver, the API check script and their outputs are in the QA lane's scratchpad (`verify8/ledger.txt`, `apicheck.out`, screenshots `01`, `02`, `05`, `07`, `09`, `10`). They are not committed, because they are run artifacts.
