# 0011. Rationale: market data store

Reasoning, options and references for [index.md](index.md).

## Context

> ⚠️ Premise note: the scope row for feature 17 asks for "a database the API reads". The access pattern does not want one. The API reads the whole market once and hands it to Polars; it never filters bars by name or date, never joins, never aggregates in the store. Putting 630k immutable rows behind SQL so that there is a database means paying a query and a row by row materialisation on every cold start to rebuild the dataframe you started with, and it makes a free tier provider's idle policy into the public demo's uptime. The right framing is: this slice needs **a store the data can change in without a rebuild**, which is object storage for files read whole, and SQL later for the rows that genuinely need rows. Feature 17's wording about versioned migrations is honoured as a layout version plus a reviewable rewrite script, not DDL, which is a real step down and is recorded as a tradeoff.

The market is generated at image build time. `services/api/Dockerfile` runs `python -m engine.synthetic --seed 42 --out /data`, the runtime stage copies `/data` in, and `services/api/src/api/state.py` loads it once at import through `engine.data.read_market()`, then calls `use_cases.warm(market)` so template scans start warm. The dataset is three files: `bars.parquet`, `securities.parquet`, `meta.json`, about 11 MB for 500 tickers across 1260 sessions. The consequence is that the numbers on the deployed site can only change by rebuilding the image and redeploying, which makes feature 19's writer and feature 20's refresh impossible to build.

The forces that shaped the choice:

- **Cost.** $0 a month at rest is a project constraint, not an aspiration, and the demo may sit idle for weeks between visits. A store that pauses, sleeps or is reclaimed after inactivity turns an idle period into a broken portfolio link, which matters more here than it would in a system with traffic.
- **The access pattern is a whole file read.** Confirmed in the design conversation: the whole market loads at start and `warm()` pins the template columns. Nothing queries the store.
- **Cold start is a measured budget, not a guess.** Doc 01 §4 allows 10 seconds for cold start and the deployed function currently reads 2.66 seconds, so there is room for one in region read and no room for a provider that wakes from idle slowly. X-7 is a different criterion (the warm exit lab, 25 seconds), and it matters here only because a reload landing inside such a run must not push it over.
- **The engine boundary.** `engine` may not import web code (`engine/tests/test_engine_boundary.py`), and store access belongs in `engine/data`, its infrastructure layer. Anything heavier than a read, for instance an ORM or a connection pool, would sit awkwardly there.
- **Contracts are frozen.** `DataMeta`, `BARS_SCHEMA` and `SECURITIES_SCHEMA` are contract v1 (spec 0002, G0 tagged). Any change to them is a `contract-change` PR with a regenerated client, so a design that avoids touching them is materially cheaper.
- **D-5 and the leak model.** Live data runs only on the owner's machine. Doc 01's risk table counts "localhost only live mode" as one of the mitigations against an accidental real data leak, so moving live data anywhere reachable changes that model and needs a replacement control.
- **Six features stand on this one.** Features 18, 19, 20, 21, 22, 23 and 24 all wait on it, so a blank left here becomes a guess in six places.

## Options considered

### Option 1: One managed Postgres for everything

Bars, securities and later the saved rules, accounts and backtest runs in a single managed Postgres on a free tier (Neon, Supabase or similar).

**Pros**:
- One store, one credential, one thing to operate, and real reviewable migrations from day one, which satisfies feature 17's wording literally.
- The rows that features 21, 22 and 23 need are relational anyway, so it would be the only store the project ever has.
- The familiar answer to "where is your database", with nothing to explain.

**Cons**:
- Every cold start pays a round trip plus materialising 630k rows into Polars, to produce the dataframe a single 11 MB file read already gives.
- Most free tiers carry an idle or inactivity policy, and with no runtime fallback (ruled out in the design conversation) that policy becomes the demo's availability over weeks of no traffic. Neon suspends after 5 minutes but keeps the data and resumes in about half a second, which is survivable; Supabase pauses a free project after 7 days idle and needs a manual restore, which is not, for a link that may go unvisited for a month. Aurora DSQL is the exception, with a perpetual free allowance and no inactivity pause, so this con does not apply to every candidate.
- Polars dtypes would round trip through SQL types, putting the exact schemas that `BARS_SCHEMA.cast()` relies on at the mercy of a mapping.
- A connection layer in `engine/data` is heavier than that layer should carry.

