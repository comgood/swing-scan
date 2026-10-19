# 0012. Rationale: market clock writer

Reasoning, options and references for [index.md](index.md).

## Context

> ⚠️ Premise note: the scope describes this feature as "a small job on a timer", about a day's work. The timer is indeed small. What the scope does not know is that **the generator cannot extend a market at all**, and not in one place but five: `_schedule` draws the bear window from fractions of `n_sessions` and walks regime runs sequentially (so the number of draws depends on `n`), `_market_returns` draws `standard_normal(n_sessions)` as one sized call and then plants the bear using a mean over the whole window, and `idio`, `pinned_noise`, `sector_returns` and `_ohlcv`'s three draws are all `(m, n)` blocks whose every cell shifts when `n` changes. So `generate(42)` at 1261 sessions is a different market from 1260, not that market plus a day. Every obvious implementation of this feature is therefore wrong. This spec works around the limitation rather than fixing it, and the limitation is recorded in Follow-up as its own piece of work.

The store from spec `0011` can now change while the site runs, but nothing changes it. Without a writer, features 18 and 20 have nothing to demonstrate.

The forces at play:

- **D-1's promise.** The project's first acceptance criterion is that the same seed produces identical data. Whatever publishes a day must keep that true.
- **The generator's shape.** One vectorised pass over a whole market, drawn from one stream in a fixed order, with invariants (a planted bear of at least 25.9%, at least 20 delistings) that are properties of the whole series.
- **What is already validated.** `tests/oracle/` is fixture based and `tests/golden/reference.py` is formula based, so neither depends on the generator. But `check_market`, D-1, D-2, D-3, four acceptance test files and X-7's measured timing all do, and the generator is the most carefully validated component in the project.
- **Generation is cheap.** 1260 sessions take about 4.7 seconds, 1818 about 7. Cheap enough to regenerate on every tick as a verification step, which is unusual and worth exploiting.
- **$0 and no operator.** The job runs unattended on the free tier with no alarm to pay for.
- **One writer.** A single scheduler and a single function, so this is not a distributed writes problem.

## Options considered

### Option 1: generate a longer market, publish behind a cursor (chosen)

Set `n_sessions` above the published length, publish a prefix, and let a tick move the boundary.

**Pros**:
- The generator is untouched, so D-1, D-2, `check_market` and the model's validated properties all stand without re-argument.
- The tick is a filter over authoritative data: it computes nothing, so it cannot compute anything wrong.
- Regenerating the master to slice it also verifies what is already published, for free.
- The master is never stored, so the unpublished future exists nowhere.
- Small: a config change, a truncation function, and a command.

**Cons**:
- Finite runway. 558 ticks, about two years and two months, then it stops.
- Leaves the generator's real limitation in place.
- `delisting_fraction` has to be raised from 0.05 to 0.08 to compensate for truncation dropping delistings beyond the cursor, which is a model parameter bent to serve a publishing mechanism.
- The published dataset still changes once, because the current 1260 session market is not a prefix of any longer one.

### Option 2: make the generator prefix stable, then append one session per tick

Rewrite the randomness so that session `i` depends only on `(seed, i)`, with the schedule fixed over an absolute horizon.

**Pros**:
- Fixes the actual defect, which is worth having regardless of this feature.
- Unbounded runway within the horizon.
- Nothing hidden and no truncation rules.

**Cons**:
- It is a rewrite of the model's randomness architecture, not a rework of two functions. All five `n` dependencies above have to go, which means restructuring `_schedule`, `_market_returns`, the per ticker draws and `_ohlcv`.
- The absolute schedule needs concrete numbers that keep D-2, D-3, the `SMALL` config at `n=400` and the `n>=300` floor all true at once. The obvious reading, applying today's fractions to a long horizon, puts the bear at sessions 1200 to 2750, so a 1260 session window has essentially no bear and D-3 fails.
- The bear is planted using a demeaned noise window, so it must sit entirely inside the minimum published window or the planting itself changes with `n`.
- Delistings and listings placed across a long horizon leave too few inside the published window; packed into the first 1260 they leave none for the next decade. Keeping the count constant as `n` grows, which an earlier draft of this spec asserted, contradicts having a market where things delist over time.
- Highest risk work on the most validated component, for a feature whose stated size is one day.

### Option 3: a continuation model drawing one day from the last state

Leave `generate` alone and write a second, smaller model producing the next session from the previous one.

**Pros**:
- No re-baseline and unbounded runway with no horizon to manage.

**Cons**:
- Two market models that must agree, with the subtle divergences (a regime boundary, a delisting, the 63 day momentum lookback) being exactly the bugs nobody notices.
- `check_market` and D-3 rely on whole series properties a one day continuation cannot reason about.
- "Deterministic and continuous from the seed", the scope's wording, weakens to "continuous from the last state".

### Option 4: a `make tick` you run by hand, no scheduler

**Pros**:
- Nothing to create in AWS, nothing to pay for.

**Cons**:
- The feature's purpose is a job on a timer. Without it, feature 20 has nothing to notice and a reviewer has nothing to see happen.
- It still needs the publishing question answered, so it skips none of the hard part.

## Rationale

The decision turned on measurement, twice, and the record should show that the first measurement was of the wrong thing.

