# 0012. Generate a longer market once, publish it one session at a time behind a cursor

**Date**: 2026-10-18
**Status**: In Progress

## Summary

A job on a timer appends one more simulated trading day to the store so the site always has something new to show. The generator cannot extend a market (asking it for one more session reshuffles the whole thing), and making it able to would mean rewriting its randomness from top to bottom. So instead the market is generated longer than it is published: 1818 sessions exist, 1260 are published, and a tick moves the published boundary forward by one. The master is never stored anywhere, because the writer regenerates it from the seed on every tick, which also gives the tick a free integrity check on the data already published.

## Requirements

**User stories**:
- As the owner, I want the demo's data to move on its own, so the site is not a frozen snapshot.
- As the owner, I want every published day to be reproducible from the seed, so the research claims survive someone checking them.
- As a reviewer, I want a tick to be incapable of corrupting history, by construction rather than by promise.

**Acceptance criteria**:

- **AC-1**: A tick advances the published window by exactly one trading day: `meta.end` moves to the next session, bars gain that session's rows, and every bar already published is unchanged.
- **AC-2**: Before publishing, a tick regenerates the master from `meta.seed` and compares the published bars to the master's first `N` sessions. A mismatch aborts the tick and writes nothing.
- **AC-3**: A tick run twice for the same target session is a no op the second time, with no lock involved: the second run sees `meta.end` already at that session and exits successfully.
- **AC-4**: A tick interrupted after bars but before meta leaves readers on the previous dataset, and the next tick completes it. No reader ever sees new bars under old meta.
- **AC-5**: The published dataset passes `check_market()` at every cursor position, including that `delisted_on` and `delist_reason` are either both set or both absent.
- **AC-6**: Nothing beyond the cursor is readable. The published objects contain no bar after `meta.end`, and no `listed_from`, `delisted_on` or `delist_reason` dated after it.
- **AC-7**: D-3 holds at every cursor position: at least 20 delisted tickers and a benchmark drawdown of at least 20% are present in the published window, starting from the initial cursor.
- **AC-8**: When the cursor reaches the master's last session the tick stops cleanly: it logs that the runway is exhausted and exits successfully, without error and without writing.
- **AC-9**: The tick runs on a schedule with no human involved, and its outcome (advanced, already current, aborted, or exhausted) is visible in CloudWatch Logs.
- **AC-10**: The synthetic banner and `/api/v1/meta` stay truthful: `data_mode` is still `synthetic`, `data_version` reads `synthetic-2`, and the as of date is the newly published session.
- **AC-11**: The writer never touches the live prefix. Its execution role has write permission on the synthetic prefix only.
- **AC-12**: Ticking stays inside the free tier: one schedule, one daily invocation, and the cost of a tick is recorded after the first week.
- **AC-13**: The four test files that take `generate(42)` as their market pass on the new configuration, and X-7's warm exit lab timing is re measured and recorded.

## Decision

**Chosen option**: Option 1: generate a longer market once, publish it behind a cursor.

The generator is left exactly as it is. `n_sessions` becomes 1818, the published window starts at 1260 sessions, and a tick advances the boundary by one session after verifying that what is already published matches the master.

**Implementation skills**: `aws-serverless` (`aws/agent-toolkit-for-aws`, `.claude/skills/aws-serverless/`) · `aws-iam` (`aws/agent-toolkit-for-aws`, `.claude/skills/aws-iam/`) · `python-testing-patterns` (`wshobson/agents`, `.claude/skills/python-testing-patterns/`)

## Feature design

**The numbers, all measured rather than chosen**

These are not free parameters. They were derived by running the real generator on 2026-10-18, and the derivation matters because the obvious values do not work.

| Constant | Value | Why this value |
|---|---|---|
| `n_sessions` (the master) | **1818** | The bear window is drawn as a fraction of `n_sessions` (`bear_start_range` 0.24 to 0.55, `bear_length_range` 0.095 to 0.143), so a longer master pushes the bear past the published window. Measured at seed 42: `n=1818` puts the bear at sessions 873 to 1053, inside the published 1260; `n=2500` puts it at 1200 to 1448, outside. 1818 is near the ceiling that keeps the bear publishable from day one |
| `PUBLISHED_START_SESSIONS` (initial cursor) | **1260** | Today's published length. Keeps the demo's history the same length, and measured: session 1260 falls on **2025-10-31**, which is exactly the date the current dataset ends on, so the as of date does not jump when this lands |
| `delisting_fraction` | **0.08** (from 0.05) | Delistings are placed across the whole master, so truncation drops the ones beyond the cursor. Measured at `n=1818`: 0.05 leaves **17** delisted inside the published window and **fails D-3's 20**; 0.07 gives 23; 0.08 gives **26**, which clears D-3 with margin and only grows as the cursor advances |
| runway | **558 ticks** | 1818 minus 1260. About two years and two months of daily ticks |

