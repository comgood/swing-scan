# 0005. Build the template scan on a cached Polars indicator engine with a read only template workspace

**Date**: 2026-10-07
**Status**: In Progress

## Summary

This spec builds the first real path through the product: pick a template, scan today's market with it, and see the hits in a table. The engine computes all 14 indicators once per ticker with Polars (a fast dataframe library) and keeps them in a small cache. It then evaluates any valid rule, including crosses and offsets, and finds the "new today" entries with the same rising edge and cooldown rule the backtest will use. The landing page opens on the Breakout template with its conditions shown as plain text and today's hits below, ready for feature 10 to swap the text for the editable builder.

## Requirements

**User stories**:
- As a visitor, I want the page to open on a ready made template with today's hits so that I see what the tool does without setting anything up (U-1).
- As a visitor, I want to switch to the other template and share a link to it so that a friend sees the same scan.
- As a visitor, I want to read exactly which conditions the scan checks, including the visible `close > 5`, so that nothing is hidden (R-10).
- As a researcher, I want "new today" to mean exactly what the backtest enters on so that the scan and the backtest never disagree (S-3).
- As the BE and FE lanes, we want the engine to accept any valid rule now so that feature 10 adds the builder UI without reworking the engine.

**Acceptance criteria**:
- **AC-1** (S-1, S-2): `engine.api.scan(request, market)` returns exactly the tickers that have a bar on `as_of`, are not the benchmark (`market.meta.benchmark`), and whose rule is valid and true on `as_of`. A ticker delisted before `as_of`, or listed after it, never appears.
- **AC-2** (R-5, R-7, doc 02 §5.2): all 14 indicators in the registry are computed per ticker (`open`, `high`, `low`, `close`, `volume`, `sma`, `ema`, `rsi`, `atr`, `highest`, `lowest`, `avg_volume`, `ret`, `rs`) with the conventions in *Indicator conventions* below. A value without enough history is null. A rule is **valid** at t only when every operand of every condition is non null at t (and at t−1 for a cross); an invalid rule evaluates false. Comparisons use raw float64 values, never rounded.
- **AC-3** (R-3, R-4): the compiler supports every operator in the contract (`>`, `<`, `>=`, `<=`, `crosses_above`, `crosses_below`), `offset` and `mult`, with no `eval`. One cached column per `(ind, n)`; `offset k` (the value k rows back within the same ticker) and `mult` are applied after lookup. `A crosses_above B` at t is `A[t] > B[t]` and `A[t−1] <= B[t−1]`, where each operand at t−1 uses the same offset counted from t−1 and a number operand is the same on both bars; a ticker's first bar is never valid for a cross.
- **AC-4** (S-3, B-14 to B-16): `new_today` on `as_of` comes from one shared entry signal function (doc 02 §6), which feature 9 reuses. Per ticker it walks every bar from the ticker's first bar up to `as_of`: an edge is valid and true at t after valid and false at t−1, and an edge is accepted only if no **accepted** signal lies in t−10 … t−1, so the cooldown is a chain, not a fixed 10 bar window. The scan reads the value on `as_of` with only the last bar term ignored, even when `as_of` is the ticker's real last bar. On every fixture and on a seeded random walk it equals QA's golden reference `entry_signals(…, ignore_last_bar=True)` (`tests/golden/reference.py`).
- **AC-5** (spec 0002): the response follows spec 0002's value sourcing exactly: `as_of`, `columns` (the label grammar, distinct operands in order of first appearance), each row's `operands` aligned to `columns`, `close`, `chg_pct`, `vol_ratio`, `new_today`, and rows sorted new first, then ticker A to Z. Values are sent unrounded. `chg_pct` uses the previous row of the same ticker; `vol_ratio` is null when `avg_volume(50)` is null or 0, never infinite. The universe is 500 tickers, so the 500 row cap is never reached and no truncation flag is needed.
- **AC-6**: `as_of` defaults to the last session in the market. An `as_of` that is not a session (a weekend, or a date before the first or after the last session) answers 422 with type `as_of_not_session`, `loc` `["body","as_of"]` and `ctx` `{min, max}` set to the first and last session. The web app never sends `as_of`.
- **AC-7** (S-4): a warm scan of a rule with 8 conditions on 500 tickers by 1,260 bars answers in under 1 s in process. Indicator columns are cached in a least recently used cache of 64 columns, guarded by a lock because FastAPI runs requests on worker threads. When the API starts it fills the cache with every column the two templates use, and those columns are pinned (never evicted). Warm means the process has already computed every column the request reads.
- **AC-8**: `POST /api/v1/scan` runs `engine.api.scan` on the one market the API loads at import with `engine.data.read_market()` (feature 7). Each successful scan writes one JSON line to stdout through the `api.scan` logger at INFO with `duration_ms`, `n_conditions`, `n_rows`, `cache` (`warm` when every column the request reads, including `vol_ratio`'s `avg_volume(50)` and the `ret(n)` under any `rs(n)`, was already cached; else `cold`) and `as_of`. 422 and 501 answers write no scan line. The route answers 501 only while no market is loaded.
- **AC-9** (U-1): `/` opens on the workspace: a labelled `Template` dropdown filled from `GET /api/v1/templates` with `breakout_52w` selected, the selected template's conditions as read only text, "Hits on {as_of}", and the results table, all under the shell's synthetic banner. No sign up.
- **AC-10**: the selected template lives in the URL as `?template=<id>`, read in a client component inside `Suspense` (required by the static export). Until the parameter is read and `GET /templates` has loaded, the workspace shows a skeleton and runs no scan, so a shared link never fires a wasted Breakout scan. Breakout carries no parameter (choosing it removes `?template`). An unknown id falls back to Breakout and the parameter is removed, once the templates have loaded. Switching templates uses `router.replace` (no new history entry), returns the table to page 1, and runs the scan for the new template.
- **AC-11**: the results table shows ticker, close, % change, volume ratio, one column per operand (header = the label from `columns`) and a sortable "New" badge column. An operand column labelled exactly `close` is skipped, because it repeats the Close column. Numbers are right aligned and formatted by indicator kind (*Number formats* below), nulls show `n/a` and sort last. The default order is the server's; sorting is client side over all rows and returns to page 1. The table pages at 50 rows.
- **AC-12** (U-5): while the scan is pending for more than 1.5 s the warm up notice shows next to the table. A failed scan shows `ErrorState` with "Try again", which runs it again; a 501 shows "Not built yet" with no retry (spec 0003 AC-10). If `GET /templates` fails, `ErrorState` replaces the workspace and "Try again" refetches the templates. Zero hits shows "No hits on {as_of}" with the hint "Try the other template."
- **AC-13** (R-10): the conditions text shows every condition of the template, including `close > 5`, and the scan applies no price filter beyond the rule's own conditions: a rule without `close > 5` returns a ticker trading below 5.
- **AC-14** (U-6): the workspace holds at 375 px and 320 px with no sideways page scroll, is fully usable by keyboard, and passes axe.

## Decision

**Chosen option**: Option 2: a cached Polars indicator engine with a full rule compiler, served by `POST /scan` on the generated market, and a read only template workspace on `/` (see `rationale.md`).

Build the whole engine core now (all indicators, all operators, entry signals), cache indicator columns, and ship a thin workspace that the rule builder later grows into.

**Implementation skills**: `fastapi` (`fastapi/fastapi`, `.agents/skills/fastapi/`) · `pydantic` (`pydantic/skills`, `.agents/skills/pydantic/`) · `python-testing-patterns` (`wshobson/agents`, `.claude/skills/python-testing-patterns/`) · `nextjs-app-router-patterns` (`wshobson/agents`, `.claude/skills/nextjs-app-router-patterns/`) · `vercel-react-best-practices` (`vercel-labs/agent-skills`, `.claude/skills/vercel-react-best-practices/`) · `shadcn` (`shadcn-ui/ui`, `.agents/skills/shadcn/`)

## Rationale

Reasoning, options and every choice made on your behalf: see [rationale.md](rationale.md).

## Feature design

**Data model sketch**: no persisted data. The request and response shapes are frozen in spec 0002 (`ScanRequest`, `ScanResponse`, `ScanRow`, `Rule`, `Market`). The engine adds in memory structures only:

| Structure | Fields | Notes |
|---|---|---|
| `IndicatorKey` | `ind` · `n?` | one cached column per key, offset and mult applied after lookup |
| `IndicatorCache` | LRU of 64 `IndicatorKey → pl.Series` aligned to `market.bars` row order · a set of pinned keys · a lock | one per loaded market (one market per process); the template keys warmed at start are pinned |
| `CompiledRule` | per condition: left and right series (after offset and mult), operator · `valid` and `value` boolean series per bar | built per request, never cached |
| `entry_signals` | shared function in `engine/rules/`: per ticker, the rule's `valid` and `value` series in, the accepted signal per bar out, walking from the ticker's first bar | used by the scan now and the backtest in feature 9 |
| `ScanTiming` | `duration_ms` · `n_conditions` · `n_rows` · `cache` · `as_of` | the log line of AC-8 |

**State transitions**: none. Every scan is stateless; the cache only changes speed, never results.

**Indicator conventions** (owner ruling, doc 02 §5.2, plus the RECOMMEND items in `rationale.md`):

| Indicator | Definition | First valid bar of a ticker |
|---|---|---|
| `open` `high` `low` `close` `volume` | the bar's own value | 1 |
| `sma(n)`, `avg_volume(n)` | mean of the n bars ending today (close, volume) | n |
| `highest(n)`, `lowest(n)` | max high, min low over the n bars ending today | n |
| `ema(n)` | starts on bar n at the mean of the first n closes, then `ema = α × close + (1 − α) × ema[t−1]`, `α = 2 / (n + 1)` | n |
| `ret(n)` | `close[t] / close[t−n] − 1` (a fraction) | n + 1 |
| `atr(n)` | Wilder: true range `max(high − low, |high − close[t−1]|, |low − close[t−1]|)`, `high − low` on a ticker's first bar; first value is the mean of the first n true ranges, then `(atr[t−1] × (n − 1) + tr) / n` | n |
| `rsi(n)` | Wilder: average gain and loss of the close changes, seeded with the simple mean of the first n changes, then smoothed like `atr`; `100 − 100 / (1 + gain / loss)`, and 100 when the loss is 0 | n + 1 |
| `rs(n)` | ranks `ret(n)` with the same n (126 when the validator fills it in): `floor(99 × (rank − 1) / (m − 1))`, where m is the number of non benchmark tickers with a bar on t and a valid `ret(n)`, and rank is the ascending rank of the ticker's `ret(n)` with ties taking the highest rank; 99 when m = 1; null when the ticker's own `ret(n)` is null | when `ret(n)` is valid |

`offset k` reads the value k rows back within the same ticker (null if that row is before the ticker's first bar); a ticker's bars are contiguous (spec 0002), so k rows is k sessions. `mult` multiplies the value. Values never cross from one ticker to the next.

**API surface**:

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/api/v1/scan` | POST | `rule: Rule` (req) · `as_of: date` (opt) | `ScanResponse` | public | 422 invalid rule (spec 0002) · 422 `as_of_not_session` · 501 only while no market is loaded |
| `/api/v1/templates` | GET | none | `list[TemplateOut]` (exists) | public | none |
| `engine.api.scan` | function | `ScanRequest`, `Market` | `ScanResponse` | n/a | raises the `as_of_not_session` validation error |

**Value sourcing**:

| Action | Value produced or displayed | Source |
|---|---|---|
| scan | the market | the one `Market` the API loads at import with `engine.data.read_market()`, which reads `SYNTHETIC_DATA_DIR` (feature 7, PR #11; the Docker image generates the data into `/data`, `make data` writes `data/synthetic/` locally). Until a market is loaded the route answers 501. Engine tests pass `make_market`, `load_fixture` or `engine.synthetic.generate(seed)` markets in directly |
| scan | `as_of` | `ScanRequest.as_of`, else the last session in `market.bars` |
| scan | in the universe on t | the ticker has a bar on t in `market.bars` and is not `market.meta.benchmark` (equivalent to `listed_from <= t <= delisted_on`, since bars are contiguous) |
| scan | indicator values | the cache, computed with the conventions above from `market.bars` |
| scan | `columns`, `operands`, `close`, `chg_pct`, `vol_ratio`, `new_today`, row order and cap | spec 0002 value sourcing, unchanged |
| scan | 422 `ctx` `{min, max}` | the first and last session in `market.bars` |
| scan | `chg_pct` | `(close / previous row's close of the same ticker − 1) × 100`; null on the ticker's first bar |
| scan | `vol_ratio` | `volume / avg_volume(50)`; null when the average is null or 0 |
| scan log | `cache` | `warm` when every column the request reads (operands, `avg_volume(50)` for `vol_ratio`, `ret(n)` under `rs(n)`) was already cached, else `cold` |
| api start | columns to warm | every `IndicatorKey` used by `TEMPLATES` |
| web | template list and default | `GET /templates`; the default is `breakout_52w`, decided here |
| web | selected template | `?template=<id>`, else `breakout_52w` |
| web | conditions text | the selected template's `rule.conditions`: each operand as its spec 0002 column label (a value operand as its plain number), the operator as `>`, `<`, `>=`, `<=`, `crosses above`, `crosses below` |
| web | "Hits on {as_of}" | `ScanResponse.as_of` through `formatDate` |
| web | number format per operand column | the operand's indicator kind from one helper, `operandColumns(rule)`: each condition's left then right operand, number operands skipped, deduped by `(ind, n, offset, mult)` in order of first appearance (spec 0002). A test checks its length equals `columns.length` for every template and mock. Never parsed from the label |
| web | which operand columns show | every column except one labelled exactly `close` |
| web | "New" badge | `ScanRow.new_today` |
| web | warm up notice | the scan query's `isPending` (spec 0003 AC-9) |
| web | error message | `toApiError` on the scan result, shown by `ErrorState` (spec 0003 AC-10) |

**Number formats** (all through `src/lib/format.ts`):

| Kind | Format |
|---|---|
| `open` `high` `low` `close` `sma` `ema` `highest` `lowest` `atr`, and the `close` column | `formatPrice` (2 decimals) |
| `volume` `avg_volume` | `formatInt` |
| `rs` | `formatInt` |
| `rsi` | `formatNumber` (2 decimals) |
| `ret` | `formatPct(value × 100)` |
| `chg_pct` | `SignedValue` with `format="pct"` |
| `vol_ratio` | `formatNumber` (2 decimals) |

A `mult` other than 1 keeps the kind of its indicator (`1.5×avg_volume(50)` is a volume).

**Key invariants**:
- Scan and backtest share one entry signal function; the scan only ignores the last bar term (S-3).
- The cache changes speed only: a scan's response is identical whether the cache is cold or warm, and pinned template columns are never evicted.
- The cooldown is computed over each ticker's whole history up to `as_of`, never from a fixed window.
- Indicator values never use a bar after t (no look ahead), and never mix tickers.
- No hidden filter: only the rule's conditions and "alive on t" decide a row (R-10).
- The web app never hard codes a template; it renders what `GET /templates` returns.

**Security model**: public and read only, no accounts or user data (spec 0001). The rule is validated by the frozen contract before it reaches the engine (at most 8 conditions, bounded parameters, no `eval`). Abuse is bounded by the Lambda's reserved concurrency of 5 (spec 0001) and the warm budget of AC-7; no new rate limiter.

**Configuration required**:
- `SYNTHETIC_DATA_DIR`: where `read_market()` finds the generated market (added by feature 7; set to `/data` in the image, default `data/synthetic` locally). Nothing new is added by this feature.

**Critical test scenarios**:
- Happy path: on a fixture market, the Breakout template returns exactly the expected tickers with correct operands and `new_today`, verifies **AC-1**, **AC-5**
- Parity: on a seeded random walk, `new_today` on every date equals the golden reference with the last bar ignored, verifies **AC-4**
- Delisting: a ticker delisted before `as_of` never appears; one delisted on `as_of` still can, verifies **AC-1**
- Cooldown chain: rising edges at bars 100, 108 and 115 give accepted signals at 100 and 115. 108 falls inside 100's cooldown and is dropped, so 115 has no accepted signal in 105 … 114 and is kept; a rule that looked back over every edge (not only accepted signals) would wrongly drop 115, verifies **AC-4**
- No hidden filter: a rule without `close > 5` returns a ticker trading at 3, verifies **AC-13**
- Templates fail: `GET /templates` errors, the workspace shows "Try again" and refetches, verifies **AC-12**
- Warm up: `close > sma(50)` on a 30 bar ticker is never a hit, verifies **AC-2**
- Crosses and offsets: closes 9, 9, 11, 11 against 10 cross only on bar 3; `highest(5)[1]` excludes today, verifies **AC-3**
- Bad date: an `as_of` on a weekend answers 422 `as_of_not_session` with the data's range, verifies **AC-6**
- Speed: 8 conditions on 500 tickers by 1,260 bars, warm, under 1 s, verifies **AC-7**
- First visit: `/` shows Breakout, its conditions including `close > 5`, "Hits on …" and the table from the mocks, verifies **AC-9**, **AC-13**
- Link: `/?template=pullback_ema21` opens Pullback; `?template=nope` opens Breakout and drops the parameter, verifies **AC-10**
- Slow and failed: a scan held over 1.5 s shows the warm up notice; a network error shows "Try again", verifies **AC-12**
- Auth or permission: not applicable, the app is public with no accounts (spec 0001).

## Build plan

Tracer Bullet: first one thin thread from the market through the engine and `/scan` to the table, then thicken the engine and the page. Lanes: **BE** owns tasks 1a, 2 and 3; **FE** owns 1b and 4 and works against the mocks until gate G3 (BE's `/scan` on `main`).

1. **Thread.**
   - a. **BE**: indicator cache for the price fields, `highest` and `avg_volume`; compiler for the four comparisons with offset and mult; rule validity; the shared `entry_signals` function with the chained cooldown; `engine.api.scan` for the Breakout template on fixtures; `/scan` wired to `read_market()` at import (501 while none is loaded). Satisfies **AC-1**, **AC-4**, **AC-5**, **AC-8**
   - b. **FE**: the workspace on `/` in `src/features/scan/`: `Template` dropdown from `GET /templates`, read only conditions, "Hits on …", results `DataTable` from the mocks, and the `operandColumns(rule)` helper with its length test. Satisfies **AC-9**, **AC-11**, **AC-13**
2. **Engine breadth (BE).** The remaining indicators (`sma`, `ema`, `rsi`, `atr`, `lowest`, `ret`, `rs`) with the conventions table, `crosses_above` and `crosses_below`, the locked LRU cache with pinned keys, and indicator tests against hand values and QA's golden reference. Satisfies **AC-2**, **AC-3**, **AC-7**
3. **Scan contract (BE).** `chg_pct`, `vol_ratio`, the golden parity test for `new_today` on a seeded random walk, `as_of` default and the 422, row order, the no hidden filter test, warming and pinning the template columns at API start, the JSON scan log line (tested with `caplog`), and the in process S-4 timing test. Load `read_market()` at import once feature 7's PR is on `main`. Satisfies **AC-4**, **AC-5**, **AC-6**, **AC-7**, **AC-8**, **AC-13**
4. **Workspace finish (FE).** `?template` in the URL under `Suspense` with the loading skeleton, number formats by kind, the "New" badge column and skipped `close` column, sorting and pages of 50, the warm up, error (scan and templates) and empty states, 375 px, keyboard and axe; then switch from the mocks to the real API once G3 opens. Satisfies **AC-10**, **AC-11**, **AC-12**, **AC-14**

## Consequences

**Positive**:
- Features 9, 10 and 12 reuse one tested indicator engine and one entry signal function, so the backtest and the scan can't drift (S-3).
- Feature 10 becomes mostly UI: the engine already accepts every rule the contract allows.
- The landing page is useful from the first deploy: a real scan on the generated market, under the synthetic banner.

**Negative / tradeoffs**:
- Feature 8 is larger than the two templates need: `rsi`, `atr`, `rs` and crosses are built before any UI uses them.
- Warming the cache adds to the cold start (goal under 6 s, spec 0001); if the measured cold start gets close, warm lazily instead.
- `/scan` can't serve real data until feature 7 merges; BE's route stays 501 on `main` until then, and the FE stays on mocks.
- `rs` ties take the highest rank, so equal returns share the higher percentile. It's a choice made here; feature 10's R-7 tests lock it.
- `?template` is a stopgap: feature 10 replaces it with the full encoded rule, and has to keep old `?template` links working.

**Neutral**:
- `src/app/page.tsx` stops being the scaffold intro and becomes the workspace.
- The scan log line is the first structured log in the API; feature 15 decides where logs go beyond CloudWatch.

## Follow-up

- [ ] Feature 7 (PR #11) provides `engine.data.read_market()` and `engine.synthetic.generate(seed)`; BE task 3 loads the market at import in `services/api/src/api/state.py` once that PR merges.
- [ ] QA: once task 3 merges, S-1, S-2, S-3 (scan side) and R-10 can flip to `required`; S-4's deployed number is a `/check verify` step after a deploy (owner ruling).
- [ ] Feature 10 replaces `?template` with the encoded rule and keeps old `?template` links working.
- [ ] Feature 15 measures the cold start with the warm cache and decides whether to keep warming at import.
