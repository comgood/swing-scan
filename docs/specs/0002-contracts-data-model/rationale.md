# 0002. Rationale: contracts and data model

## Context

Four agents (DI, BE, FE, QA) start work in parallel on Day 1, and the only thing that lets them do that safely is a frozen set of shared shapes. Doc 02 §15.3 makes this Phase 0: nobody fans out until the contracts are merged and tagged `contracts-v1`. Doc 02 §5 sketched the rule, exit, file and endpoint shapes, but left the details a builder would otherwise guess: how operand types are told apart, what units percentages use, how per indicator limits reach the UI, what "baseline config" means, what an empty run returns, and how errors carry the allowed range that R-6 and U-7 need.

The forces are specific. The FE lane builds the whole workspace against mocks before any engine code exists, so the mocks must be realistic and must stay valid as the contract evolves. QA writes tests from criteria and contracts only, never from implementation, so the contract must fix the use case signatures and the error shape. The owner approves every oracle by hand, so the fixture format must make the bar by bar math easy to read. Breaking changes are allowed only until the Day 4 checkpoint, which makes drift the main risk (doc 02 §15.9 rates contract drift medium likelihood, high impact).

The stack is already fixed by spec 0001: Pydantic v2 and FastAPI in Python, openapi-typescript and openapi-fetch in the web app, a committed `contracts/openapi.json` with a CI diff check, and FastAPI's default 422 body. The engine must not import web frameworks. If this isn't decided now, every lane invents its own answer to each open question above, and the first integration day (Day 5) becomes the day those answers collide.

This is a repo wide decision. It touches `engine`, `services/api`, `packages/api-client`, `apps/web`, `contracts/` and the test suites.

## Options considered

### Option 1: Pydantic first, everything generated (chosen)

Write every shape as a Pydantic model in `engine/contracts/`. FastAPI turns the models into `openapi.json`, openapi-typescript turns that into TS types, and a seeded Python script builds the mocks as instances of the same models. The web app serves the mocks with MSW. CI regenerates all three and fails on any diff.

**Pros**:
- One source. A field can't exist in TypeScript, a mock or a route without existing in the model first.
- Validation, the JSON Schema and the 422 errors all come from the same constraints.
- The mocks are type checked by construction and can't fall out of date unnoticed.
- It reuses exactly the tools spec 0001 already chose, plus MSW.

**Cons**:
- The contract's shape is tied to what Pydantic and FastAPI emit as OpenAPI (for example, discriminated unions become `oneOf` with a discriminator).
- Three generated artefacts in every contract PR.
- MSW is a new dependency for the web lane.

### Option 2: OpenAPI first, hand written spec

Write `contracts/openapi.yaml` by hand as the source, generate the Pydantic models from it (datamodel-code-generator) and the TS types with openapi-typescript, and serve its `examples` with a mock server such as Prism.

**Pros**:
- Language neutral source, readable by anyone who knows OpenAPI.
- Mock server comes for free from the examples.

**Cons**:
- Generated Pydantic models can't hold the custom validators this contract needs (per indicator `n`, duplicate exit types, `start < end`), so validation splits between the YAML and hand written Python.
- Hand writing a 30 model OpenAPI document is slow and error prone on a Day 1 budget of about 2.5 hours.
- Prism adds a process to `make dev` and to Vitest.

### Option 3: Minimal, models plus hand written mocks

Pydantic models as the source and generated TS types as in Option 1, but mocks written by hand as JSON and validated in CI, with the web app swapping `fetch` to read them.

**Pros**:
- No mock script and no MSW. The fewest moving parts.
- Mocks are easy to read and edit.

**Cons**:
- Realistic sizes (500 equity points, about 150 trades, 5 config rows with matching counts) are impractical by hand, so the mocks end up tiny and the FE never sees the truncated or full states.
- A hand rolled fetch swap reinvents routing, delays and error injection, which U-5 and U-7 tests need.

## Rationale

Option 1 wins on the force that matters most here: drift between four parallel lanes. With one model per shape and CI regenerating every derived file, drift becomes a failing build instead of a Day 5 surprise. It also puts the validation rules R-6 needs (per indicator ranges, duplicates, both bounds in the error) in the same place that produces the schema, which Option 2 can't do without splitting validation across two files.

Option 3 is the simplest, and would be right for a single developer. But the FE lane's job on Days 1 to 4 is to build every report state against mocks, and hand written mocks won't cover the 2,000 trade cap, the no stop config, or a five row exit lab with consistent counts. The script costs roughly an hour and pays that back the first time a field changes. MSW is the boring choice for request mocking in a React and Vitest stack. It lets the real openapi-fetch client and TanStack Query run unchanged, so switching to the real API is one environment variable.

Server side trial keys, `best_is` and warnings follow the same logic. The rules behind them (which numbers to strip, which direction is better, the 10% horizon threshold) are research honesty rules, and they belong where pytest and the owner's oracles can see them, not duplicated in UI code.