Verified on the truncated market at the initial cursor: 26 delisted, a 50.0% benchmark drawdown, and `check_market()` passing.

**The master is never stored**

The writer regenerates the 1818 session master in memory from `meta.seed` on every tick. That is about 7 seconds of compute for a daily job, and it buys three things at once:

- No master object exists, so the unpublished future is not merely unserved, it is nowhere. There is nothing to leak and nothing to secure.
- The regeneration doubles as AC-2's integrity check: the tick already holds the authoritative data, so comparing it to what is published is free.
- No second storage location, no second prefix, no extra IAM statement.

**The tick**

```
read meta ──> N = index of meta.end in the master's session dates
               │
               ├── N+1 beyond the master?  ──> log "runway exhausted at <date>", exit 0   (AC-8)
               │
               ├── regenerate master from meta.seed
               │     └── published bars != master[..N]  ──> exit non zero, write nothing   (AC-2)
               │
               └── truncate the master at N+1, then write:
                     bars.parquet ──> securities.parquet ──> meta.parquet                 (AC-4)
```

Idempotency comes from the target being derived from `meta.end` rather than counted, so two runs compute the same target and the second finds the cursor already there (AC-3). Safety on a half finished tick comes from spec `0011`'s write order: meta last, so readers stay on the old dataset until everything else is in place.

**The truncation rule** (this is where the real bug was)

Truncating bars is a filter. Truncating `securities` is not, because its rows carry dates in the future that must not be revealed. Nulling them naively breaks the dataset: `check_market()` requires `delisted_on` and `delist_reason` to be set together, and nulling only the date fails with *"delist_reason and delisted_on must be set together"*. Measured, not predicted. So:

| Column | Rule at cursor date `C` |
|---|---|
| `bars` | keep rows where `date <= C` |
| `securities.delisted_on` | null when it is after `C` |
| `securities.delist_reason` | null when `delisted_on` is after `C`, **together with the date** |
| `securities.listed_from` | null when it is after `C` |

**API surface**

None. The writer has no HTTP surface. Two existing surfaces reflect its work:

| Endpoint | Method | Changes |
|---|---|---|
| `/api/v1/meta` | GET | `data.end` advances after a tick, `data.data_version` reads `synthetic-2` |
| `/api/v1/scan`, `/api/v1/backtest` | POST | one more session of data once the API reloads it, via `0011`'s change check |

**Value sourcing**

| Action | Value produced | Source |
|---|---|---|
| tick | the current session index `N` | the position of `meta.end` in the master's session date list. Derived from the master, not counted from a config, so a calendar assumption cannot drift from the data |
| tick | the seed | **`meta.seed`, read from the published dataset**, never an environment variable. A seed supplied separately could disagree with the published data, which would make AC-2 abort on every tick for no reason |
| tick | the target session | the master's session `N+1`, and its date is the master's own date for that session, so no weekday arithmetic is reimplemented |
| tick | the master's length | `SyntheticConfig.n_sessions` = 1818 |
| tick | the initial cursor | `PUBLISHED_START_SESSIONS` = 1260, a new constant in `engine/synthetic/config.py`, used only by the seed step |
| tick | which tickers have a bar that session | the master, unchanged. The generator already decides listings and delistings |
| tick | `data_version` | `GENERATOR_VERSION = "synthetic-2"`, bumped because `n_sessions` and `delisting_fraction` changed and the config file's own rule is to bump on any change to the model or its defaults |
| tick | how it writes to the store | `write_market()` on `market_uri()` directly, with no temp directory and no separate upload step, which is the same call `scripts/push_market.py` already makes against the store. **Amended 2026-10-19, after the build**: this row first described a temp directory plus an upload. Polars 2.0's `write_parquet` writes to a cloud URI and reads its credentials from the environment, so the upload step was never needed. Spec `0011` specified reads from `s3://` but not writes, and that gap is still open in one respect: the `mkdir=True` in `write_market()` is unverified against an object store, which has no directories. The first `make push-market STORE_URI=s3://...` settles it for the tick and the seed step at once; if it errors, `mkdir` goes behind a local path check |
| tick | its exit status and log line | the function's own stdout, collected by CloudWatch Logs. No metric and no alarm, which keeps this at $0 |
| schedule | the cron expression | the schedule's definition, created by hand now and adopted by feature 24. Once a day at `00:00` UTC |
| AC-12's cost figure | the measured cost | your AWS bill after the first week; recorded once known rather than estimated |

