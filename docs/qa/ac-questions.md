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

**Status:** owed (QA follow up), all but U-6 written. R-1, R-8 and U-1 are `required` since 2026-10-08; X-3, X-4, X-9, U-3, U-4, U-7 and U-8 since 2026-10-10, when the exit lab page (feature 12 FE milestone 5, PR #74) landed and the tests below were written against it. Only U-6 is still owed, and it needs a browser, not a page.
Doc 02 section 15.4 puts these in `apps/web/tests/acceptance/` as Vitest tests against the mocks. Vitest runs that folder (one line added to `apps/web/vitest.config.mts`), and those tests always block CI through `pnpm --filter web test`.

**Written** (against the shipped app shell, spec 0003):
- U-1, banner part: `data-mode-banner.test.tsx`. The synthetic banner is the first thing in `main` on every page, while the health ping is pending, after a synthetic answer and after a failure, and it has no close button.
- U-2: `data-mode-banner.test.tsx`. A `live` health answer swaps in the live text on every page. The "badge" is the shell's data mode banner, with the words spec 0003 AC-4 fixes; doc 01 names only the meaning.
- U-5: `warmup.test.tsx`. A health ping delayed 2.5 s shows "Warming up the engine…" after 1.5 s (not at 1.2 s) and clears when the answer lands; a fast answer never shows it; the 1,499 and 1,500 ms edges and the restart are checked on `WarmupNotice` with fake timers.
- U-6, structure only: `layout-375.test.tsx`. No page carries a fixed width over 375 px, every table sits in its own labelled scroll box, and `FormRow` is one column unless the `sm` breakpoint applies.
- U-4, components: `honesty.test.tsx`. `RunTrialCounter` on the mock `trial` blocks and seeded storage: the counter line, a numbers only tweak adding to the same `N`, re runs and re renders adding nothing, `M` across structure keys, k pairs per exit lab run, the spec 0004 storage keys, `N` surviving a new session, no warning at 9 and the warning word for word at 10 and above, unparsable values treated as empty, and either store throwing hiding the counter behind the static warning. The `/ui` gallery shows every state.
- U-8, words: `honesty.test.tsx`. `ProcedureNote` renders the doc 01 text word for word, as body text, and the `/ui` gallery shows it.
- U-3, portfolio report: `backtest-report.test.tsx`, against `/backtest` on the mocks (plain `it`, so it blocks). After "Run backtest", an "Assumptions" region comes before the results, with one term per `Assumptions` field (spec 0007 AC-12), and each doc 01 item (fill model, slippage, sizing, max positions, rising edge, cooldown 10, no last bar entry, the config's exit rules, horizon and seed as "not used in portfolio mode", delisting, OOS date, data mode, version and seed) shows the response's value; a result with distinct values and a live result show those values, not the form's. `/backtest` is now in `pages.tsx`, so the "every page" banner and 375 px structure checks cover it.
- R-1, R-8 and U-1 (builder part): `rule-builder.test.tsx`, against the builder on `/` (feature 10, spec 0008). R-8: edits, an added row (decision 8's `close > sma(50)`, then an indicator and a Number right side) and a removed row reach `POST /scan` exactly as the rows read back, and a rule pasted into the JSON panel becomes rows that read back as the same JSON. R-1: the first edit switches the link to `?r=` (it decodes, by spec 0008 decision 3, to the rows), and reopening that address gives the same rows and scans the same rule; a `?r=` built in that encoding (every operand shape, non ASCII name) opens that exact rule. U-1: the builder opens holding Breakout's rule and scans it.
- U-7, pages: `rule-builder.test.tsx`. A 422 on row 2's left "Bars ago" lands on that field only, and a 422 on the stop's `pct` lands on "Stop loss (%)" on `/backtest`, not on the time exit. Right side paths, with the real API's union tag, land on their field since PR #60 ([U-7-loc](#U-7-loc), ruled (a)): row 2's right `n` (`right.ind.n`) on its "Window (n)", and row 3's right Number (`right.value.value`, added 2026-10-09) on its "Number", with no other row marked.
- U-7, shared helpers: `errors-422.test.tsx`. The 422 mocks come back through the `api` client and `fieldErrorsFrom422`, land on the named field (`aria-invalid`, the message as its description) and on no other row; a body level error shows in `FormErrorSummary`.
- X-3, X-4, X-9, U-3, U-4, U-7 and U-8, exit lab report: `exit-lab-report.test.tsx`, against `/backtest` switched to the lab (the "Exit lab" radio, then "Run exit lab") on the `backtest.trade_lab.json` mock (plain `it`, so it blocks). The table is read through its header cells, each carrying `aria-label` "<metric> IS" or "<metric> OOS", which fixes every data cell's column without reading the component. X-3: a pair of columns per metric, each row's values from the response, the "Best IS" marker in exactly the cells `best_is` names, and in no OOS, random or edge cell. X-4: the two stopless configs read "n/a" in `Expectancy (R)` and `Edge Expectancy (R)` for both segments, keep their % expectancy, point at a footnote, and the footnote explains R needs a stop and names them; a config with a stop shows its R. X-9: the warned config's row carries a worded badge and the message, no other row does, and a response with no warnings shows none. U-3: an Assumptions header before the table, one line per `Assumptions` field, every doc 01 item with the trade mode value (the horizon, the seed, "same ticker trades may overlap", `max_positions` as "not used in trade mode", one exit line per config, the baseline config), and a response with other numbers echoed, not the form's. U-4: the counter beside the header (not inside the table) reading k for k configs, one stored pair per config under the spec 0004 keys, and no counter and no stored count after a 500 or a 422. U-7: a 422 at `configs.2.exits.<i>.stop_pct.pct` marks config 3's "Stop loss (%)" with the message as its description, and marks no other config and no other field of config 3. U-8: the note word for word, outside the table's scroll box and the first thing after it, as body text.
- U-4, in the portfolio report: `backtest-report.test.tsx`. The counter is inside the Assumptions region once a 200 result is on screen, with the mock's one pair stored; a 500 shows no counter and stores nothing.

**Still owed:**
- U-6: real builder rows stacking (the builder is on `/` now; jsdom cannot see stacking), and anything that needs layout: `scrollWidth` at 375 px and the actual column stacking. jsdom has no CSS, so these stay a browser check in `/check verify` until Playwright is added (spec 0003 follow up). U-6 is the only UI ID left `pending`, and no page will change that.

Each ID keeps a pointer (`ui_covered_by`) in `tests/acceptance/` naming the Vitest files that cover it, plus a contract level test where one applies (U-3 fields, U-7 error paths, U-4 trial keys, X-3 `best_is`, X-4 null R); the pointer checks each file exists, names the ID in a test title and owes no `it.todo` for it. The `it.todo` placeholders for U-4 and U-8 in `honesty.test.tsx` are gone: those halves are driven through the two report files instead.

<a id="perf"></a>
## S-4, B-13 and X-7: where the time budgets are measured

**Status:** ruled (owner, 2026-10-07).
The criteria name the deployed API (S-4, X-7) or a warm run (B-13). CI never calls the deployed API, so the acceptance tests time the use case in process on a seeded 500 ticker, 1,260 bar random walk.
**Tests assume:** an in process pass is the CI gate, and the deployed numbers are a `/check verify` step (`make smoke`).
**Ruling:** the split stands. The in process timing is the CI gate; the deployed numbers for S-4 and X-7 are a `/check verify` step after a deploy (`make smoke`). Once feature 7 lands, the tests switch to the real synthetic market.

<a id="X-7-margin"></a>
## X-7: the budget passes locally, but how much margin does CI have?

**Status:** QA reading (2026-10-10), no builder dispute; the owner can overrule it. X-7 stays `pending` for now.
Feature 12's budget work (PR #63) is on `main`, and both X-7 tests pass: the gate prints X-7 as "pending and fully passing". Measured here through `engine.api.backtest` on the seed 42 market, 6 configs plus the baseline, warm, on an Apple Silicon dev machine: `breakout_52w` 0.81 s, `pullback_ema21` 4.48 s, body 0.64 MB each (the budget is 10 s and 6 MB).
**Why it is not flipped:** the pullback template uses 4.5 s of the 10 s on the fastest machine this project runs on. A GitHub hosted runner is commonly 2x slower on plain Python, which puts that run at the limit, and X-7 is the one budget whose own criterion names the deployed API, where nothing has been timed yet. A flip now would make CI's slowest runner the gate, so a timing flake, not a regression, would turn `main` red.
**What X-7 needs to flip:** a warm `pullback_ema21` number from CI (or the same machine class) with room to spare, say under 5 s of the 10 s budget, and ideally the deployed number from feature 15's `make smoke`. Either the margin shows on CI and X-7 flips as it stands, or the budget test is split so the CI gate times a fixed size market and `make smoke` owns the deployed number (a QA change, no contract change).
**Tests assume:** nothing new. Both X-7 tests already run on every CI pass as non strict xfail, so the numbers are visible in the log before anyone flips the ID.

<a id="mode-split"></a>
## S-3, B-13 to B-16: which half each criterion needs before it flips

**Status:** QA reading (2026-10-09), no builder dispute; the owner can overrule it. Every half is now met: S-3, B-13 to B-16 are `required`.
Doc 01 S-3, B-13 to B-16 name no mode, and their old tests ran the exit lab (trade mode, feature 12), so they stayed `pending` behind `NotYetImplemented` after feature 9 merged. Spec 0007's test plan says which halves gate feature 9: "the portfolio tests in B-14, B-15 and B-16", AC-7 (B-13) in portfolio mode, and "the parity test ... the trade mode halves of B-15, B-16" with feature 12. Spec 0009 AC-1 maps the exit lab's entry list to X-1 (with B-14 to B-16), and its budget test owns "run twice equal" in trade mode.
**Tests assume:**
- S-3: `new_today` equals the golden reference and a portfolio run's entries (20 slots for 20 tickers, a 1 bar time exit, so every signal is entered). The same parity against the exit lab's entries is tagged X-1. S-3 is `required`.
- B-13: portfolio determinism, plus the 3 s and 6 MB budget on the generated seed 42 market for both templates (the [perf](#perf) ruling's "once feature 7 lands" switch) and on the 500 ticker random walk. Trade mode determinism is tagged X-7. B-13 is `required`.
- B-14: portfolio runs on both fixtures; the trade mode version is tagged X-1, since neither spec names a B-14 trade mode half. B-14 is `required`.
- B-15 and B-16: the portfolio tests pass (B-16 with every exit type), and both specs name a trade mode half (B-16 says "in every exit config"). The trade mode halves pass since feature 12's BE milestones 1 and 2 merged (PRs #53, #55, #59: the 501 is gone), so both are `required` since 2026-10-09. X-1, which carries B-14's trade mode check and S-3's parity on the exit lab's entries, flipped in the same PR.

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

<a id="U-7-loc"></a>
## U-7: a right side 422 path carries the operand's `kind`, and the builder does not map it

**Status:** ruled (owner, 2026-10-09): option (a), the builder strips the tag; done in PR #60 (`withoutTag` in `apps/web/src/lib/field-errors.ts`). The API keeps the tag, and BE's `services/api/tests/test_scan_rule_validation.py` pins it. Found 2026-10-08 against `main` after features 10 and 11.
The real API answers a bad right side field with the union member in the path: a right `n` of 300 on row 2 gives `loc: ["body", "rule", "conditions", 1, "right", "ind", "n"]`, a bad Number gives `[..., "right", "value", "value"]` (`test_ui.py::test_422_paths_point_at_the_row_or_exit_field` checks the first; a TestClient probe shows the second). Left side paths carry no tag (`[..., "left", "offset"]`), since `left` is always an indicator. Spec 0008's 422 table maps `conditions.i.right.<field>` and `conditions.i.right.value` to the row's right field, with no tag segment, and AC-7 says "on the exact field its `loc` names (for example row 3's right `n`)". The exit form on `/backtest` already maps the tagged path (`exits.0.stop_pct.pct` lands on "Stop loss (%)").
**What the builder does on `main`:** given the real path `right.ind.n`, the message shows as a row level message on Condition 2, and the "Window (n)" field is not marked (`aria-invalid` unset). Given the untagged `right.n`, it lands on the field. The contract mocks never show the difference: `422.rule.n_out_of_range` uses a left side path.
**Reading:** doc 01 U-7 ("the offending builder row or exit field shows the inline error") is met by the row message; spec 0008 AC-7 (ratified as written) is not, on the real API.
**Tests assume:** AC-7: the field is marked. `rule-builder.test.tsx` sends the real API's tagged paths (`right.ind.n` and `right.value.value`); both pass on PR #67's base with PR #60 merged (2026-10-09). The exit lab's config editor maps the same shape per config (`configs.2.exits.0.stop_pct.pct` marks config 3's "Stop loss (%)", `exit-lab-report.test.tsx`), so U-7 is `required` since 2026-10-10.
**Ruling needed, one of:** (a) the builder strips the `ind` / `value` tag after `right` (an FE fix, matching the exit form); (b) the API drops the tag from `loc` (a `contract-change` PR, with the `right.ind.n` assertion in `test_ui.py` updated); (c) the row message is enough for U-7, and spec 0008's table and AC-7 are amended. QA suggests (a): the exit form already does it, and the contract stays as is. Either way, a contract mock with a right side path (`422.rule.right_n_out_of_range`, say) would let the FE lane see it.

<a id="B-10-scan"></a>
## B-10: the scan half of QA's look-ahead test differs in the last bit

**Status:** ruled (owner, 2026-10-09): option (b). Found 2026-10-09 on PR #67's base, after feature 12's BE milestones 1 and 2.
Doc 01 B-10 names backtests only: "trades and equity up to T are identical". `test_backtest.py::test_a_poisoned_future_changes_nothing_up_to_t` also asks the scan at `as_of` T − 20 and T to be identical on the clean and the poisoned market. For both templates the portfolio and the trade lab responses (random baseline included) are now identical. For the pullback template the scan is not: one ticker's `sma(50)` operand differs in the last binary digit at T − 20 (33.324742030926174 against 33.32474203092618), and at T one ticker's `vol_ratio` does too (1.680529991534194 against 1.6805299915341938). No row, `hit` or `new_today` changes.
**Reading:** bars after T reach a value up to T only through floating point (a rolling window computed over the whole series), not through the logic. QA first read "identical" as bit for bit; the owner ruled that last bit noise is not a look ahead.
**Tests assume:** the ruling. The scan half compares the two scan responses key by key: every key, row, ticker, flag (`new_today`) and list length exact, every float within 1e-12 absolute or relative (`_assert_same_up_to_float_noise` in `test_backtest.py`). The portfolio and trade mode halves stay exact. Both templates pass, and B-10 is `required` since 2026-10-09.
**Ruling:** (b). **Options that were considered:** (a) the engine computes rolling indicators so a cut at T gives bit identical values (a BE fix; the operands are what a user sees); (b) the scan half compares numbers to a relative 1e-12 and keeps rows, `hit` and `new_today` exact (a QA change); (c) the scan half moves out of B-10, which names backtests only. The owner's B-10 oracle is unaffected.

<a id="U-4"></a>
## U-4: what the session total `M` counts, and which storage failure hides the counter

**Status:** ruled (owner, 2026-10-08): spec 0004 as written. The owner ratified specs 0004, 0006, 0007, 0008 and 0009 as written.
Doc 01 U-4 says "a global session total across all rules is kept in sessionStorage" but not whether it counts runs or distinct pairs, and "storage unavailable" does not say which store. Spec 0004 assumes `M` is the number of distinct pair keys run this session (a re run adds nothing; a pair first seen in an earlier session counts once toward `M` but not again toward `N`), and that either store throwing hides both counters.
**Tests assume:** spec 0004 as written, including its storage keys (`swing-scan:trials:v1:<structure_key>`, `swing-scan:session-trials:v1`). `honesty.test.tsx` checks the keys directly.
**Ruling:** spec 0004 as written: `M` counts distinct pair keys run this session, either store throwing hides both counters, and the storage keys stand. The tests are unchanged. The counter inside both reports, and the no count on a failed run, are covered since 2026-10-10 (`backtest-report.test.tsx`, `exit-lab-report.test.tsx`), so U-4 is `required`.

<a id="U-8"></a>
## U-8: "one line" in a DOM test

**Status:** QA reading (2026-10-08), with one browser check left; U-8 is `required` since 2026-10-10.
jsdom applies no CSS, so it cannot see whether the note wraps to a second line at a given width. **Tests assume:** "one line" means one sentence pair of body text with no line break, not fine print (spec 0004, assumption 5). Whether it wraps at 375 px is a `/check verify` browser check. The placement is checked structurally instead: the note is outside the lab table's scroll box and the first element after it (`exit-lab-report.test.tsx`, spec 0009 AC-18).
