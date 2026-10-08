# Acceptance criteria questions

Where QA and the docs (or a builder) could read a criterion differently, the question lands here (doc 02 section 15.6). The orchestrator rules, the ruling is appended to the relevant spec, and the test stays `pending` until then. Each entry says what the tests assume today, so you can see exactly what a ruling would change.

Status values: **open** (needs a ruling), **ruled** (decided, tests follow it), **owed** (no question about meaning, but an entry point or rule the test needs is not frozen yet).

<a id="S-3"></a>
## S-3: is `new_today` before or after the cooldown?

**Status:** ruled (spec 0002, *Value sourcing*, `new_today`).
Doc 01 S-3 says the scan's "new today" equals the backtest's **raw** signals, before cooldown and last bar filtering. Spec 0002 freezes doc 02 section 6 instead: `new_today` includes the 10 bar cooldown and ignores only the last bar term.
**Tests assume:** the spec 0002 ruling. `test_scan.py::test_new_today_equals_the_backtest_entry_signals` compares `new_today` with the golden signal list (cooldown on, last bar ignored), and with the backtest's entries on every bar except a ticker's own last bar.
**Doc 01 fixed** (2026-10-07): S-3 now reads after the cooldown, ignoring only the last bar term.

<a id="R-2"></a>
## R-2 and R-10: the breakout template has 3 conditions or 4?

**Status:** ruled (owner, 2026-10-07).
Doc 01 section 6.2 listed four conditions for the 52 week breakout, including `close > sma(50)`. Doc 02 section 5.2, spec 0002 AC-8 and the frozen `TEMPLATES` have three (no `close > sma(50)`).
**Ruling:** three conditions; the contract stands. A close above the prior 252 day high is almost always above its 50 day SMA, so the fourth condition rarely filters anything. Doc 01 section 6.2 is corrected to match; no contract change.
**Tests:** unchanged. R-2 evaluates whatever `TEMPLATES` holds; R-10 checks the visible `close > 5`.

<a id="ema-seed"></a>
## R-2: how is `ema(n)` seeded, and which bars do windows cover?

**Status:** ruled (owner, 2026-10-07). Recorded in doc 02 section 5.2, so the BE lane builds the engine to it.
No doc fixed the first EMA value or the exact windows. The golden reference uses the common conventions: `sma(n)`, `avg_volume(n)`, `highest(n)` and `lowest(n)` cover the n bars ending today (first value on bar n); `ema(n)` starts on bar n at the simple mean of the first n closes, then `alpha = 2 / (n + 1)`; `ret(n)` is `close[t] / close[t-n] - 1` (first value on bar n + 1).
**Why it matters:** a different EMA seed changes values for many bars, so the pullback template could disagree with the golden reference on a few dates.
**Ruling:** these conventions, as the golden reference already uses them (the TA-Lib and StockCharts convention for the EMA seed).

<a id="X-1"></a>
## X-1: which date does `entries.hash` use?

**Status:** ruled (owner, 2026-10-07).
Spec 0002 says `entries.hash` is the sha256 of the sorted `ticker|entry_date` lines. `Trade.entry_date` is the fill date (signal bar + 1).
**Tests assume:** the fill date, the same as `Trade.entry_date` (`test_backtest.py` B-16 and `test_exit_lab.py` X-1).
**Ruling:** the fill date (signal bar + 1), the same value as `Trade.entry_date`. X-1's entry triple pairs the date with the entry price, which is the fill price.

<a id="X-10"></a>
## X-10: how can QA see that random entries are alive and never on a last bar?

**Status:** ruled (owner, 2026-10-07).
The trade lab response carries the random counts and metrics, but no random entry list or hash, so "all on alive tickers and none on a last bar" cannot be checked through the public API.
**Ruling:** option 2, no contract change. QA checks what the API shows: the random counts equal the strategy's IS and OOS counts, the same seed gives identical random results, another seed changes them, and edge equals strategy minus random. "Alive and never on a last bar" is covered by the BE unit tests and the owner's B-10 oracle; QA records that it cannot check this part independently. The placeholder test was removed, and the matrix row names the other coverage.
**Options that were considered:** an additive `entries.random_hash`, or a capped random entry list (contract change, minor bump).

<a id="D-1"></a>
## D-1 to D-3: the synthetic generator's entry point