**Key invariants**

- The published dataset is always a prefix of the master. Nothing is ever computed at publish time, only filtered.
- A tick writes bars, then securities, then meta. Never another order.
- A tick that cannot verify the published prefix writes nothing at all.
- `delisted_on` and `delist_reason` are nulled together, always.
- `check_market()` runs on the truncated market before it is written, so a tick cannot publish a dataset that fails its own sanity rules.
- The writer is the only thing that writes the synthetic prefix after the seed step, so there is one writer and no coordination problem.
- The simulated clock advances one session per tick and is not tied to the wall clock, so a missed day is caught up by the next tick rather than skipped.

**Security model**

- No HTTP surface, so no authentication to design.
- The writer's execution role gets `s3:PutObject` and `s3:GetObject` on `<bucket>/synthetic/*` plus the prefix conditioned `s3:ListBucket` spec `0011` requires, and nothing on the live prefix (AC-11). It is a different role from the API's, which has no write permission.
- The unpublished future never exists outside the writer's memory (AC-6), so there is nothing to protect.
- No vendor credentials and no personal data. The data is invented.

**Configuration required**

- `MARKET_STORE_URI` and `DATA_MODE`: as spec `0011`, set in the writer function's environment.
- No seed variable, deliberately: the seed comes from the published dataset.
- No new secrets.

**Critical test scenarios**

- Happy path: a tick advances `end` by one session and leaves every earlier bar identical, verifies **AC-1**.
- Integrity: a store whose bars were altered aborts the tick with nothing written, verifies **AC-2**.
- Idempotency: the same tick run twice advances the cursor once, verifies **AC-3**.
- Torn write: a tick killed between bars and meta leaves readers on the old dataset, and the next tick completes, verifies **AC-4**.
- Truncation: at several cursor positions the published market passes `check_market()`, including the delist pair rule, verifies **AC-5**.
- No leakage: no published bar is dated after `end`, and no `listed_from`, `delisted_on` or `delist_reason` is either, verifies **AC-6**.
- D-3 at the boundary: the initial cursor has at least 20 delisted and a 20% drawdown, and so does the cursor at the end of the runway, verifies **AC-7**.
- Exhaustion: with the cursor at the master's last session, the tick logs and exits 0 without writing, verifies **AC-8**.
- Permission: the writer's role cannot write the live prefix, verifies **AC-11**.
- Regression: the four `generate(42)` test files pass on the new configuration, verifies **AC-13**.

## Build plan

Tracer Bullet. The thread is one real appended day visible on the deployed site, which needs the new configuration published first.

1. `n_sessions` to 1818, `delisting_fraction` to 0.08, `PUBLISHED_START_SESSIONS` = 1260, `GENERATOR_VERSION` to `synthetic-2`, satisfies **AC-10**
2. `engine.data` gains the truncation function: filter bars at a cursor date, null the three securities columns with the delist pair kept together, run `check_market()` on the result, satisfies **AC-5**, **AC-6**
3. A test that the truncated market satisfies D-3 at the initial cursor and at the end of the runway, satisfies **AC-7**
4. Re-baseline: run the four `generate(42)` test files, re measure X-7's warm exit lab timing, update `docs/specs/0006-synthetic-market/index.md`'s recorded bar count, record the new numbers, satisfies **AC-13**
5. The truncation gets one home, a `--published` flag on the existing `python -m engine.synthetic` CLI, and `make data` plus `services/api/Dockerfile` both pass it. `scripts/push_market.py` is left alone and still just copies `data/<mode>` into the store, so `make push-market STORE_URI=...` seeds the initial cursor. **Amended 2026-10-19, after the build**: this step first said to put the truncation inside `push_market.py`. That would have left the Dockerfile generating the full master, baking all 1,818 sessions into the image and publishing the future there, against this spec's own "the future is nowhere" invariant. One truncation path rather than two, same AC-10 outcome. Satisfies **AC-10**
6. The tick command (`python -m engine.synthetic.tick`): read meta, derive `N` and the seed from it, regenerate, verify the prefix, truncate at `N+1`, write bars then securities then meta, handle the already current and exhausted cases, satisfies **AC-1**, **AC-2**, **AC-3**, **AC-4**, **AC-8**
7. Run the tick locally against MinIO, confirm one session appended and the API picking it up through `0011`'s change check, satisfies **AC-1**, **AC-10**
8. You create the writer Lambda by hand from the existing API image with the tick command, `2048 MB`, `300 s`, and its own execution role scoped to write the synthetic prefix, satisfies **AC-9**, **AC-11**
9. You create the EventBridge Scheduler schedule, once a day at `00:00` UTC, targeting that function, satisfies **AC-9**
10. Watch one real scheduled tick end to end: the session appears on the deployed site, the log line reads correctly, and the cost is recorded after a week, satisfies **AC-9**, **AC-12**