### Decision log

Each line is one question from the design conversation: the engineer's pick, why, and the runner up.

| Dimension | Pick | Why | Runner up |
|---|---|---|---|
| Routes before the engine | Validate fully, then 501 | Real 422s now, which makes this the tracer bullet | Serve mock JSON from the real API |
| Baseline config | `configs[0]` | No extra field or UI state | `baseline: true` flag |
| Operand discriminator | `kind` tag | Clean narrowing in Pydantic and TS, and precise 422 paths | Untagged (shorter URLs) |
| Percent units | Percent numbers, `_pct` names | Matches the UI, the docs and the 422 text | Fractions everywhere |
| Indicator `n` rules | One model + registry + `/indicators` | One source of truth, small TS | One variant per indicator |
| Exit config shape | List tagged by `type` | Matches doc 02 and the editor rows | Object keyed by type |
| Trial keys | Server returns them | One tested implementation | Browser Web Crypto |
| `best_is` and warnings | Server computes them | Rules in one Python place | FE derives them |
| Bars dtypes | String ticker, Float64 volume | Adjusted volume can be fractional, and plain joins work | Categorical + Int64 |
| Fixture time axis | 1 based `bar` column | Hand math reads straight off the file | Real dates |
| Oracle expected values | Literals in the test | One file to approve, and the formula documents itself | Sidecar JSON |
| Fixture listing/delisting | Inferred, optional sidecar | Zero extra files for most oracles | Always explicit |
| Mock authoring | Seeded script | Realistic and always valid | Hand written JSON |
| Mock wiring | MSW | The real client runs unchanged | Fetch swap |
| Over the cap | Stride and flag (trades spread evenly, changed after the cross check so OOS trades aren't hidden) | The default 5 year demo always fits | Weekly resample |
| `new_today` and the cooldown | Cooldown included (doc 02 §6), a ruling over doc 01 S-3's wording | "New today" means "would actually be entered" | Raw signals |
| References | None | Decisions rest on the project's own docs | Sources only |
| Scan `as_of` | Optional input | S-1 and S-3 testable over HTTP | Latest only |
| Empty runs | 200, empty + `no_entries` warning | "Never fires" is a valid research answer | 422 |
| Names | 1 to 40, unique configs | Unambiguous rows, bounded URLs | Server filled defaults |
| Use case data | `scan(req, market)` | No hidden I/O, and fixtures can be injected | Module global |
| Assumptions header | Typed fields | U-3 asserted by name | Label and value pairs |
| Exit reason | Per exit type | Oracles can assert the exact exit | Grouped by kind |
| Versioning | Own semver + git tag | Engine releases don't churn `openapi.json` | Reuse engine version |
| Benchmark storage | An ordinary ticker in bars, named by `meta.benchmark` | One file and one loader | A separate file |

**Calls made at write time** (not asked, settled here with the runner up):

- **Where the models live:** `engine/contracts/`, as doc 02 §15.3 and `engine/AGENTS.md` already say. Runner up: a separate `contracts` Python package, which would add a third uv member for no gain.
- **Two bound errors:** a `bounded()` helper puts both limits in the JSON Schema and raises one `out_of_range` error carrying `min` and `max`. Pydantic's built in `ge`/`le` errors only report the side that failed, which falls short of R-6's "the allowed range". Runner up: rewriting errors in a global exception handler, which is harder to test per field.
- **`stop_atr.n` range:** 2 to 50, default 14. Doc 02 fixes only the default. Runner up: 2 to 252 like the `atr` indicator, which is wider than any sensible stop.
- **Canonical wire form:** every field written, defaults included. That makes R-1 round trips exact at the cost of slightly longer URLs. Runner up: leaving out defaults, which makes equality depend on the serialiser.
- **Undefined numbers:** `null`, with non finite floats rejected at serialisation. JSON has no NaN. Runner up: sentinels like `-1`, which are easy to misread as real values.
- **Sign convention:** `mae_pct` ≤ 0 and `mfe_pct` ≥ 0, so "closer to 0 is better" holds for MAE in `best_is`. Runner up: both positive magnitudes, which hides direction in the trade list.
- **`/meta` before data exists:** `data: null` rather than a 501, so the FE can build the banner and version display now.
- **No separate JSON Schema files:** `openapi.json` already holds every schema. Doc 02 §15.2 mentioned "JSON schemas", but a second copy would only be one more thing to drift.
- **Fixture benchmark:** the loader adds a flat `FIXTURE-INDEX` so `validate_market` holds everywhere without oracle authors thinking about it.

### Premise check

Doc 02 frames this as five deliverables (rule schema, bars schema, exit schema, OpenAPI with mocks, fixture format). They are tightly coupled, frozen together under one tag and one sign off, so one spec rather than an umbrella is the right size. If the fixture format grows (for example, multi ticker portfolio fixtures for B-11), it can split into its own child spec without touching the rest.