### Option 2: A SQLite or DuckDB file in object storage

One database file in S3, fetched whole at start, giving SQL and real migrations in a single blob.

**Pros**:
- One fetch and real SQL, so feature 17's migration wording is satisfied without a relational service.
- No provider, no idle policy, no connection management.

**Cons**:
- Feature 19's writer appending a day to a database file in object storage has no locking story at all. Concurrent or interrupted writes to a single file over HTTP is a known way to lose data, and that is the next feature in the slice.
- The whole file is rewritten per append anyway, so the SQL buys nothing the Parquet layout does not already give.
- DuckDB would be a new dependency doing work Polars already does.

### Option 3: Parquet objects in S3, read whole, with a request driven change check (chosen)

The existing three files move into one object store prefix per data mode, read in full at start exactly as now, with meta carried as Parquet so one reader covers everything, and a reload triggered by the meta object's contents changing.

**Pros**:
- Matches the access pattern exactly: one read of the whole dataset, which is what the engine wants.
- No new runtime dependency and no extra import at cold start, because Polars 2.0 reads `s3://` natively and infers credentials from the environment variables Lambda already injects from the execution role.
- No idle policy, no pause, no reclamation, and about $0.0003 a month for 11 MB in Singapore.
- The contracts are untouched, so no `contract-change` PR.
- Local development keeps working against a plain directory, because `data/synthetic` and `data/live` already match the `<root>/<mode>` layout the store uses.
- Feature 19's append is one atomic PUT, and feature 20's refresh gets a change signal for free.

**Cons**:
- Not DDL migrations. A layout change is a rewrite script plus a version bump.
- The project ends slice 7 with two stores.
- Meta stops being readable by eye in the console, since it is Parquet rather than JSON.
- The `s3://` read path is not exercised by a plain local directory, which is why MinIO joins development and moto joins CI.

### Option 4: Fix in place, keep baking the market, make the rebuild cheap

Leave the data in the image and speed up the rebuild and redeploy instead.

**Pros**:
- No new infrastructure, no credentials, no store, nothing to operate. Genuinely the smallest change.
- Cold start stays exactly as measured.

**Cons**:
- It does not solve the problem. Feature 19's writer has nothing to append to and feature 20 has nothing to notice, so slices 6 and 7 do not start.
- Every data change stays a deploy, which is the thing feature 17 exists to remove.

## Rationale

Option 3 follows from the access pattern and the cost constraint together. The engine reads the whole market and nothing else, so the store's only job is to hand over about 11 MB and say when it changed; object storage does exactly that, with no service to wake, no connection to manage and no idle policy to outlive a quiet month, which matters because the runtime fallback was deliberately ruled out and the store therefore carries the demo's availability by itself. Polars already reads cloud paths and already reads Parquet, so the whole change is a path and a loader, not a new layer in `engine/data`, which keeps the engine boundary clean and leaves the frozen contracts alone.

Option 1 is the conventional answer and it is not wrong about slices 6 to 8 as a whole; it is wrong about the bars. Its real cost is not performance (630k rows is small) but that it puts a dtype mapping between the stored data and the schemas the oracle tests pin, pays a round trip and a row by row materialisation on every cold start to rebuild a dataframe a single file read already gives, and on most providers makes an inactivity policy load bearing for a portfolio link. Those costs buy DDL migrations for data whose schema is frozen by contract anyway. The inactivity objection does not hold against Aurora DSQL, which is free in perpetuity in this region; the access pattern objection still does, and that is the one that decides the bars. Option 2 dies on feature 19: the next feature in the slice is a writer, and a database file in object storage has no answer for concurrent or interrupted writes. Option 4 is the honest do nothing, and it is named because fixing in place is often right; here it simply does not solve the stated problem.

**Two places the engineer's choice differs from my recommendation, recorded deliberately.**

First, **live data in the store**. I recommended live stay on the local machine: live mode runs only there, `data/live` already works, and the function's execution role is scoped away from the live prefix anyway, so uploading real vendor prices buys no capability. The engineer chose to push live too, for a single uniform store. That is a conscious trade: doc 01's leak mitigation changes from "the data never leaves the machine" to "an IAM statement has no path to it", and the mitigations in the spec (prefix scoped `s3:GetObject`, the retained D-5 start check, and the seed script refusing a live push without an explicit flag) are what make it defensible rather than merely allowed.

