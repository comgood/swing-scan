# Scope: Swing Scan

A $0 swing trading scanner and research tool: build entry rules, backtest them honestly, and compare exit strategies on identical entries. A learning and portfolio project built in about a week with AI coding agents, never sold.

**Build approach:** Tracer Bullet (one thin, real path through every layer first, then thicken it one strand at a time).
**Workflow:** Beta (check verify, then test). The project default level of rigor. Engine features carry `· GA`, which adds a fresh model `/check review` and `/document`. `/architect` is the recommended first stop for a feature with a real decision, but skippable when you already know the build. Any feature can carry its own tag to do more or less.

_These are recommendations to keep your build orderly, not requirements. Skip anything that does not fit: if you already know how to build a feature, use `/develop` and skip `/architect`. You decide when a feature is `done`._

_Source of truth: acceptance criteria IDs (D, R, S, B, X, U) and settled defaults live in `docs/01-market-research-and-product-spec.md`. Design, the Day 1 to 7 plan, and the parallel agent lanes (DI, BE, FE, QA) live in `docs/02-technical-design-and-roadmap.md`, section 15. Each feature below names its lane._

## At a glance

| # | Feature | Phase | Status |
|---|---------|-------|--------|
| 1 | Stack & architecture | Foundation | in-progress |
| 2 | Coding standards & tooling | Foundation | done |
| 3 | Contracts & data model | Foundation | done |
| 4 | Design system & UI foundation | Foundation | done |
| 5 | Acceptance test harness & traceability | Foundation | done |
| 6 | Backtest correctness oracles | Foundation | done |
| 7 | Synthetic market | Slice 1 | done |
| 8 | Template scan | Slice 1 | done |
| 9 | Portfolio backtest core | Slice 1 | in-progress |
| 10 | Rule builder | Slice 2 | done |
| 11 | Exit types | Slice 3 | done |
| 12 | Exit lab | Slice 3 | in-progress |
| 13 | Research honesty guards | Slice 3 | done |
| 14 | Live research mode (local) | Slice 4 | done |
| 15 | Deploy hardening & demo readiness | Slice 5 | done |
| 16 | README, research note & GIF | Slice 5 | in-progress |
| 17 | Market data store | Slice 6 | in-progress |
| 18 | One command local stack | Slice 6 | planned |
| 19 | Market clock writer | Slice 6 | in-progress |
| 20 | Live refresh and push | Slice 6 | in-progress |
| 21 | Saved rules | Slice 7 | in-progress |
| 22 | Accounts | Slice 7 | planned |
| 23 | Backtest runs as jobs | Slice 7 | planned |
| 24 | Infrastructure as code | Slice 8 | planned |

## Parallel work

From here on, features run in parallel across the four agent lanes of doc 02 §15. Each lane runs one feature at a time, in its own worktree and branch, and writes only to its own folders (`CODEOWNERS`). A feature can start as soon as its gate below is open. Gates replace the old Day 1 to 7 dates.

### Gates

| Gate | What opens it | Status | What it unlocks |
|---|---|---|---|
| **G0 Contracts frozen** | `contracts-v1` tagged (feature 3) | **open** (tag on `9fd3879`) | Lane fan out: every feature marked "now" below |
| **G1 Oracles approved** | You recompute and merge QA's oracle drafts with the `oracle-approved` label (feature 6) | **open** (oracles approved in PR #9) | Engine simulator and exit work in features 9 and 11 |
| **G2 Simulator merged** | Feature 9's simulator and its single exit interface (`step()`) on `main` | **open** (`step()` and the day loop landed in #39) | Engine work in features 11 and 12 |
| **G3 Real scan API** | Feature 8's `/scan` on `main` (and on a preview deploy) | **open on `main`** (#39) and deployed (2026-10-09) | FE switches from mocks to the real API, screen by screen |
| **G4 Feature freeze** | Every MUST criterion `required` and green in `docs/qa/traceability.md` | **open** (52 required, 0 pending, 2026-10-15; D-4 and D-5 were the last two) | Feature 16, then the `v1.0` tag |

### Who can work on what, and when