Initially I recommended option 1 on the grounds that a model change was too expensive. The engineer chose option 2. I then measured the re-baseline cost and found it small, because `tests/oracle/` never calls `generate(` and the golden suite is formula based, so I told the engineer their choice was affordable and wrote the spec for it. That measurement was real but it answered the wrong question: it priced the *re-baseline* and not the *rework*. A cross check against the generator line by line showed the rework is the dominant term, with five separate `n` dependencies to remove and a set of absolute schedule numbers that have to satisfy D-2, D-3, the `SMALL` config and the minimum session floor simultaneously, plus an internal contradiction in the acceptance criteria I had written about delisting counts staying constant. On that evidence the engineer moved to option 1, which is where the design should have stayed.

Option 1 wins because the tick computes nothing. It filters a market the generator already produced and validated, so correctness is inherited rather than re-established, and the only new logic is a truncation rule. That rule is where the one real bug lived, and running the design rather than reasoning about it is what found it: nulling `delisted_on` beyond the cursor without nulling `delist_reason` fails `check_market` with "delist_reason and delisted_on must be set together". Running it also showed the two constants cannot be picked by taste. At seed 42, `n=1818` keeps the planted bear inside the published window while `n=2500` does not, and `delisting_fraction` at 0.05 leaves only 17 delistings inside the window against D-3's 20, so it has to rise to 0.08, which measures at 26.

The cost accepted is a finite runway of 558 ticks and a generator whose real limitation is still there. Both are recorded rather than hidden: AC-8 makes the end of the runway a clean, logged stop about two years out, and the prefix stable rewrite is enrolled in Follow-up as its own piece of work, to be done when it is the most valuable thing rather than because a writer needed it.

**One engineer choice against my recommendation, recorded deliberately.** I recommended a GitHub Actions cron for the schedule, because it needs no new AWS infrastructure and gives a free, clickable run history. The engineer chose EventBridge Scheduler plus a Lambda. The trade accepted: two more pieces of infrastructure created by hand before feature 24 exists to describe them, and tick logs in CloudWatch rather than in a tab already open. What it buys is that no write credential for the bucket ever leaves AWS, which is the stronger posture and the better answer to how this would run in production.

## References

**Project sources** (verifiable, in this repo):
- `engine/src/engine/synthetic/generator.py`: `_schedule`'s fraction based bear window (lines 68 to 73) and sequential `fill()`, `_market_returns`'s sized draw (line 97) and whole window bear planting (lines 99 to 103), and `_ohlcv`'s three `(m, n)` draws (lines 131 to 136). These are the five `n` dependencies that rule out extending a market.
- `engine/src/engine/synthetic/config.py`: `n_sessions`, `delisting_fraction`, `min_delisted`, `bear_start_range`, `bear_length_range`, `GENERATOR_VERSION`, and the file's own instruction to bump the version on any change to the model or its defaults.
- `engine/src/engine/data/sanity.py`: `check_market` and `bar_problems`, including the rule that `delisted_on` and `delist_reason` are set together, which the truncation rule has to respect.
- `tests/oracle/` and `tests/golden/reference.py`: fixture and formula based, never calling `generate(`, which is why the re-baseline does not reach the owner approved numbers.
- `tests/acceptance/test_data.py`, `test_backtest.py:373`, `test_exit_lab.py:249`, `engine/tests/sim/test_lab_budget.py`: the four files taking `generate(42)` as their market.
- `scripts/check_synthetic.py`: D-1 and D-3 proved by generating twice and comparing, which still passes under a config change.
- `engine/src/engine/data/store.py`: `write_market(market, out_dir)` taking a local directory, which is why the tick writes to a temp directory and uploads.
- Spec `0011`: the store layout, the bars then securities then meta write order, the change check the API uses to notice a tick, and the `s3:ListBucket` requirement; also the gap it left, which is that it specified reads from the store and not writes.
- Spec `0006`: the model this feature reconfigures, and the recorded 602,776 bar count that goes stale.
- `docs/01-market-research-and-product-spec.md`: D-1's determinism promise, D-3's planted bear and delisting counts, X-7's warm exit lab budget.
- `AGENTS.md`: the never list barring agents from `aws` write commands, which is why the function and the schedule are created by you.

**Measured in this repo on 2026-10-18** (run against the real generator, which is why these are not guesses):
- Bear placement at seed 42: `n=1260` gives sessions 605 to 730; `n=1818` gives 873 to 1053 (inside the published 1260); `n=2500` gives 1200 to 1448 (outside it). This is what fixes the master length.
- Truncated at session 1260 with `n=1818`: `delisting_fraction` 0.05 leaves 17 delisted (fails D-3's 20), 0.07 leaves 23, 0.08 leaves 26.
- The truncated market at `delisting_fraction` 0.08 shows a 50.0% benchmark drawdown and passes `check_market()`.
- Nulling `delisted_on` without `delist_reason` fails `check_market()` with "delist_reason and delisted_on must be set together".
- Session 1260 falls on 2025-10-31, the same date the current published dataset ends on, so the as of date does not jump.
- numpy 2.5.3: `SeedSequence` children are position addressable and stable, and `spawn_key=(i,)` addresses one directly. Measured while option 2 was still the plan; retained because the prefix stable rewrite in Follow-up would need it.

**Practices & standards**:
- Publish a prefix of validated data rather than computing at publish time, so correctness is inherited.
- Derived idempotency over locking: compute the target from committed state so a repeat run is a no op.
- Verify before write: regenerate and compare the immutable past on every run, since it is cheap here.
- Ordered writes with the pointer last, so an interrupted write is invisible to readers.
- Run the design, do not reason about it, when a sanity check already encodes the invariants.
- Version the generated artifact rather than mutating it in place, so old data stays readable.