Second, **the background reload**. I recommended reloading inline: the one unlucky request waits about 2.66 seconds and nobody writes a lock. The engineer chose the background reload after being told that Lambda freezes the execution environment the moment a response is sent, so a reload thread stops mid flight and only resumes when the next request thaws it, possibly minutes or hours later and possibly with a dead socket. The choice stands, and the spec pays for it properly: single flight, a failure that leaves the old market serving and retries at the next check, and an explicit acknowledgement that the stale window stretches with the traffic gap. The upside is real, which is that no request ever pays the reload, and the warm exit lab budget (X-7, 25 seconds) is a timed criterion a reload could otherwise eat into.

## References

**Project sources** (verifiable, in this repo):
- `AGENTS.md`: Clean Architecture layering, so store I/O belongs in `engine/data`; the never list barring `aws` write commands, so the bucket is created by hand; the rule that a new service needs an ADR, which this spec is.
- `engine/src/engine/data/store.py`: the current three file reader, `BARS_SCHEMA.cast()` and `check_market()`, all preserved.
- `services/api/src/api/state.py`: the load once at import plus `warm()` shape, and the existing tolerated missing dataset path that AC-6 keeps.
- `services/api/src/api/settings.py` and `live_mode_problems()`: the D-5 start check kept as is.
- `services/api/Dockerfile`: the build time generation step and the `/data` copy that AC-1 removes, and `scripts/smoke_image.sh` with the CI `api-image` job, whose template scan assertion AC-16 keeps working once the bake is gone.
- Spec 0002, contracts frozen as Pydantic models: why `DataMeta` and the Parquet schemas are left untouched.
- Spec 0005, the cached indicator engine and `warm()`: why AC-14 requires `warm()` on every reload.
- Spec 0006, the seeded synthetic market: the generator that the seed script pushes the output of.
- Spec 0010, live research mode: the `data/live` layout and the localhost only posture this spec modifies.
- `docs/01-market-research-and-product-spec.md`: D-5 as written, D-6's leak guard, the 10 second cold start budget in §4 with its 2.66 second reading, and X-7's separate 25 second warm exit lab budget, and the risk table entry naming localhost only live mode as a leak mitigation.

**Practices & standards**:
- Strangler pattern for a live migration: the new reader runs beside the baked dataset until the deployed function is proven on the store, which is why removing the bake is its own late phase.
- Measure before you remove: phase 3 measures cold start on the deployed function before phase 4 takes the fallback path away.
- Single flight for a shared refresh, so a change seen by many concurrent requests causes one reload.
- Monotonic time for interval logic, so a wall clock change cannot stall or spam the check.
- Least privilege on the object store: `s3:GetObject` on one prefix, and no `s3:ListBucket`, because every key is known.
- Atomic whole object replacement in object storage, rather than in place mutation, as the safe shape for an append.

**Links** (web verified only):
- Polars cloud storage guide, credentials inferred from environment variables when `storage_options` is not passed: https://docs.pola.rs/user-guide/io/cloud-storage
- `polars.read_parquet`, the `credential_provider` and `storage_options` parameters: https://docs.pola.rs/api/python/dev/reference/api/polars.read_parquet.html
- S3 Standard pricing in Asia Pacific (Singapore), $0.025 per GB month and $0.0004 per 1000 GET requests, a third party 2026 summary; confirm on the AWS pricing page before relying on it: https://upstash.com/blog/aws-s3-pricing-explained-2026
- AWS S3 pricing, the official page. The regional rate sits behind a selector the fetch could not read, and the current AWS free tier for S3 is credit based and time limited rather than perpetual, which is immaterial here at about $0.0003 a month: https://aws.amazon.com/s3/pricing/
- Neon free tier auto suspend, 5 minutes of inactivity, data retained, resume in roughly half a second: https://neon.com/faqs/postgres-hosting-options-auto-pause-database
- Aurora DSQL pricing, a perpetual free allowance of 100k DPUs plus 1 GB storage, available in `ap-southeast-1`: https://aws.amazon.com/rds/aurora/dsql/pricing/

Not web verified, named rather than linked: Supabase's free project pause after 7 days idle requiring a manual restore, found only in third party 2026 summaries and not on Supabase's own pricing page.
