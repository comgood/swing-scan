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
| 3 | Contracts & data model | Foundation | in-progress |
| 4 | Design system & UI foundation | Foundation | in-progress |
| 5 | Acceptance test harness & traceability | Foundation | planned |
| 6 | Backtest correctness oracles | Foundation | planned |
| 7 | Synthetic market | Slice 1 | planned |
| 8 | Template scan | Slice 1 | planned |
| 9 | Portfolio backtest core | Slice 1 | planned |
| 10 | Rule builder | Slice 2 | planned |
| 11 | Exit types | Slice 3 | planned |
| 12 | Exit lab | Slice 3 | planned |
| 13 | Research honesty guards | Slice 3 | planned |
| 14 | Live research mode (local) | Slice 4 | planned |
| 15 | Deploy hardening & demo readiness | Slice 5 | planned |
| 16 | README, research note & GIF | Slice 5 | planned |

## Foundations

Done in order on Day 1 before the lanes fan out. Feature 3 ends with the `contracts-v1` tag and your sign offs (SO-1 to SO-3); feature 6 must be approved before engine work in feature 9 starts.

### 1. Stack & architecture · in-progress
Lane DI. Record the stack already chosen in doc 02 (Next.js on Vercel Hobby, FastAPI with Polars and NumPy in a Lambda container, GitHub Actions with OIDC) and scaffold a runnable monorepo with a hello world deploy of both apps.
**Done when:** the stack is captured in a spec, the empty web app and API both run locally, and both are reachable on their free tier hosts.
- [x] Decide the stack (spec): `/architect stack & architecture`
- [x] Scaffold from the decision: `/develop stack & architecture` (local scaffold done; your first deploy per `infra/README.md` still pending)
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

### 3. Contracts & data model · in-progress
Lane orchestrator with your sign off. Freeze the shared shapes every lane builds against: rule JSON schema with Pydantic and generated TypeScript types, the bars schema, the exit config schema, the OpenAPI contract with mock responses, and the test fixture format.
**Done when:** contracts are tagged `contracts-v1`, mocks validate against the schema in CI, the generated client compiles, and you have signed off SO-1 to SO-3.
- [x] Design it (spec): `/architect contracts & data model`
- [ ] Build it: `/develop contracts & data model`
  - [x] Thin thread: rule models, `/scan` (422 then 501), OpenAPI and generated client, one mock through MSW in Vitest (AC-1, AC-2, AC-5, AC-6, AC-13, AC-15)
  - [x] Full shapes: exits, sim, backtest responses, static GET routes, trial keys (AC-3, AC-4, AC-6 to AC-9, AC-14)
  - [x] Data and fixtures: market schema, `validate_market`, fixture loader and builder (AC-10, AC-11)
  - [ ] Mocks and freeze: `make mocks`, every MSW handler, CI drift checks, SO-2 and SO-3, tag `contracts-v1` (AC-1, AC-12, AC-13, AC-16) (built; your SO-2 and SO-3 sign offs and the `contracts-v1` tag at merge are still open)
- [ ] Verify it: `/check verify contracts & data model`
- [x] Test it: `/test contracts & data model`
Spec [0002](../specs/0002-contracts-data-model/index.md) · code in `engine/src/engine/contracts/`, `engine/src/engine/data/fixtures.py`, `services/api/src/api/routes/`, `contracts/`, `packages/api-client/`, `apps/web/src/mocks/`

### 4. Design system & UI foundation · in-progress
Lane FE. A small, calm visual language and base components: page layout, data table, form controls, number inputs, banners, and loading and error states.
**Done when:** base components exist, are keyboard usable with visible focus and readable contrast, inputs are labelled, and layouts hold at 375 px (U-6).
- [x] Design it (spec): `/architect design system & UI foundation`
- [x] Build it: `/develop design system & UI foundation`
  - [x] Thin thread: tokens, shadcn `base-nova`, app shell with the data mode banner, `/ui` gallery, first Vitest and axe test (AC-1 to AC-4, AC-15, AC-16)
  - [x] Forms: fields, number input, 422 to field mapping (AC-5 to AC-7)
  - [x] Data display: data table, formatters, badges and cards (AC-8, AC-11, AC-12)
  - [x] Feedback and hardening: banners, warm up notice, error states, keyboard, 375 px, axe on every section (AC-9 to AC-11, AC-13, AC-14, AC-16)
- [x] Verify it: `/check verify design system & UI foundation`
- [ ] Test it: `/test design system & UI foundation`
Spec [0003](../specs/0003-design-system-ui-foundation/index.md) · design in `apps/web/design.md` · code in `apps/web/src/components/`, `apps/web/src/lib/`, `apps/web/src/app/ui/`

### 5. Acceptance test harness & traceability · planned
Lane QA. The independent test suite, written from doc 01 criteria and the contracts only, never from builder code: `tests/acceptance/`, `tests/golden/`, a pending or required status gate in CI, and an AC to test matrix in `docs/qa/`.
**Done when:** every MUST criterion in doc 01 has a row in the matrix and a test marked pending or required, and CI fails only on required tests.
- [ ] Build it: `/develop acceptance test harness`