**Status:** ruled (feature 7 on `main` names the entry points, spec 0006).
The hook `load_synthetic_market(seed)` in `tests/acceptance/test_data.py` now calls `engine.synthetic.generate(seed)`, and one test reads the `python -m engine.synthetic --seed 42 --out DIR` output back with `engine.data.read_market`. D-1 to D-3 pass on `main` and are `required` since 2026-10-08.
D-3's "bear segment" is **ruled** (owner, 2026-10-07): the benchmark closes at least 20% below its running peak at some point. This is what the tests check; feature 7's spec should generate to it.

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

**Status:** owed (QA follow up), partly written.
Doc 02 section 15.4 puts these in `apps/web/tests/acceptance/` as Vitest tests against the mocks. Vitest runs that folder (one line added to `apps/web/vitest.config.mts`), and those tests always block CI through `pnpm --filter web test`.

**Written** (against the shipped app shell, spec 0003):
- U-1, banner part: `data-mode-banner.test.tsx`. The synthetic banner is the first thing in `main` on every page, while the health ping is pending, after a synthetic answer and after a failure, and it has no close button.
- U-2: `data-mode-banner.test.tsx`. A `live` health answer swaps in the live text on every page. The "badge" is the shell's data mode banner, with the words spec 0003 AC-4 fixes; doc 01 names only the meaning.
- U-5: `warmup.test.tsx`. A health ping delayed 2.5 s shows "Warming up the engine…" after 1.5 s (not at 1.2 s) and clears when the answer lands; a fast answer never shows it; the 1,499 and 1,500 ms edges and the restart are checked on `WarmupNotice` with fake timers.
- U-6, structure only: `layout-375.test.tsx`. No page carries a fixed width over 375 px, every table sits in its own labelled scroll box, and `FormRow` is one column unless the `sm` breakpoint applies.
- U-4, components: `honesty.test.tsx`. `RunTrialCounter` on the mock `trial` blocks and seeded storage: the counter line, a numbers only tweak adding to the same `N`, re runs and re renders adding nothing, `M` across structure keys, k pairs per exit lab run, the spec 0004 storage keys, `N` surviving a new session, no warning at 9 and the warning word for word at 10 and above, unparsable values treated as empty, and either store throwing hiding the counter behind the static warning. The `/ui` gallery shows every state.
- U-8, words: `honesty.test.tsx`. `ProcedureNote` renders the doc 01 text word for word, as body text, and the `/ui` gallery shows it.
- U-7, shared helpers: `errors-422.test.tsx`. The 422 mocks come back through the `api` client and `fieldErrorsFrom422`, land on the named field (`aria-invalid`, the message as its description) and on no other row; a body level error shows in `FormErrorSummary`.

**Still owed** (the UI does not exist yet, so the IDs stay `pending`):
- U-1: the workspace on `/` opening with Breakout and its scan results (feature 8) is written in `template-scan.test.tsx` through the `acIt` gate, so it runs but cannot fail CI until U-1 is `required`; the editable builder (feature 10) is still owed.
- U-6: real builder rows stacking (feature 10), and anything that needs layout: `scrollWidth` at 375 px and the actual column stacking. jsdom has no CSS, so these stay a browser check in `/check verify` until Playwright is added (spec 0003 follow up).
- U-7: the real builder row and exit config editor showing the error (features 10 and 12).
- U-4: the counter inside the portfolio report (feature 9) and the exit lab report (feature 12), and no count for a failed run. `it.todo` in `honesty.test.tsx`.
- U-8: the note directly under the exit lab table (feature 12). `it.todo` in `honesty.test.tsx`.
- U-3 (report header), R-1 and R-8 (builder), X-3, X-4 and X-9 (exit lab report): no UI yet.

Each ID keeps its pending placeholder in `tests/acceptance/`, plus a contract level test where one applies (U-3 fields, U-7 error paths, U-4 trial keys, X-3 `best_is`, X-4 null R). U-2 is `required` since 2026-10-08: its placeholder is now a pointer (`ui_covered_by`) that checks the Vitest file exists and owes nothing for the ID. U-5 is fully covered too and flips the same way in its own PR.

<a id="perf"></a>
## S-4, B-13 and X-7: where the time budgets are measured

**Status:** ruled (owner, 2026-10-07).
The criteria name the deployed API (S-4, X-7) or a warm run (B-13). CI never calls the deployed API, so the acceptance tests time the use case in process on a seeded 500 ticker, 1,260 bar random walk.
**Tests assume:** an in process pass is the CI gate, and the deployed numbers are a `/check verify` step (`make smoke`).
**Ruling:** the split stands. The in process timing is the CI gate; the deployed numbers for S-4 and X-7 are a `/check verify` step after a deploy (`make smoke`). Once feature 7 lands, the tests switch to the real synthetic market.

