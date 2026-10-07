# Acceptance criteria questions

Where QA and the docs (or a builder) could read a criterion differently, the question lands here (doc 02 section 15.6). The orchestrator rules, the ruling is appended to the relevant spec, and the test stays `pending` until then. Each entry says what the tests assume today, so you can see exactly what a ruling would change.

Status values: **open** (needs a ruling), **ruled** (decided, tests follow it), **owed** (no question about meaning, but an entry point or rule the test needs is not frozen yet).

<a id="S-3"></a>
## S-3: is `new_today` before or after the cooldown?

**Status:** ruled (spec 0002, *Value sourcing*, `new_today`).
Doc 01 S-3 says the scan's "new today" equals the backtest's **raw** signals, before cooldown and last bar filtering. Spec 0002 freezes doc 02 section 6 instead: `new_today` includes the 10 bar cooldown and ignores only the last bar term.
**Tests assume:** the spec 0002 ruling. `test_scan.py::test_new_today_equals_the_backtest_entry_signals` compares `new_today` with the golden signal list (cooldown on, last bar ignored), and with the backtest's entries on every bar except a ticker's own last bar.
**Still to do:** fix the S-3 wording in doc 01 to match (orchestrator).

<a id="R-2"></a>
## R-2 and R-10: the breakout template has 3 conditions or 4?

**Status:** open.
Doc 01 section 6.2 lists four conditions for the 52 week breakout, including `close > sma(50)`. Doc 02 section 5.2, spec 0002 AC-8 and the frozen `TEMPLATES` have three (no `close > sma(50)`).
**Tests assume:** the contract. R-2 evaluates whatever `TEMPLATES` holds, so it passes either way; R-10 only checks the visible `close > 5`.
**Ruling needed:** which list is right, then fix the other doc (and, if doc 01 wins, a contract change PR for `TEMPLATES`).

<a id="ema-seed"></a>
## R-2: how is `ema(n)` seeded, and which bars do windows cover?

**Status:** open.
No doc fixes the first EMA value or the exact windows. The golden reference uses the common conventions: `sma(n)`, `avg_volume(n)`, `highest(n)` and `lowest(n)` cover the n bars ending today (first value on bar n); `ema(n)` starts on bar n at the simple mean of the first n closes, then `alpha = 2 / (n + 1)`; `ret(n)` is `close[t] / close[t-n] - 1` (first value on bar n + 1).
**Why it matters:** a different EMA seed changes values for many bars, so the pullback template could disagree with the golden reference on a few dates.
**Ruling needed:** confirm these, or state the engine's convention so the golden reference can follow it.

<a id="X-1"></a>
## X-1: which date does `entries.hash` use?

**Status:** open.
Spec 0002 says `entries.hash` is the sha256 of the sorted `ticker|entry_date` lines. `Trade.entry_date` is the fill date (signal bar + 1).
**Tests assume:** the fill date, the same as `Trade.entry_date` (`test_backtest.py` B-16 and `test_exit_lab.py` X-1).
**Ruling needed:** confirm fill date, not signal date.

<a id="X-10"></a>
## X-10: how can QA see that random entries are alive and never on a last bar?

**Status:** open.
The trade lab response carries the random counts and metrics, but no random entry list or hash, so "all on alive tickers and none on a last bar" cannot be checked through the public API.
**Tests assume:** nothing; `test_random_entries_are_alive_and_never_on_a_last_bar` is a pending placeholder.
**Options:** (1) an additive optional field, such as `entries.random_hash` or a capped random entry list (contract change, minor bump); (2) rely on the BE unit tests and the owner's B-10 oracle, and record that QA cannot check it independently.

<a id="D-1"></a>
## D-1 to D-3: the synthetic generator's entry point

**Status:** owed (scope feature 7).
The generator has no frozen public entry point yet. The tests are written against the frozen `Market` shape and call one hook, `load_synthetic_market(seed)` in `tests/acceptance/test_data.py`, which fails until feature 7 names the function.
D-3 also needs a definition of a "bear segment". **Tests assume:** the benchmark falls at least 20% from a running peak at some point. Confirm or replace when feature 7 is specced.

<a id="D-4"></a>
## D-4: checking the live load

**Status:** owed (scope feature 14).
D-4 needs Alpaca keys and real data, so it can never run in CI. The test reads the local dataset through a hook, `load_live_market()`, and stays `pending` in CI. The owner runs it locally after `make load-live` as part of `/check verify`.

<a id="D-5"></a>
## D-5: how the API knows it is not on localhost

**Status:** owed (scope feature 14).
D-5 says the API exits with a clear error when `DATA_MODE=live` runs on a non localhost host. No doc fixes how the API learns its host (bind address, an environment variable, or the Lambda environment). The test is a pending placeholder until feature 14 decides.

<a id="ui-tests"></a>
## UI halves of R-1, R-8, X-3, X-4, X-9 and U-1 to U-8

**Status:** owed (QA follow up).
Doc 02 section 15.4 puts these in `apps/web/tests/acceptance/` as Vitest tests against the mocks. They were not written in this change because the FE lane is building the design system in `apps/web/` in parallel. Until then each ID has a pending placeholder in `tests/acceptance/`, plus a contract level test where one applies (U-3 fields, U-7 error paths, U-4 trial keys, X-3 `best_is`, X-4 null R).

<a id="perf"></a>
## S-4, B-13 and X-7: where the time budgets are measured

**Status:** open.
The criteria name the deployed API (S-4, X-7) or a warm run (B-13). CI never calls the deployed API, so the acceptance tests time the use case in process on a seeded 500 ticker, 1,260 bar random walk.
**Tests assume:** an in process pass is the CI gate, and the deployed numbers are a `/check verify` step (`make smoke`).
**Ruling needed:** confirm that split. Once feature 7 lands, the tests can switch to the real synthetic market.
