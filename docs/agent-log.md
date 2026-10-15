# Agent log

How this project was actually built: one person directing AI coding agents across four parallel
lanes, with the interesting part being the guard rails rather than the generation.

**2026-10-06 to 2026-10-16 · 272 commits · 96 merged pull requests · 10 specs · 17 ADRs**

## The setup

Work ran in four lanes, each owning its own folders and enforced by `CODEOWNERS`, so lanes could
run at the same time without editing each other's files:

| Lane | Owns | Queue it worked |
|---|---|---|
| **DI** (data and infrastructure) | `infra/`, `.github/`, `engine/synthetic`, `engine/live`, `scripts/` | stack → synthetic market → live mode → deploy hardening |
| **BE** (the critical path) | `engine/` domain modules, `services/api/` | template scan → portfolio backtest → exit types → exit lab |
| **FE** | `apps/web/src/features/` | template scan → rule builder → honesty guards → report → exit lab |
| **QA** | `tests/acceptance/`, `tests/golden/`, `docs/qa/` | oracle drafts, then each feature's criteria as it landed |
| **Owner** | `tests/oracle/`, every merge, the live data | approve oracles, run the deploy, run `make load-live` |

Each lane ran one feature at a time, in its own worktree and branch, at most two open pull
requests, about 400 changed lines per pull request.

## What kept the agents honest

Generation was never the hard part. Five mechanisms did the real work, and each one caught
something:

**1. Owner written oracles, before the engine.** 26 correctness tests in `tests/oracle/`,
protected by a pre commit guard and an `oracle-approved` CI label so no agent can edit them. They
define what "correct" means for every MUST exit type, loop parity, look ahead and MAE/MFE. An
agent that cannot change the test has to change the code.

**2. One place for exit precedence.** ADR-008 put all exit ordering inside a single `step()`
function and made "never special case an exit outside it" an engine invariant. This is the rule
that paid off most: when the per bar path was later optimised for speed, and again when a
vectorised rewrite was costed, the invariant is what made the first safe and the second
unattractive.

**3. A criteria gate that cannot drift.** 52 MUST acceptance criteria in `status.yaml`, mirrored
in `docs/qa/traceability.md`, with `test_traceability.py` failing the build if the two disagree or
if a test claims an ID it does not carry. QA wrote these from the spec and the contracts only,
never from the implementation.

**4. A boundary test instead of a convention.** `engine/tests/test_engine_boundary.py` fails if
the domain imports FastAPI, Starlette or uvicorn. Clean Architecture enforced by a test is
Clean Architecture; written in a style guide it is a suggestion.

**5. Disagreements logged, not resolved in private.** When QA and a builder read a criterion
differently it went to `docs/qa/ac-questions.md` and the criterion stayed `pending` until the owner
ruled. Three of those questions shaped real decisions, including both of the last two to close.

## What the agents got wrong

The failures are more informative than the successes, and all of them share a shape: **an agent
asserting a number it had not measured.**

- **Doc 02's assumption A4** claimed a warm Lambda runs the 6 config exit lab in under 10 s,
  "measured on Day 4". It was never measured on Day 4. When it finally was, nine days later, the
  answer was **24.85 s**. The criterion built on it (X-7) sat unverified the whole time.
- **Four separate extrapolations** of that same number were produced from in process timings (43 s,
  12.4 s, 11.9 s, 16.4 s). Only the last was close to the measured 16.5 to 18.9 s, and the one
  recommended most confidently at the time was 11.9 s, which was badly wrong. Spec 0009 now
  carries the instruction "Measure this number, never derive it."
- **Doc 02's assumption A3** had the live loader on Alpaca's `feed=sip` from 2016, about 1.35M
  bars. The free plan has no `sip`. The real dataset starts **2017-11-15** and holds 43% fewer
  bars. Nobody noticed until the loader was actually run, on the last day.
- **A speed fix that was slower.** The first attempt at splitting exits by kind used four tuple
  generator expressions and cost 0.36 s per lab run on its own. The profiler caught it; review
  would not have.

The pattern held on the other side too. The one time the process worked exactly as designed was
also a measurement: spec 0009 said "profile first, vectorise second", and profiling found that
only ~8% of a warm run was exit logic and ~92% was object and interpreter overhead. That turned a
2 h rewrite into a 40 minute change with no logic touched, for 1.43x.

## What the humans did

Five things were never delegated, and all five turned out to be the leverage points:

1. **Writing and approving the oracles.** The one gate that could stall the critical path, so it
   went first.
2. **Ruling on criterion disputes.** An agent asked to interpret an ambiguous criterion will
   pick an interpretation and sound certain about it.
3. **Running the first deploy and the live data load.** Both needed real credentials, and both
   immediately exposed assumptions the docs had carried for days.
4. **Merging.** Every one of the 96 pull requests.
5. **Deciding when a number was good enough.** The exit lab was 2.5x over its stated budget. The
   call to retire the unmeasured budget and set a measured one, rather than spend 4 to 5 h on a
   rewrite to hit a number nobody had justified, was a judgement about what the project is for.

## What it produced

| | |
|---|---|
| Engine (domain logic) | ~4,800 lines |
| Web app | ~13,800 lines |
| API (presentation) | ~320 lines |
| Tests | 710 Python tests (26 owner oracles, 141 acceptance), ~450 web tests |
| Specs | 10, in `docs/specs/` |
| Decision records | 17, tracked to outcomes in the [ADR digest](adr-digest.md) |
| Reviews | 5, in `docs/reviews/`, each by a fresh model on a different model than wrote the code |
| Research notes | 1 published, in [`docs/research-notes/`](research-notes/) |

The API is ~320 lines because the architecture pushed the work inward: routers assemble responses
and the engine decides everything. That ratio is the clearest single measure of whether the
boundary held.