<a id="AC-10-url"></a>
## U-1 (spec 0005 AC-10): how the workspace changes the URL

**Status:** ruled (2026-10-08): test the behaviour, not the API.
AC-10 says switching templates uses `router.replace`. In the real browser (verify of #29 with #21, 2026-10-08), switching changes the URL with no new history entry, and an unknown `?template` is dropped from the URL. Both behaviors are correct. Two Vitest tests in `template-scan.test.tsx` (#23) emulate `next/navigation` and expect `useRouter().replace` to be called, and they never see the call, so the pending gate skips them.
**Ruling:** assert on what the user sees, not on which API changed it. The two tests now check the URL's `template` search parameter in `window.location` and an unchanged `history.length` (no new history entry). The `next/navigation` emulation routes `router.replace` / `push` through `window.history`, so `router.replace` and `history.replaceState` both pass. The same reading covers "runs the scan for the new template": switching back to a template already scanned may be served from the query cache (the market is fixed, so the answer is identical), so the switching test gives each template its own tickers and checks the rows on screen, not that a second request went out.

<a id="feature-8"></a>
## Feature 8 (template scan): readings the tests take

**Status:** open (spec 0005 is In Progress; nothing here blocks the build).
- **Exception type for a bad `as_of`.** Spec 0005 says `engine.api.scan` "raises the `as_of_not_session` validation error" but freezes no exception class. **Tests assume:** any exception whose message or `errors()` names `as_of_not_session`; the HTTP test checks the full 422 shape (`type`, `loc`, `ctx`).
- **`/scan` needs a market, CI has none.** The API loads its market at import from `SYNTHETIC_DATA_DIR` (AC-8), and `make test` runs without `make data`. **Tests assume:** the route tests generate the seed 42 market into a temp folder with `python -m engine.synthetic` and run the real app in a fresh process with `SYNTHETIC_DATA_DIR` set. They read the stdout scan log line there too. A builder who wants the session `client` to carry a market can say so here.
- **The UI words the spec leaves open.** AC-11 fixes the columns but not the header words for % change and volume ratio, nor the badge word beyond "New". **Tests assume:** headers matching `/change/i` and `/vol(ume)? ratio/i`, a `New` header, and a badge whose text is exactly `New`. The template dropdown is a combobox named `Template` (native `select` or Base UI).
- **`next/navigation` in jsdom.** The tests emulate `useRouter`, `useSearchParams` and `usePathname` with a small store backed by jsdom's `window.location` and `window.history` (either history call re renders). **Tests assume:** the workspace reads the template from `useSearchParams`; how it rewrites the URL is not asserted (see [AC-10-url](#AC-10-url)).
- **Conditions text.** Each condition is checked as one element whose whole text is `<left label> <op> <right>`, e.g. `volume > 1.5×avg_volume(50)` and `close > 5` (spec 0005 value sourcing).

<a id="U-4"></a>
## U-4: what the session total `M` counts, and which storage failure hides the counter

**Status:** open (spec 0004 is "Assumed", not ratified by `/architect`).
Doc 01 U-4 says "a global session total across all rules is kept in sessionStorage" but not whether it counts runs or distinct pairs, and "storage unavailable" does not say which store. Spec 0004 assumes `M` is the number of distinct pair keys run this session (a re run adds nothing; a pair first seen in an earlier session counts once toward `M` but not again toward `N`), and that either store throwing hides both counters.
**Tests assume:** spec 0004 as written, including its storage keys (`swing-scan:trials:v1:<structure_key>`, `swing-scan:session-trials:v1`). `honesty.test.tsx` checks the keys directly, so a ratification that changes the layout changes those tests. U-4 stays `pending` anyway until the counter is in the reports (features 9 and 12).

<a id="U-8"></a>
## U-8: "one line" in a DOM test

**Status:** owed (feature 12, plus a browser check).
jsdom applies no CSS, so it cannot see whether the note wraps to a second line at a given width. **Tests assume:** "one line" means one sentence pair of body text with no line break, not fine print (spec 0004, assumption 5). Whether it wraps at 375 px is a `/check verify` browser check. The placement under the exit lab table waits for feature 12.