### 6. Backtest correctness oracles · planned · GA
Lane QA drafts, you approve. Hand computed fixtures for each fill and exit rule plus the poisoned future look ahead test, kept in the protected `tests/oracle/` folder.
**Done when:** B-1, B-2, B-7 to B-10 and B-14 to B-16 exist with hand calculations you have recomputed and approved; agents cannot edit the folder.
- [ ] Write and approve the oracles: `/test backtest oracles`

## Slice 1: Thin real thread (walking skeleton)

Generated data, one template scan, one simple backtest, shown on the deployed page. Every layer real, just narrow.

### 7. Synthetic market · planned
Lane DI. A seeded generated market of 500 invented tickers over 5 years with regimes, planted delistings, and a demo index, built into the API image.
**Done when:** the same seed gives identical data, every bar passes sanity checks, and at least one bear segment and 20 delisted tickers exist (D-1 to D-3).
- [ ] Build it: `/develop synthetic market`

### 8. Template scan · planned · needs a decision
Lanes BE and FE. Indicators, rule evaluation with the valid rising edge and the signal based cooldown, the two templates, the `/scan` endpoint, and a sortable results table on the landing page.
**Done when:** a first visit opens the Breakout template with today's hits and the synthetic banner, delisted tickers never appear, scan and backtest signals match, and a warm scan answers in under a second (S-1 to S-4, R-10, U-1, U-5).
- [ ] Design it (spec): `/architect template scan`

### 9. Portfolio backtest core · planned · needs a decision · GA
Lanes BE and FE. The portfolio simulator with next open fills, % stop and time exit, equal weight, max positions, slippage, delisting exits, IS and OOS split, an equity curve against the benchmark, a trade list with MAE and MFE, and the report page with its assumptions header.
**Done when:** all approved oracles pass, results are deterministic, the top ranked signals fill free slots, and the report shows IS and OOS side by side with the assumptions header (B-1, B-2, B-7 to B-11, B-13 to B-16, U-3).
- [ ] Design it (spec): `/architect portfolio backtest core`

## Slice 2: Rule builder

### 10. Rule builder · planned · needs a decision
Lanes BE and FE. Build your own entry rules: a flat AND list of up to 8 conditions over 12 indicators, with numbers or indicators on the right side, crosses, offsets, and clear validation. The templates load into it as editable starting points.
**Done when:** rules round trip as JSON, crosses and offsets behave as specified, warm up bars evaluate as not computable, invalid rules return a clear 422 shown on the right row, and the structure key ignores numbers (R-1 to R-9, U-7).
- [ ] Design it (spec): `/architect rule builder`

## Slice 3: Exit research

### 11. Exit types · planned · GA
Lane BE. Add the remaining exits behind the same exit interface: ATR stop, % target, trailing stop, and close below a moving average filled at the next open, with stops checked before targets.
**Done when:** each exit passes its oracle and the per bar precedence holds (B-3 to B-6). Rests on the spec from feature 9.
- [ ] Build it: `/develop exit types`

### 12. Exit lab · planned · needs a decision · GA
Lanes BE and FE. Hold one entry rule fixed and compare 2 to 6 exit setups on identical entries, trade by trade, with a random entry baseline run through the same exits.
**Done when:** entries are identical across configs, metrics are per trade only with IS and OOS columns, the best IS config is highlighted, MAE and MFE guides use IS trades only, expectancy per bar, distinct entry weeks and horizon exits show, edge versus random is reported, and six configs finish within the time budget (X-1 to X-5, X-7 to X-10).
- [ ] Design it (spec): `/architect exit lab`

### 13. Research honesty guards · planned
Lanes FE and BE. The things that stop you fooling yourself: the structure keyed trial counter with a session total and a warning at 10, the procedure note under the exit lab table, and the data banners.
**Done when:** tweaking only numbers still counts toward the same rule's trials, the warning shows at 10, the procedure note renders, and the synthetic and survivors only banners appear in the right modes (U-2, U-4, U-8).
- [ ] Build it: `/develop research honesty guards`

## Slice 4: Live research mode

### 14. Live research mode (local) · planned
Lane DI, run by you. Load Alpaca free daily bars since 2016 for about 500 current S&P 500 names plus SPY into the same schema, on your machine only.
**Done when:** `make load-live` fills local data with keys from the environment, the API refuses live mode anywhere but localhost, and `research/` is ignored by git (D-4, D-5).
- [ ] Build it: `/develop live research mode`

## Slice 5: Ship

### 15. Deploy hardening & demo readiness · planned
Lane DI. Make the public demo dependable at $0: OIDC deploys, a $1 budget alarm, the warm up ping, response size limits, a measured cold start, and the Day 1 checks (Alpaca terms, GitHub's 60 day rule, the Lambda 6 MB limit).
**Done when:** a merge to main deploys both apps without stored keys, the budget alarm exists, cold start is measured and recorded, and every response stays under the size limit.
- [ ] Build it: `/develop deploy hardening`

### 16. README, research note & GIF · planned
Lane orchestrator. The portfolio face of the project: the portfolio ready checklist, one research note run on the synthetic market, an ADR digest, the agent log, a GIF of the demo script, and the not investment advice and data licence statements.
**Done when:** every item in doc 01's portfolio ready definition is ticked and the README links the live demo and the GIF.
- [ ] Build it: `/develop readme & demo`

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
11. **Infrastructure as code** for the AWS pieces
12. **OR groups in the rule builder** · needs a decision

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