| Feature | Lanes | Can start | Runs alongside | Writes to |
|---|---|---|---|---|
| 1. Stack & architecture (finish) | DI, you run the first deploy | now | everything | `infra/`, `.github/`, root config |
| 6. Backtest correctness oracles | QA drafts, you approve | now | 1, 7, 8, 10, 13, 14 | drafts in an `oracle-draft` PR; only you merge into `tests/oracle/` |
| 7. Synthetic market | DI | now | 6, 8, 10, 13 | `engine/src/engine/synthetic/`, `engine/src/engine/data/`, `scripts/` |
| 8. Template scan | BE + FE | now (`/architect` first) | 6, 7, 13 | BE: `engine/` indicators and rules, `services/api/`; FE: `apps/web/src/features/` |
| 10. Rule builder | FE now against mocks; BE after 8's rule evaluator merges | now (`/architect` first) | 6, 7, 9 | FE: `apps/web/src/features/`; BE: `engine/` rules |
| 13. Research honesty guards | FE (trial keys are already frozen in the contract) | now, against mocks | 8 to 12 | `apps/web/src/features/` |
| 14. Live research mode | DI, you run `make load-live` | now (D-5's host rule is decided in its spec) | everything | `engine/src/engine/data/`, `scripts/` |
| 9. Portfolio backtest core | BE + FE | spec now; engine after **G1** and 8's entry signals | 10, 13, 14 | BE: `engine/` sim and metrics, `services/api/`; FE: `apps/web/src/features/` |
| 11. Exit types | BE | after **G1** and **G2** | 12 (FE), 13 | `engine/` exits |
| 12. Exit lab | BE + FE | spec now; FE against mocks now; engine after **G2** | 11, 13 | BE: `engine/` baseline and sim; FE: `apps/web/src/features/` |
| 15. Deploy hardening | DI | after 1's first deploy; cold start number after 9 | everything | `infra/`, `.github/workflows/`, `services/api/Dockerfile` |
| 16. README, research note & GIF | Orchestrator + you | after **G4** (the research note needs 12) | none | `README.md`, `docs/` |

### Lane queues (one feature at a time per lane)

- **DI:** 1 → 7 → 14 → 15.
- **BE (the critical path):** 8 → 9 → 11 → 12. Keep this lane busy first; it decides the finish date.
- **FE:** 8 → 10 → 13 → 9 (report) → 12. FE works against the frozen mocks until G3, so it never waits on BE.
- **QA:** 6 (oracle drafts) → for each feature as it lands: its UI acceptance tests in `apps/web/tests/acceptance/`, then flip its IDs to `required` once green on `main`, then `/check verify`. A feature closes `done` only after this QA gate (doc 02 §15.4).
- **You:** approve the oracles (G1) as early as you can, since it is the one gate that can stall the BE lane. Run the first deploy (feature 1) and `make load-live` (feature 14). Batch your reviews twice a day.
- **Orchestrator:** `/architect` for 8, 9, 10 and 12 ahead of their lanes, then `/sync` after each merge batch.

### Rules that keep parallel work safe

- Rebase on `origin/main` at session start and before every PR. Branches are `<lane>/<feature>-<slug>`, at most 2 open PRs per lane, about 400 changed lines per PR.
- Shared root files (`Makefile`, `pyproject.toml`, root `package.json`, CI) change only through DI; other lanes ask in their PR.
- Contract changes go through a `contract-change` PR you approve. Additive optional fields can land any time; breaking changes bump the tag to `contracts-v2`.
- When QA and a builder read a criterion differently, log it in `docs/qa/ac-questions.md`; the test stays `pending` until you rule. Nobody edits the other lane's files.

## Foundations

Done in order on Day 1 before the lanes fan out. Feature 3 ends with the `contracts-v1` tag and your sign offs (SO-1 to SO-3); feature 6 must be approved before engine work in feature 9 starts.

### 1. Stack & architecture · in-progress
Lane DI. Record the stack already chosen in doc 02 (Next.js on Vercel Hobby, FastAPI with Polars and NumPy in a Lambda container, GitHub Actions with OIDC) and scaffold a runnable monorepo with a hello world deploy of both apps.
**Done when:** the stack is captured in a spec, the empty web app and API both run locally, and both are reachable on their free tier hosts.
- [x] Decide the stack (spec): `/architect stack & architecture`
- [x] Scaffold from the decision: `/develop stack & architecture` (local scaffold done; first deploy done 2026-10-09: the API on a Lambda Function URL in `ap-southeast-1`, the web app on `https://swing-scan-one.vercel.app`, `make smoke` passes, the throttle alarm emails you; no reserved concurrency because the account quota is 10). Cold start, the number doc 01's "cold start ≤ 10 s" is about, is **2.66 s measured 2026-10-14** on an idle function (3.1 s on the first deploy). The first call right after a deploy is a different and much slower number, 9.33 s then 13.94 s, because Lambda optimises each newly pushed image; `infra/README.md` §6 keeps both apart
- [ ] Verify it: `/check verify stack & architecture`
- [ ] Test it: `/test stack & architecture`
Spec [0001](../specs/0001-stack-architecture/index.md) · code in `./` (`apps/web`, `services/api`, `engine`)

### 2. Coding standards & tooling · done
Lane DI. Capture conventions from the real scaffold into root `AGENTS.md` (including lane ownership, the protected `tests/oracle/` folder, and the no real data rule), then install lint, format, typecheck, CI, secret scanning, the data leak guard, and `CODEOWNERS`.
**Done when:** root `AGENTS.md` reflects the real stack and lanes, CI runs lint, typecheck and tests on every PR, and a commit with price data or an API key is blocked (D-6).
- [x] Capture conventions + tooling choices: `/audit`
- [x] Build it: `/develop tooling`
  - [x] Ruff lint and format, mypy strict (engine, api, scripts)
  - [x] Prettier with ESLint in the web app
  - [x] pre-commit: gitleaks, data leak guard (D-6), oracle guard
  - [x] CI (checks + guards, oracle label check), `CODEOWNERS`, `make ci`
Spec [0001](../specs/0001-stack-architecture/index.md) · code in `.pre-commit-config.yaml`, `.github/`, `scripts/guards/`, `Makefile`

### 3. Contracts & data model · done
Lane orchestrator with your sign off. Freeze the shared shapes every lane builds against: rule JSON schema with Pydantic and generated TypeScript types, the bars schema, the exit config schema, the OpenAPI contract with mock responses, and the test fixture format.
**Done when:** contracts are tagged `contracts-v1`, mocks validate against the schema in CI, the generated client compiles, and you have signed off SO-1 to SO-3.
- [x] Design it (spec): `/architect contracts & data model`
- [x] Build it: `/develop contracts & data model`
  - [x] Thin thread: rule models, `/scan` (422 then 501), OpenAPI and generated client, one mock through MSW in Vitest (AC-1, AC-2, AC-5, AC-6, AC-13, AC-15)
  - [x] Full shapes: exits, sim, backtest responses, static GET routes, trial keys (AC-3, AC-4, AC-6 to AC-9, AC-14)
  - [x] Data and fixtures: market schema, `validate_market`, fixture loader and builder (AC-10, AC-11)
  - [x] Mocks and freeze: `make mocks`, every MSW handler, CI drift checks, SO-2 and SO-3, tag `contracts-v1` (AC-1, AC-12, AC-13, AC-16)
- [x] Verify it: `/check verify contracts & data model`
- [x] Test it: `/test contracts & data model`
Spec [0002](../specs/0002-contracts-data-model/index.md) · code in `engine/src/engine/contracts/`, `engine/src/engine/data/fixtures.py`, `services/api/src/api/routes/`, `contracts/`, `packages/api-client/`, `apps/web/src/mocks/`

### 4. Design system & UI foundation · done
Lane FE. A small, calm visual language and base components: page layout, data table, form controls, number inputs, banners, and loading and error states.
**Done when:** base components exist, are keyboard usable with visible focus and readable contrast, inputs are labelled, and layouts hold at 375 px (U-6).
- [x] Design it (spec): `/architect design system & UI foundation`
- [x] Build it: `/develop design system & UI foundation`
  - [x] Thin thread: tokens, shadcn `base-nova`, app shell with the data mode banner, `/ui` gallery, first Vitest and axe test (AC-1 to AC-4, AC-15, AC-16)
  - [x] Forms: fields, number input, 422 to field mapping (AC-5 to AC-7)
  - [x] Data display: data table, formatters, badges and cards (AC-8, AC-11, AC-12)
  - [x] Feedback and hardening: banners, warm up notice, error states, keyboard, 375 px, axe on every section (AC-9 to AC-11, AC-13, AC-14, AC-16)
- [x] Verify it: `/check verify design system & UI foundation`
- [x] Test it: `/test design system & UI foundation`
Spec [0003](../specs/0003-design-system-ui-foundation/index.md) · design in `apps/web/design.md` · code in `apps/web/src/components/`, `apps/web/src/lib/`, `apps/web/src/app/ui/`

### 5. Acceptance test harness & traceability · done
Lane QA. The independent test suite, written from doc 01 criteria and the contracts only, never from builder code: `tests/acceptance/`, `tests/golden/`, a pending or required status gate in CI, and an AC to test matrix in `docs/qa/`.
**Done when:** every MUST criterion in doc 01 has a row in the matrix and a test marked pending or required, and CI fails only on required tests.
- [x] Build it: `/develop acceptance test harness`
  - [x] Gate: `status.yaml`, the `ac` marker, pending as non strict xfail, gate summary, `make test-acceptance`
  - [x] Golden reference for rule evaluation and entry signals, with self tests
  - [x] Acceptance tests for all 52 MUST IDs (3 required, 49 pending)
  - [x] Matrix and criteria questions in `docs/qa/`, kept in step by a harness test
No spec (built from doc 02 section 15.4) · code in `tests/acceptance/`, `tests/golden/`, `docs/qa/`

### 6. Backtest correctness oracles · done · GA
Lane QA drafts, you approve. Hand computed fixtures for each fill and exit rule plus the poisoned future look ahead test, kept in the protected `tests/oracle/` folder.
**Done when:** B-1, B-2, B-7 to B-10 and B-14 to B-16 exist with hand calculations you have recomputed and approved; agents cannot edit the folder.
- [x] Write and approve the oracles: `/test backtest oracles` (approved in PR #9, code in `tests/oracle/`)

## Slice 1: Thin real thread (walking skeleton)

Generated data, one template scan, one simple backtest, shown on the deployed page. Every layer real, just narrow.

### 7. Synthetic market · done
Lane DI. A seeded generated market of 500 invented tickers over 5 years with regimes, planted delistings, and a demo index, built into the API image.
**Done when:** the same seed gives identical data, every bar passes sanity checks, and at least one bear segment and 20 delisted tickers exist (D-1 to D-3).
- [x] Design it (spec): `/architect synthetic market` (signed off by the owner 2026-10-08)
- [x] Build it: `/develop synthetic market` · spec [0006](../specs/0006-synthetic-market/index.md) (signed off by the owner 2026-10-08) · code in `engine/src/engine/synthetic/`, `engine/src/engine/data/`
- [x] Verify it: `/check verify synthetic market` (D-1 to D-3 pass; the linux/amd64 image build still needs an x86 runner, since it segfaults under emulation on Apple Silicon. See [the report](../reviews/2026-10-08-verify-synthetic-market.md))
- [x] Test it: `/test synthetic market` (54 engine tests pass; QA still owes the D-1 to D-3 acceptance hook)

### 8. Template scan · done
Lanes BE and FE. Indicators, rule evaluation with the valid rising edge and the signal based cooldown, the two templates, the `/scan` endpoint, and a sortable results table on the landing page.
**Done when:** a first visit opens the Breakout template with today's hits and the synthetic banner, delisted tickers never appear, scan and backtest signals match, and a warm scan answers in under a second (S-1 to S-4, R-10, U-1, U-5).
- [x] Design it (spec): `/architect template scan`
- [x] Build it: `/develop template scan`
  - [x] Thread: BE engine slice with the shared entry signal function and `/scan` on fixtures; FE workspace with the template dropdown, conditions and results from the mocks (AC-1, AC-4, AC-5, AC-8, AC-9, AC-11, AC-13)
  - [x] Engine breadth (BE): all 14 indicators, crosses, the locked and pinned cache (AC-2, AC-3, AC-7)
  - [x] Scan contract (BE): `chg_pct`, `vol_ratio`, golden parity, `as_of` 422, warm start, the scan log, the S-4 timing test, and `read_market()` once feature 7 merges (AC-4 to AC-8, AC-13)
  - [x] Workspace finish (FE): `?template` URL, number formats, New badge, paging, states, 375 px; switch to the real API at G3 (AC-10 to AC-12, AC-14)
- [x] Verify it: `/check verify template scan`
- [x] Test it: `/test template scan`
Spec [0005](../specs/0005-template-scan/index.md)

### 9. Portfolio backtest core · in-progress · GA
Lanes BE and FE. The portfolio simulator with next open fills, % stop and time exit, equal weight, max positions, slippage, delisting exits, IS and OOS split, an equity curve against the benchmark, a trade list with MAE and MFE, and the report page with its assumptions header.
**Done when:** all approved oracles pass, results are deterministic, the top ranked signals fill free slots, and the report shows IS and OOS side by side with the assumptions header (B-1, B-2, B-7 to B-11, B-13 to B-16, U-3).
- [x] Design it (spec): `/architect portfolio backtest core` (signed off by the owner 2026-10-08)
- [x] Build it: `/develop portfolio backtest core`
  - [x] BE thread: `Exit` protocol, one `step()`, `stop_pct`, `time`, delisting, `end_of_test`, `walk_trade()`, the day loop and a minimal `PortfolioResult` behind `/backtest` (AC-1 to AC-3, AC-8, AC-11)
  - [x] BE portfolio rules and metrics: ranking, slots, sizing, window cut, IS and OOS, metrics, curves, truncation, `trial`, `assumptions`, the 3 s and 6 MB budget (AC-4 to AC-7, AC-9, AC-10); B-9 and B-10 portfolio turn green with feature 11's exits
  - [x] FE report page: `/backtest` with the exit form, assumptions header, IS and OOS metrics, equity chart, trade list, trial counter and every state, on mocks first (AC-12 to AC-17)
- [x] Verify it: `/check verify portfolio backtest core` (2026-10-14, real browser on the seed 42 market: all 17 ACs met, including the truncation line at 2,382 trades. AC-17's "axe clean" failed first: the chart's TradingView attribution link sat inside its `role="img"` box, fixed here and re-checked clean)
- [x] Test it: `/test portfolio backtest core` (engine response assembly, metric nulls, thinning and ranking gaps in PR #83; report page states, metrics table, exit form and chart in PR #85; no bugs found)
- [x] Review it (fresh model): `/check review portfolio backtest core` ([findings](../reviews/2026-10-09-review-9-backtest-engine.md); the two major findings are fixed)
- [ ] Document it: `/document portfolio backtest core`
Spec [0007](../specs/0007-portfolio-backtest-core/index.md)

## Slice 2: Rule builder

### 10. Rule builder · done
Lanes BE and FE. Build your own entry rules: a flat AND list of up to 8 conditions over 12 indicators, with numbers or indicators on the right side, crosses, offsets, and clear validation. The templates load into it as editable starting points.
**Done when:** rules round trip as JSON, crosses and offsets behave as specified, warm up bars evaluate as not computable, invalid rules return a clear 422 shown on the right row, and the structure key ignores numbers (R-1 to R-9, U-7).
- [x] Design it (spec): `/architect rule builder` (signed off by the owner 2026-10-08)
- [x] Build it: `/develop rule builder`
  - [x] FE thread: reducer over the contract `Rule`, one editable row, "Run scan" on the mocks, UI to JSON parity (AC-4, AC-8)
  - [x] FE rows and links: every field, add and remove limits, catalog hints, 422 on the right field, `?template` to `?r=` links, bad link fallback, JSON panel (AC-1 to AC-3, AC-5 to AC-7, AC-9)
  - [x] FE finish: 375 px and 320 px, keyboard, axe, `/ui` gallery, mounted in feature 8's workspace, real API at G3 (AC-10)
  - [x] BE tests after feature 8's evaluator merges: R-3, R-4, R-5, R-7 on custom rules, every R-6 case through `/scan` (AC-11, AC-12; AC-13 is already met by spec 0002)
- [x] Verify it: `/check verify rule builder` (2026-10-14, real browser on the seed 42 market: all 13 ACs met, axe clean at 1280 and 375 px with every row open; the chart `nested-interactive` finding belongs to feature 9)
- [x] Test it: `/test rule builder`
Spec [0008](../specs/0008-rule-builder/index.md)

## Slice 3: Exit research

### 11. Exit types · done · GA
Lane BE. Add the remaining exits behind the same exit interface: ATR stop, % target, trailing stop, and close below a moving average filled at the next open, with stops checked before targets.
**Done when:** each exit passes its oracle and the per bar precedence holds (B-3 to B-6). Rests on the spec from feature 9.
- [x] Build it: `/develop exit types`
Spec [0007](../specs/0007-portfolio-backtest-core/index.md) · code in `engine/src/engine/exits/`

### 12. Exit lab · in-progress · GA
Lanes BE and FE. Hold one entry rule fixed and compare 2 to 6 exit setups on identical entries, trade by trade, with a random entry baseline run through the same exits.
**Done when:** entries are identical across configs, metrics are per trade only with IS and OOS columns, the best IS config is highlighted, MAE and MFE guides use IS trades only, expectancy per bar, distinct entry weeks and horizon exits show, edge versus random is reported, and six configs finish within the time budget (X-1 to X-5, X-7 to X-10).
- [x] Design it (spec): `/architect exit lab` (signed off by the owner 2026-10-08)
- [x] Build it: `/develop exit lab`
  - [x] BE trade mode thread (after G2, PR #31): per trade loop over `walk_trade()` with the horizon, shared entries, per trade metrics, `best_is`, `guides_is`, warnings, still 501 for 2 to 6 configs (AC-1, AC-3 to AC-7, AC-9, AC-12)
  - [x] BE random baseline and edge, then drop the 501; B-10 trade mode and parity (AC-2, AC-8, AC-10)
  - [x] BE budget: 6 configs plus baseline under 10 s and 6 MB on seed 42 (AC-11, `engine/tests/sim/test_lab_budget.py`; the hot loop moved to plain lists and slotted dataclasses)
  - [x] FE exit lab table on the mock: IS and OOS pairs, best IS highlight, R n/a footnote, horizon badge, edge and random rows, `ProcedureNote` directly under, guide row (AC-13 to AC-18)
  - [x] FE page wiring on `/backtest` after feature 9's report page: 2 to 6 config form, assumptions, trial counter, states, 375 px (AC-19, AC-20; `lab-configs.tsx`, `exit-fields.tsx`, the `mode` switch in `backtest-report.tsx`)
  - [ ] BE enforcement split (amended AC-11, measured 2026-10-11): the fixed size market becomes the hard CI gate, the seed 42 pair reports its numbers and fails at 2x, `x-compute-ms` and `x-cache` headers let smoke prove a warm call, and feature 15's smoke owns the deployed 20 s budget
- [ ] Verify it: `/check verify exit lab`
- [x] Test it: `/test exit lab`
- [x] Review it (fresh model): `/check review exit lab` ([findings](../reviews/2026-10-09-review-11-12-exits-and-lab.md), shared with feature 11; both majors fixed in PR #75)
- [ ] Document it: `/document exit lab`
Spec [0009](../specs/0009-exit-lab/index.md)

### 13. Research honesty guards · done
Lanes FE and BE. The things that stop you fooling yourself: the structure keyed trial counter with a session total and a warning at 10, the procedure note under the exit lab table, and the data banners.
**Done when:** tweaking only numbers still counts toward the same rule's trials, the warning shows at 10, the procedure note renders, and the synthetic and survivors only banners appear in the right modes (U-2, U-4, U-8).
- [x] Design it (spec): `/architect research honesty guards` (signed off by the owner 2026-10-08)
- [x] Build it: `/develop research honesty guards`
  - [x] Trial store, counter and procedure note in `features/honesty/` (U-4, U-8; spec 0004 AC-1 to AC-7)
  - [x] `/ui` gallery with every state, U-2 shell banner confirmed (spec 0004 AC-8, AC-9)
- [x] Verify it: `/check verify research honesty guards`
- [x] Test it: `/test research honesty guards`
Spec [0004](../specs/0004-research-honesty-guards/index.md) (signed off by the owner 2026-10-08) · code in `apps/web/src/features/honesty/` · placed by features 9 and 12

## Slice 4: Live research mode

### 14. Live research mode (local) · done
Lane DI, run by you. Load Alpaca free daily bars since 2016 for about 500 current S&P 500 names plus SPY into the same schema, on your machine only.
**Done when:** `make load-live` fills local data with keys from the environment, the API refuses live mode anywhere but localhost, and `research/` is ignored by git (D-4, D-5).
- [x] Build it: `/develop live research mode` (assumed decisions, spec 0010; you run `make load-live`)
- [x] Verify it: `/check verify live research mode` (2026-10-15, a real `make load-live` with your keys: 502 tickers plus SPY, 770,552 bars, 2017-11-15 to 2026-10-14, 1 missing symbol, 97 bars dropped; the dataset serves through the API in live mode and a 52 week breakout scan on it returns real hits. D-5 driven against a real uvicorn down all five refusal paths, each exiting 1, with loopback still starting)
- [x] QA gate: D-4 and D-5 flipped to `required`, which **opens G4** at 52 required and 0 pending. The hooks both tests were owed are now real: D-4 reads `data/live` through `read_market` and skips where there is none, so CI stays green while the owner's local run is the evidence; D-5 drives `Settings.from_env` over every host spelling and both markers
Spec [0010](../specs/0010-live-research-mode/index.md) (Assumed, and the first real load corrected three of its assumptions: `feed=iex` not `sip`, and 2017-11-15 not 2016-01-04) · code in `engine/src/engine/live/`, `services/api/src/api/settings.py`

## Slice 5: Ship

### 15. Deploy hardening & demo readiness · done
Lane DI. Make the public demo dependable at $0: OIDC deploys, a $1 budget alarm, the warm up ping, response size limits, a measured cold start, and the Day 1 checks (Alpaca terms, GitHub's 60 day rule, the Lambda 6 MB limit).
**Done when:** a merge to main deploys both apps without stored keys, the budget alarm exists, cold start is measured and recorded, and every response stays under the size limit.
- [x] Build it: `/develop deploy hardening` (PR #73: OIDC deploys with no stored keys, the keep alive ping, the $1 budget and throttle alarms, response size guards in `scripts/smoke.sh`; cold start recorded in `infra/README.md` §6, 2.66 s on an idle function 2026-10-14)

### 16. README, research note & GIF · in-progress
Lane orchestrator. The portfolio face of the project: the portfolio ready checklist, one research note run on the synthetic market, an ADR digest, the agent log, a GIF of the demo script, and the not investment advice and data licence statements.
**Done when:** every item in doc 01's portfolio ready definition is ticked and the README links the live demo and the GIF.
- [x] Build it: `/develop readme & demo`, everything but the GIF (2026-10-16)
  - [x] `README.md`: the idea, the demo script, a Mermaid architecture diagram, the honest tech list, the $0/month breakdown with the measured 2.66 s cold start, "Limits of the research" copied from doc 01 §8.1, the data licence statement, the not investment advice notice, the CI badge and the live demo link
  - [x] [Research note 0001](../research-notes/0001-fixed-vs-trailing-stop-synthetic.md): a real run on the seed 42 market following doc 01 §4.3. The hypothesis (a 10% trailing stop beats a fixed 8% stop per bar) is **rejected**, and the note's own headline is that the chosen config's OOS expectancy quadrupled while its edge over random fell 78%
  - [x] [ADR digest](../adr-digest.md): all 17 decisions tracked to what actually happened. 15 held, ADR-005's "p95 > 10 s" trigger fired and the deviation was accepted on purpose, ADR-016's checkpoint resolved against its own fallback
  - [x] [Agent log](../agent-log.md): the four lanes, the five mechanisms that kept the agents honest, and what they got wrong (every failure was a number asserted without measuring it)
  - [x] Doc 01 §4.1 portfolio ready checklist ticked, including correcting the stale 10 s exit lab figure it still carried
- [ ] **Record the GIF** (you, at a screen recorder): the six steps of the demo script against `make dev` on the seed 42 market, 375 px wide, into `docs/assets/demo.gif`, under about 10 MB, with the synthetic banner legible in frame 1. The README has a pending notice in its place and a one line swap in a comment
- [ ] Tag `v1.0` once the GIF lands

## Slice 6: Live data

Slices 6 to 8 are the post `v1.0` pass. The one week build baked the market into the container image (`services/api/Dockerfile` generates the seeded market at build time into `/data`), so the only way the numbers change is a rebuild and a redeploy. This slice moves the data into a store that can change while the site is running. Lanes below are kept for habit; post `v1.0` you are every lane.

### 17. Market data store · in-progress
Lane BE. Move the bars out of the container image and into a database the API reads, so the data can change without a rebuild. Everything else in these three slices stands on this one. About 2 days.
**Done when:** the API serves scans and backtests from the store in both synthetic and live mode, the image no longer ships a generated market, schema changes run as versioned migrations you can review, the engine's store access stays inside its infrastructure layer (`engine/data`) so the boundary test still passes, and the whole thing still costs nothing at rest.
- [x] Design it (spec): `/architect market data store` (signed off by the owner 2026-10-18)
- [ ] Build it: `/develop market data store`
  - [ ] The store reader: `MARKET_STORE_URI` replaces `SYNTHETIC_DATA_DIR`, `meta.parquet` carries `layout_version` and is written last, and a rerunnable push script seeds the store (AC-2, AC-5, AC-9, AC-10)
  - [ ] Deployed on the store, bake removed: the bucket by hand, the deployed URI pointed at it, cold start measured, then the Dockerfile generation step out and the image smoke test given a dataset (AC-1, AC-6, AC-11, AC-15)
  - [ ] Change check and inline reload: one middleware comparing `meta.parquet` contents on a 10 s floor, the noticing request reloading before it is served, and recovery when the store was absent at start (AC-7, AC-8, AC-13, AC-14)
  - [ ] Local stack, CI cover and the live prefix: MinIO in compose and reused as the CI service, the execution role scoped to synthetic only, and the live dataset pushed (AC-3, AC-4, AC-12)
- [ ] Verify it: `/check verify market data store`
- [ ] Test it: `/test market data store`
Spec [0011](../specs/0011-market-data-store/index.md)

### 18. One command local stack · planned
Lane DI. Bring the store, the API, the web app and the writer up together, so you or a reviewer runs the whole project with one command. Nothing is left to decide once feature 17's spec names the services. About half a day.
**Done when:** one command brings the full stack up from a clean clone with no manual setup, `make dev` still works for day to day coding, and the README says which to use when.
- [ ] Build it: `/develop one command local stack`

### 19. Market clock writer · in-progress
Lane BE. A small job on a timer that appends one more simulated trading day to the store, so there is always something new to refresh into. About 1 day.
**Done when:** a tick appends exactly one trading day without rewriting history, the series stays deterministic and continuous from the seed, a tick that fails halfway or runs twice leaves the data correct, and the synthetic banner stays truthful about what the data is.
- [x] Design it (spec): `/architect market clock writer` (signed off by the owner 2026-10-18)
- [ ] Build it: `/develop market clock writer`
  - [ ] The published window: `n_sessions` to 1818, `delisting_fraction` to 0.08, `synthetic-2`, and the truncation that nulls the delist pair together and hides everything past the cursor (AC-5, AC-6, AC-10)
  - [ ] Re-baseline and re-seed: D-3 verified at both ends of the runway, the four `generate(42)` test files and X-7's timing re measured, the store seeded at the initial cursor (AC-7, AC-13)
  - [ ] The tick: derive the session and seed from meta, regenerate, verify the published prefix, write bars then securities then meta, handle already current and runway exhausted (AC-1, AC-2, AC-3, AC-4, AC-8)
  - [ ] The schedule: the writer Lambda from the API image with its own write scoped role, an EventBridge daily schedule, and one real tick watched end to end (AC-9, AC-11, AC-12)
- [ ] Verify it: `/check verify market clock writer`
- [ ] Test it: `/test market clock writer`
Spec [0012](../specs/0012-market-clock-writer/index.md)

### 20. Live refresh and push · in-progress
Lane FE and BE. The site notices new data by itself: an as of marker that moves, and the server pushing the change rather than the browser asking again and again. Holding a stream open rules out some hosting shapes, so this decision reaches past the UI. About 1 day, now closer to 2: spec 0013 found the honest version needs a contract change.
**Done when:** an open page updates within seconds of the writer appending a day, with no reload; the as of date and the data mode banner stay honest; the page recovers on its own when the stream drops; and the hosted demo either works or falls back to asking on a timer.
- [x] Design it (spec): `/architect live refresh and push` (signed off by the owner 2026-10-18; the decision is polling, not push, because Lambda bills a held open stream for every second it is open)
- [ ] Build it: `/develop live refresh and push`
  - [ ] The contract change: `Assumptions` gains `data_end` and `data_version` so a result names its own data, then the regenerated client, mocks and owner approval (AC-3, AC-12)
  - [ ] The as of marker beside each view's results, read straight off the result rather than from the poll, with no shared context (AC-2)
  - [ ] The poll: one query on a 30 s focused interval, failures swallowed, a null dataset rendering nothing (AC-1, AC-6, AC-7, AC-8, AC-11)
  - [ ] The notice: a new component rather than `Banner`, with its `/ui` gallery entry, telling the person to reload rather than re-running anything for them (AC-4, AC-5, AC-13)
  - [ ] Trial counts labelled with the dataset ends in a sibling key so no count is wiped, and the banner's existing behaviour confirmed unchanged (AC-9, AC-10)
- [ ] Verify it: `/check verify live refresh and push`
- [ ] Test it: `/test live refresh and push`
Spec [0013](../specs/0013-live-refresh-push/index.md)

## Slice 7: Your own saved work

### 21. Saved rules · in-progress
Lane BE and FE. Save a rule you built under a name, list them, load one back into the builder, delete one. The first time anything writes to the store instead of only reading it. About 1 to 1.5 days.
**Done when:** a saved rule survives a restart, loads back into the builder exactly as saved, keeps working after the rule format grows a field, and a malformed or oversized rule comes back as a 422 the form can show.
- [x] Design it (spec): `/architect saved rules` (signed off by the owner 2026-10-18; this is where SQL arrives, on Neon, with writes gated to your own machine until feature 22)
- [x] Build it: `/develop saved rules` (`engine/data/rules.py`, `engine.api`, `services/api/src/api/routes/rules.py`, `apps/web/src/features/scan/saved-rules.tsx`)
  - [x] The database: Neon, Alembic with plain SQL migrations, one table holding the rule as `jsonb`, and the enablement gate (a database URL plus the D-5 host checks) (AC-5, AC-6, AC-7)
  - [x] The repository in `engine/data` plus the `engine.api` use cases the routers call: four plain SQL statements, no ORM, a connection per request (AC-1, AC-2, AC-9)
  - [x] One `contract-change` PR for all three endpoints at once, since CI fails on any client diff: the `Rule` body, the 409, `DELETE` added to CORS, the regenerated client, mocks and owner approval (AC-3, AC-4, AC-8, AC-11)
  - [x] The thread proved against the real database, and the skip that keeps `make ci` green without one (AC-2, AC-10)
  - [x] The builder's save control and saved list, loaded from the list payload, hidden when the API answers 501 (AC-6)
  - [x] Round trip tests across every operand shape (AC-2)
- [ ] Verify it: `/check verify saved rules`
- [ ] Test it: `/test saved rules`
Spec [0014](../specs/0014-saved-rules/index.md)

### 22. Accounts · planned · needs a decision · GA
Lane BE and FE. Real sign in, with saved rules and saved runs belonging to whoever made them. Local demo only, so there is no public login to attack and no real person's data to lose. About 2 days, and the item an interviewer is most likely to dig into.
**Done when:** you can register, sign in, sign out and stay signed in across a restart; passwords are never stored or logged in readable form; one account cannot read or delete another's rows; and the hosted demo runs with accounts switched off.
- [ ] Design it (spec): `/architect accounts`

### 23. Backtest runs as jobs · planned · needs a decision
Lane BE and FE. Submit a backtest, get a run id back immediately, watch it progress, then find it again in a history table beside the exact rule and settings that produced it. About 2 days. This is what turns the app from request and response into a system with work in flight.
**Done when:** a submitted run returns before it finishes, its status and result are readable by id, a failed run says why, the history table shows past runs with their inputs, and the same rule and seed replay to the same numbers.
- [ ] Design it (spec): `/architect backtest runs as jobs`

## Slice 8: Operations

### 24. Infrastructure as code · planned · needs a decision
Lane DI. Describe the AWS pieces as code instead of console clicks, including whatever the data store turns out to need. Promoted out of the deferred list. About 1.5 days.
**Done when:** an apply from scratch builds the whole stack, state lives somewhere safe to share, no secret sits in the files, a plan against an unchanged stack reports no drift, and a destroy leaves nothing billable behind.
- [ ] Design it (spec): `/architect infrastructure as code`

## Deferred

Out of scope for the one week build, kept so the plan stays honest. Picked up in this order once the MUST list ships.
1. **Candle chart with hit markers** (S-5)
2. **MAE and MFE scatter** (X-5S)
3. **Index join date filter**: only trade names after they joined the S&P 500 · needs a decision
4. **Exit lab portfolio mode** (X-6) · needs a decision
5. **Signal study**: forward returns versus the base rate · needs a decision
6. **R based targets** (B-4R, B-12)
7. **Error monitoring**
8. **Parameter sweep** · needs a decision
9. **Walk forward testing** · needs a decision
10. **Free history that includes delisted names** · needs a decision
11. ~~**Infrastructure as code** for the AWS pieces~~ promoted to feature 24
16. **Prefix stable generator** · from spec 0012. `generate(seed)` cannot extend a market: the regime schedule, the bear planting, the per ticker draws and the OHLCV blocks all depend on `n_sessions`, so one more session reshuffles everything. Feature 19 works around it with a published window over a longer master, which is why its runway ends after 558 ticks. Fixing it properly is a rewrite of the model's randomness (independent per session streams, an absolute schedule) plus a dataset re-baseline, and it removes the runway limit. Blocks nothing today; decide before the runway runs out, around the start of 2029.
12. **OR groups in the rule builder** · needs a decision
13. **Read cache in front of the store**, only once a measurement shows the store is the slow part · needs a decision
14. **Browser tests in CI** driving the real pages on every pull request
15. **Self hosted deploy** of the whole stack on one small machine

If the week runs behind, cut in this order: close below MA exit, then ATR stop, then the trial counter becomes a static warning, then live research mode moves to Day 8. The rule builder, the backtest, the exit lab with IS and OOS, the oracle tests, the deploy, and the README are never cut.

## Legend

**The decision box.** Every feature carries exactly one, the sub task whose label ends with `(spec)`. Its wording varies (`Design it (spec)` normally, `Decide the stack (spec)` on Stack & architecture), so skills locate it by that `(spec)` suffix, never by an exact label. Every other box is an execution box and `/architect` never ticks one.

**Feature lifecycle**: the scope updates as a feature moves; each row is what it shows and who sets it:

| State | Set by | The feature shows |
|---|---|---|
| `planned` · needs a decision | `/scope` | one box: `Design it (spec): /architect <feature>` |
| `in-progress` (designed) | **`/architect` at spec capture** | `Design it` ticked; spec linked; `Build it: /develop <feature>` + **2 to 5 milestones**; the tier's closing boxes (`Verify it` Alpha+, `Test it` Beta+, `Review it` + `Document it` GA); any surfaced follow up enrolled |
| `in-progress` (building) | `/develop` | milestone sub boxes tick one by one; code pointer filled |
| `in-progress` (verified) | `/check verify` | `Build it` + milestones ticked; `Verify it` ticked |
| `done` | **you, when you decide it is** (any skill sets it when you say so); `/sync` reconciles | boxes you ran ticked, skipped ones marked skipped; the tier's last stage (`Prototype` after `/develop`; `Alpha` after `/check verify`; `Beta` and `GA` after `/test`) is the suggested point to call it done; `/sync` captures conventions |

- **Next step** is the first unticked box (always a command or a tracked milestone).
- **needs a decision** means run `/architect` first; otherwise go straight to `/develop` (or `/audit` for standards and tooling). The tag drops once the spec is captured.
- **Atomic build tasks live in the spec's `## Build plan`, not here**: the scope carries only the milestone rollup.
- **Status** goes `planned`, then `in-progress`, then `done`, plus `existing` (pre workflow) and `dropped` (de scoped, kept for history).
- **Approach tag** beside a heading overrides the project default for that feature; no tag means it inherits.
- **Workflow tier tag** beside a heading (here `· GA` on the engine features) sets that one feature's rigor above or below the project default; no tag inherits the default.
- **Workflow** (header line) is the project default, what runs after `/develop`: **Prototype** runs nothing; **Alpha** runs `/check verify`; **Beta** runs `/check verify` then `/test`; **GA** adds a fresh model `/check review` then `/document`. A feature built on an unratified decision (an `Assumed` spec) stays flagged, but that never blocks `done`.
- **Pointer line** (`spec <n> · code in <path>`): the spec link added by `/architect`, the code path by `/develop`.