## Migration plan

**Strategy**: big bang on the dataset. The generator is unchanged, but `n_sessions` and `delisting_fraction` are not, so the published market's numbers change once. There is no way to avoid that while also having a master to publish from, because the current 1260 session market is not a prefix of any longer one.

**Phases**:
1. Steps 1 to 4. The new configuration exists and the suite is re-baselined. Nothing is published, so the deployed site is untouched.
2. Step 5. The store is re-seeded at the initial cursor. The deployed site's numbers change here, and this is the visible moment. The as of date does not change: session 1260 is still 2025-10-31.
3. Steps 6 and 7. The tick exists and works locally.
4. Steps 8 to 10. The schedule runs it for real.

**Rollback**: through phase 1, revert the commits. After phase 2, push the previous dataset back; the bucket has versioning on, so the prior objects are recoverable, and the loader reads a `synthetic-1` dataset without complaint. After phase 4, disable the schedule, which stops any further change immediately without touching data.

**Risks**: the re-baseline moves every number the demo shows. `docs/reviews/` and the README record what was measured at the time, so they stay as history; only `0006`'s surface table, which claims to describe the current dataset, is updated. The runway is finite at 558 ticks, and AC-8 makes its end a clean stop rather than a failure, but it is a date in about two years when this feature stops doing anything.

## Consequences

**Positive**:
- The generator is not touched. D-1, D-2, the oracle fixtures, `check_market` and every property the model already satisfies are left exactly as they are, which is the whole reason this option was chosen over a prefix stable rewrite.
- The tick is small and provably safe: a derived target, a verified prefix, a filter, and an ordered write. No lock, no run log, no state outside the store.
- The unpublished future exists only in memory during a tick, so there is nothing stored that should not be read.
- Regenerating to verify turns "history cannot change" from a claim into a check that runs on every tick.
- One image for the API and the writer, so the engine code they share cannot drift.
- Every number in this spec was measured on the real generator, including the two that the obvious choices get wrong.

**Negative / tradeoffs**:
- **Finite runway.** 558 ticks, about two years and two months, after which the feature stops advancing. AC-8 makes that a clean stop, and extending it means a new master length, which is another re-baseline.
- The published demo dataset changes once, and with it every number quoted about it. Unavoidable in any version of this feature.
- `delisting_fraction` moved from 0.05 to 0.08 for a reason that has nothing to do with realism: it is compensation for truncation dropping delistings beyond the cursor. That is a model parameter bent to serve a publishing mechanism, and it should be read that way.
- The generator's inability to extend a market is left in place. This feature works around it rather than fixing it, and the workaround is what imposes the runway.
- A tick regenerates 1818 sessions every day purely to verify and slice. About 7 seconds, which is cheap, but it means tick cost grows if the master ever grows.
- Two more pieces of AWS infrastructure created by hand before feature 24 exists to describe them.

**Neutral**:
- `GENERATOR_VERSION` becomes `synthetic-2` because the config changed, not because the model did. Older datasets stay readable.
- The writer has no HTTP surface, so the contracts and the generated client are untouched.
- Observability is log lines only, with no metric or alarm, which is a deliberate $0 choice.
- Spec `0011` specified reading from the store but not writing to it. This spec fills that gap by reusing the upload path from its push script.

## Follow-up

- [ ] The generator cannot extend a market, and this feature works around that rather than fixing it. Enroll the prefix stable rewrite as its own scope feature so the defect is on the record: it is a rewrite of the randomness architecture (the schedule, the bear planting, the per ticker blocks and `_ohlcv` are all `n` dependent), not a patch, and it would remove the runway limit entirely.
- [ ] Decide before the runway runs out, in about two years, whether to extend the master or do the rewrite. AC-8 makes the deadline visible in the logs rather than a surprise.
- [ ] Feature 24's Terraform adopts the writer function, its role and the schedule rather than recreating them.
- [ ] Feature 18's one command local stack should include a way to run a tick, so a reviewer can watch the data move without waiting a day.
- [ ] `docs/reviews/2026-10-08-verify-synthetic-market.md` and the README quote the old numbers. They are historical records, so they stay, but the README's live figures should be checked after step 4.
- [ ] Deliberately out of scope: a tick that appends several sessions at once. One tick, one session.

## Rationale

Reasoning, the options weighed, and the references: see [rationale.md](rationale.md).
