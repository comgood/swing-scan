# 0011. Serve the market from Parquet objects in S3, read whole and reloaded on change

**Date**: 2026-10-18
**Status**: Proposed

## Summary

The market is baked into the API's container image today, so the only way the numbers change is a rebuild and a redeploy. This spec moves the three dataset files into object storage (S3, a store that holds whole files rather than rows) under one setting, keeps loading the whole dataset into memory exactly as the API does now, and adds a cheap check so a running instance notices when a day is appended. There is no SQL database: the bars are read in full every time and never queried by name or date, so a file store fits the access pattern and a relational one would not earn its cost. SQL arrives later, with feature 21, when saved rules need real rows.

## Requirements

**User stories**:
- As the owner, I want to change the market data without rebuilding and redeploying the API, so the demo can show something new.
- As the owner, I want a running instance to pick up an appended trading day by itself, so feature 19's writer and feature 20's refresh have something to stand on.
- As a reviewer, I want the store swap to leave every number identical, so I can trust that nothing about the research changed.

**Acceptance criteria** (the contract, each criterion is IDed and independently checkable):

- **AC-1**: With `MARKET_STORE_URI` pointing at an `s3://` prefix, `/scan` and `/backtest` serve from the store, and the container image contains no generated dataset and no generation step.
- **AC-2**: The same dataset loaded from a local directory and from an `s3://` prefix produces identical scan and backtest results.
- **AC-3**: With `DATA_MODE=live` and a live dataset in the store, the API on localhost serves it, and D-5 still holds: started on a non localhost host it exits with a clear error. Note that `Settings.from_env` and `state.py` already enforce D-5, so this is mostly a regression check rather than new work. What does change is the dataset level check's trigger: with the mode now selecting a prefix, that check only fires when the prefix and the dataset's own `data_mode` disagree.
- **AC-4**: The function's execution role cannot read the live prefix. A read of `<root>/live/` with that role's credentials fails with an access error, never with live prices.
- **AC-5**: A dataset whose `layout_version` is not the supported one is refused at load, with an error naming both the version found and the version supported.
- **AC-6**: A missing dataset leaves the API up and `/scan` answering 501, exactly as a missing local dataset does today. A dataset that loads but fails `check_market` raises, so a broken store never serves wrong numbers.
- **AC-7**: A request arriving at least 10 seconds after the previous check performs a check. If and only if `meta.parquet` differs from the loaded dataset's, that request reloads the market inline and then serves the new dataset, with `GET /api/v1/meta` reporting the new `end` date. A check that finds no change starts nothing.
- **AC-8**: A reload that fails leaves the previously loaded market serving, logs the failure, and is retried at the next check.
- **AC-9**: The seed script pushes a local dataset directory into the store and is rerunnable: two runs leave the store in the same state.
- **AC-10**: The seed script refuses to push a live dataset unless an explicit flag is passed.
- **AC-11**: Cold start including the store read stays inside the 10 second cold start budget in doc 01 §4 (measured at 2.66 s before this change), measured again on the deployed function and recorded. Separately, a warm exit lab run that happens to trigger a reload still meets X-7's 25 seconds.
- **AC-12**: `make dev` brings MinIO up with the bucket present and the dataset loadable, and the `s3://` read path is covered in CI by the **same MinIO** as a service container, so development and CI exercise one implementation rather than two fakes that can drift apart. No real AWS call in either.
- **AC-13**: `warm()` runs on load and on every reload, so the first template scan after either is not paying indicator computation (spec 0005, AC-7 and AC-8).
- **AC-14**: An API that started with no dataset reachable recovers by itself: once the dataset appears, the next check loads it and `/scan` stops answering 501, with no restart and no redeploy.
- **AC-15**: The image smoke test passes against an image carrying no dataset: `make smoke-image` bind mounts a generated dataset into the container with `MARKET_STORE_URI` pointing at it, and its template scan succeeds. This path touches no object store at all, real or fake, so it stays the fastest check in CI.

## Decision

**Chosen option**: Option 3: Parquet objects in S3, read whole, with a request driven change check.

Move `bars.parquet`, `securities.parquet` and a new `meta.parquet` into one object store prefix per data mode, read the whole dataset at start exactly as today, and reload it inline on the request that notices the stored meta object's contents have changed.

**Implementation skills**: `aws-serverless` (`aws/agent-toolkit-for-aws`, `.claude/skills/aws-serverless/`) · `aws-iam` (`aws/agent-toolkit-for-aws`, `.claude/skills/aws-iam/`) · `multi-stage-dockerfile` (`github/awesome-copilot`, `.agents/skills/multi-stage-dockerfile/`) · `python-testing-patterns` (`wshobson/agents`, `.claude/skills/python-testing-patterns/`)

## Feature design

**Data model sketch**

One prefix per data mode, three objects each. `DataMeta` and the two Parquet schemas are unchanged, so this needs no `contract-change` PR.

| Object | Key | Holds | Written by | Read by |
|---|---|---|---|---|
| bars | `<root>/<mode>/bars.parquet` | 630k rows (synthetic) or 770k (live), `BARS_SCHEMA` unchanged | the seed script, later feature 19's writer | `read_market()` |
| securities | `<root>/<mode>/securities.parquet` | `SECURITIES_SCHEMA` unchanged | same | same |
| meta | `<root>/<mode>/meta.parquet` | one row, two columns: `layout_version` (int) and `meta_json` (the `DataMeta` JSON string) | same | same, and its contents are the change key |

- `<root>` is `MARKET_STORE_URI`: `data` locally, `s3://<bucket>` deployed. There is deliberately **no version segment in the key**: the layout version lives in `meta.parquet`, which is one mechanism instead of two, and staging a second layout beside the first is a need this project does not have.
- `<mode>` is `synthetic` or `live`, which is already how `data/synthetic` and `data/live` are laid out, so the local directory case needs no special handling.
- The loader does not parse the path for a version. It reads `layout_version` out of `meta.parquet` and refuses a number it does not support (AC-5).
- `meta` is Parquet rather than JSON because Polars reads Parquet from a URI and cannot read JSON from one, so one reader covers all three objects with no extra dependency and no extra import at cold start. `GET /api/v1/meta` still returns the whole `DataMeta` over HTTP, so nothing is lost for debugging.
- **The change key is the contents of `meta.parquet`, not an ETag.** Polars offers no head or stat call, and an ETag would mean adding an object store client to `engine/data` purely to read one header, plus a separate modified time path for a local directory. Re-reading that one object (about 1 KB) and comparing its `meta_json` to the loaded dataset's costs one small read per check, behaves identically on a directory and on `s3://`, and needs nothing new.
- **Write order is bars, then securities, then meta last.** The change key lives in the object written last, so a reader that sees new meta is guaranteed to have new bars behind it. The reverse order would let a reload pick up new meta over old bars, which `check_market()` would not catch.

**State transitions** (the loaded market, in the API process)

```
none ──load──> loaded ──change seen──> reloading ──ok───> loaded (new dataset)
  ^   \                                    │
  |    \── dataset absent: stays none,     └── failure: back to loaded (old dataset),
  |        /scan answers 501                   retried at the next check
  |
  └── the check also runs while nothing is loaded, so a dataset that appears later
      is picked up by the next request (AC-14). Without this, a store absent at
      start would leave the API answering 501 until the container recycled.
```

**Error taxonomy** (which failure means "absent" and which means "refuse"):

| Condition | At start | During a reload |
|---|---|---|
| objects absent (`FileNotFoundError` locally, or a 404 from the store) | tolerated: no market, `/scan` answers 501, the check keeps looking (AC-6, AC-15) | tolerated: the old market keeps serving, retried at the next check |
| access denied (403) | raise, so a misconfigured role fails loudly instead of looking like an empty store. This row only works because the role has prefix scoped `s3:ListBucket`; without it a missing key also returns 403 and the two cases collapse | logged as a failure, old market keeps serving, retried |
| network or timeout | tolerated as absent, since a transient blip at start should not kill the container | logged as a failure, old market keeps serving, retried |
| Parquet parse error, or `check_market()` fails | raise: a broken dataset must never serve | the reload is abandoned, the old market keeps serving, logged loudly |
| unsupported `layout_version` | raise with both versions named (AC-5) | the reload is abandoned, logged loudly |

**API surface**

No new endpoints. Two existing surfaces change behaviour only:

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/api/v1/meta` | GET | none | `contract_version`, `data` (`DataMeta`, now reflecting the most recent reload) | none | none |
| `/api/v1/scan`, `/api/v1/backtest` | POST | unchanged | unchanged | none | 501 while no dataset is loaded (AC-6), 422 unchanged |

**Value sourcing**

| Action | Value produced or displayed | Source |
|---|---|---|
| load market | the dataset root | `MARKET_STORE_URI` env var, set in the Lambda environment at deploy and in `.env` for MinIO; replaces `SYNTHETIC_DATA_DIR` |
| load market | the mode prefix | `DATA_MODE` read straight from the environment inside `engine/data`, exactly as `market_dir()` reads `SYNTHETIC_DATA_DIR` today. Not via `Settings`: `state.py` calls `read_market()` at import (`state.py:43`) and `main.py:18` builds `Settings` only afterwards, so a `Settings` dependency would be an import order bug |
| load market | the layout version accepted | `SUPPORTED_LAYOUT_VERSION = 1`, a constant in `engine/src/engine/data/store.py` |
| load market | the dataset identity | the `DataMeta` JSON inside `meta.parquet`, contract unchanged |
| load market | S3 credentials, deployed | the `AWS_*` env vars Lambda injects from the function's execution role; Polars infers them with no `storage_options` passed |
| load market | credentials for `make dev-live` | your own, from the standard AWS chain (`~/.aws`), reading the real `s3://` live prefix. The MinIO development keys are synthetic only and never see live data |
| load market | the MinIO endpoint, locally | `AWS_ENDPOINT_URL` in `.env`, plus `AWS_ALLOW_HTTP=true` (object store refuses a plain http endpoint without it) and `AWS_REGION` (nothing injects one locally). Step 10 verifies Polars honours these from the environment and falls back to passing `storage_options` explicitly if it does not |
| change check | the change key | the contents of `<root>/<mode>/meta.parquet`, re-read and compared against the loaded dataset's `meta_json`. No ETag, no head call, no separate modified time path for a local directory |
| change check | the floor interval | `STORE_CHECK_FLOOR_SECONDS = 10`, set from feature 20's "updates within seconds" |
| change check | elapsed time | `time.monotonic()` in the API process, not wall clock, so a clock change cannot stall the check |
| change check | where it runs | one FastAPI middleware in `services/api`, calling a function in `engine/data`. One place per request, the engine boundary stays clean, and feature 20 extends this single hook rather than adding a second mechanism |
| reload | what serves meanwhile | the previously loaded market object, still referenced |
| AC-4's test | the role to assume | the function's execution role, by name from the deploy notes, assumed with `aws sts assume-role`. Not the OIDC deploy role, which pushes the image and is a different principal |
| as of marker in the UI | `DataMeta.end` | already returned by `GET /api/v1/meta`; no new field, no contract change |
| bucket name | the name itself | you choose it and set it in `MARKET_STORE_URI`; recommended shape `swing-scan-market-<short suffix>` in `ap-southeast-1` |

**Key invariants**

- `check_market()` runs on every load and every reload. A dataset that fails it is never served (AC-6).
- Appending a day never changes an existing bar. The seed script and later the writer rewrite the whole bars object in one PUT, which S3 applies atomically, and the invariant is enforced by a test comparing the prior rows byte for byte, not by the file layout.
- Meta is always written last, so the change key never advertises a dataset whose bars are not in place yet.
- The loaded market is always reached as `state.market`, never imported as a name (`from .state import market`). The reload swaps the module attribute, so a captured name would pin the old dataset forever. `main.py:47` and `catalog.py` already read it by attribute; keep it that way.
- Paths in `engine/data` stop going through `pathlib` for the dataset root. `Path("s3://b/v1")` collapses to `s3:/b/v1`, which is not a valid URI, so the root is joined as a string and only the local case touches the filesystem.
- A reload happens on the request that noticed the change, before that request is served. One request waits; nothing else is coordinated. There is no flag, no thread and no swap, because the reload finishes before the next request is handled.
- `warm()` always follows a successful load (AC-13).
- The engine's store access stays inside `engine/data`, its infrastructure layer. No `boto3`, no FastAPI, nothing web facing enters the engine, so `engine/tests/test_engine_boundary.py` still passes.

**Security model**

- No application auth anywhere; nothing about that changes.
- The function's **execution role** (the principal the Lambda assumes at runtime, not the OIDC role that deploys it) gets `s3:GetObject` on `<bucket>/synthetic/*`, plus `s3:ListBucket` on the bucket **conditioned to that same prefix**.

`s3:ListBucket` is required, not optional, and an earlier draft of this spec was wrong to omit it: without it S3 answers a request for a key that does not exist with `403 AccessDenied` rather than `404 NoSuchKey`. The error taxonomy below depends on telling those apart, so without the list permission a missing dataset is indistinguishable from a misconfigured role, and both AC-6 and AC-4 become uncheckable. The prefix condition keeps it from widening anything: the role still cannot see or read the live prefix.

```json
[
  { "Effect": "Allow", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::<bucket>/synthetic/*" },
  { "Effect": "Allow", "Action": "s3:ListBucket", "Resource": "arn:aws:s3:::<bucket>",
    "Condition": { "StringLike": { "s3:prefix": "synthetic/*" } } }
]
```

- The bucket blocks all public access and has versioning on, so a bad push is recoverable.
- The live prefix holds real vendor prices. Two things keep them out of the demo: the IAM statement above, which simply has no path to them (AC-4), and the existing D-5 start check in `state.py`, which is kept as is (AC-3). Your own credentials write both prefixes; the seed script refuses a live push without an explicit flag (AC-10).
- No PII, no regulated data, no compliance scope.

**Configuration required**

- `MARKET_STORE_URI`: the dataset root. `data` locally, `s3://<bucket>` deployed, `/data` inside the smoke tested image. Replaces `SYNTHETIC_DATA_DIR` everywhere (Makefile, Dockerfile, `scripts/smoke_image.sh`, tests, `engine/data/store.py`).
- `AWS_ENDPOINT_URL`: local only, points Polars at MinIO. Absent in deploy, so the real S3 endpoint is used.
- `AWS_ALLOW_HTTP`: local only, `true`. The object store layer refuses a plain http endpoint without it, so MinIO fails to read with a confusing error if this is missed.
- `AWS_REGION`: local only. Nothing injects a region outside Lambda and the object store needs one; any value works against MinIO, so use `ap-southeast-1` to match deploy.
- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`: local only, the MinIO development keys, in `.env` (already gitignored, and gitleaks already runs in pre-commit). Deployed, these plus `AWS_SESSION_TOKEN` come from the execution role and are never set by hand; the session token matters because role credentials are temporary and a reader that ignores it fails on Lambda. `make dev-live` uses your own credentials from the standard AWS chain instead, since it reads the real live prefix.
- `DATA_MODE`: unchanged, but now read inside `engine/data` from the environment rather than through `Settings`.

**Critical test scenarios**

- Happy path: a dataset in a local directory and the same dataset in a store produce identical scan output, verifies **AC-2**.
- Happy path, deployed: `/scan` and `/backtest` serve from `s3://` with no dataset in the image, verifies **AC-1**.
- Change detection: `meta.parquet` contents change, a request after the floor interval sees it and triggers a reload, a later request serves the new `end` date, verifies **AC-7**.
- Concurrency: two requests arrive together after a change and exactly one reload runs; both are served from the old market until the swap, verifies **AC-8**.
- Failure case: the store is unreachable at start, so the API comes up and `/scan` answers 501; a reload failing mid flight leaves the old market serving and logs it, verifies **AC-6** and **AC-8**.
- Recovery: the API starts with nothing in the store, the dataset is then pushed, and a later request serves it with no restart, verifies **AC-14**.
- Torn write: new bars are in place but meta has not been written yet, and the check does not reload until meta lands, verifies the write order invariant.
- Image: an image carrying no dataset passes `make smoke-image` with the dataset supplied to the container, verifies **AC-15**.
- Failure case: a dataset carrying an unsupported `layout_version` is refused with both versions named, verifies **AC-5**.
- Permission: a read of the live prefix with the execution role's credentials is denied, verifies **AC-4**.
- Permission: the API started off localhost with `DATA_MODE=live` exits with a clear error, verifies **AC-3**.
- Idempotency: the seed script run twice leaves the store identical, and refuses a live dataset without the flag, verifies **AC-9** and **AC-10**.

## Build plan

Tracer Bullet, so the thread lands first: one real dataset read from a real bucket, all the way through the deployed API, before any of the reload machinery exists. Steps 1 to 6 are that thread. Steps 7 onward thicken it.

1. `MARKET_STORE_URI` replaces `SYNTHETIC_DATA_DIR`; `read_market()` resolves `<root>/<mode>/` from the environment (both the root and `DATA_MODE`, inside `engine/data`, no `Settings` import), joining the root as a string rather than through `pathlib`, and treats a local path and a URI the same way. The rename reaches every caller listed under Consequences, including the Dockerfile's `--out` path, satisfies **AC-2**
2. `write_market()` also writes `meta.parquet` (`layout_version` plus the `DataMeta` JSON), meta written last; `read_market()` reads it and refuses an unsupported version. This changes D-1's hash set, so `scripts/check_synthetic.py`'s `FILES` tuple gains `meta.parquet`, and any existing local `data/` directory must be regenerated with `make data`, satisfies **AC-5**
3. `scripts/push_market.py` plus a `make push-market` target: upload a local dataset directory to the store in bars, securities, meta order, rerunnable, and refusing a live dataset without an explicit flag, satisfies **AC-9**, **AC-10**
4. You create the bucket by hand (`ap-southeast-1`, versioning on, all public access blocked) and push the synthetic dataset, satisfies **AC-1**
5. Point the deployed function's `MARKET_STORE_URI` at the `s3://` prefix, confirm `/scan` and `/backtest` serve from it, and measure cold start against doc 01 §4's 10 second budget, satisfies **AC-1**, **AC-11**
6. Remove the Dockerfile's `RUN python -m engine.synthetic` step and the `COPY --from=build /data /data` line, and give `scripts/smoke_image.sh` a dataset: `make data` first, then run the container with `data/synthetic` bind mounted and `MARKET_STORE_URI=/data`. Without this the CI `api-image` job's template scan answers 501 and fails, satisfies **AC-1**, **AC-15**
7. The error taxonomy from the design section: absent objects and transient network errors are tolerated and answer 501; access denied, a parse error, a failed `check_market()` and an unsupported layout version raise, satisfies **AC-6**
8. The change check as a FastAPI middleware calling into `engine/data`: re-read `meta.parquet` and compare its `meta_json` to the loaded dataset's, no more often than every `STORE_CHECK_FLOOR_SECONDS` on monotonic time, and run it while nothing is loaded too so a late arriving dataset is picked up, satisfies **AC-7**, **AC-14**
9. The inline reload: re-read the dataset, `warm()` it, rebind, then serve the request. On failure, log and keep the old market, retried at the next check, satisfies **AC-7**, **AC-8**, **AC-13**
10. MinIO in docker compose, wired into `make dev`, with the bucket created on start and `AWS_ENDPOINT_URL`, `AWS_ALLOW_HTTP` and `AWS_REGION` in `.env.example`. Verify here that Polars picks these up from the environment; if it does not, pass `storage_options` explicitly from `engine/data`, satisfies **AC-12**
11. The same MinIO as a CI service container, covering the `s3://` branch with no real AWS call. One fake, shared with `make dev`, rather than a second one in CI that could drift from it. (This is also why moto is not used: its in process mock patches `botocore`, while Polars reads S3 through Rust `object_store`, so moto would have needed server mode anyway, which is a second service for no gain.) satisfies **AC-12**
12. Scope the function's execution role to `s3:GetObject` on the synthetic prefix plus prefix conditioned `s3:ListBucket`, and verify two things with that role's credentials: a live read is denied, and a missing synthetic key returns 404 rather than 403 so the error taxonomy holds, satisfies **AC-4**, **AC-6**
13. Push the live dataset to its prefix with `make push-market` and the explicit live flag, confirm `make dev-live` serves it from the real `s3://` prefix using your own credentials, and that an off localhost start still exits, satisfies **AC-3**
14. Record the measured cold start and warm numbers in `docs/qa/traceability.md`, against doc 01 §4's cold start line and X-7 separately, satisfies **AC-11**

## Migration plan

**Strategy**: strangler. The new reader runs beside the baked dataset until the deployed function is proven on the store.

**Phases**:
1. Steps 1 and 2. The store reader exists and `MARKET_STORE_URI` still points at a local directory. **This phase is not invisible**, contrary to an earlier draft: `write_market()` now emits `meta.parquet`, so D-1's hash set changes, `scripts/check_synthetic.py` changes with it, and a stale local `data/` directory holding only `meta.json` will read as "no dataset" until regenerated. The Dockerfile's generate step also moves from `--out /data` to `--out /data/synthetic`, so the baked copy still matches the `<root>/<mode>/` layout the reader now expects, which is what keeps the rollback below working.
2. Steps 3 and 4. The bucket exists and holds the synthetic dataset. The API still reads the image.
3. Step 5. The deployed `MARKET_STORE_URI` points at `s3://`, while the image still happens to carry its baked copy. Measure here.
4. Step 6. The bake comes out of the image. This is the one way door.
5. Steps 7 to 14. The reload, local stack, tests, IAM and live mode.

**Rollback**: through phase 3, set `MARKET_STORE_URI` back to `/data` and redeploy. This only works because phase 1 moved the Dockerfile's output to `/data/synthetic`; with the original flat `/data` the reader would look for `/data/synthetic/` and find nothing, so the rollback would silently 501. After phase 4, roll back the commit that removed the Dockerfile steps. Phase 3's baked copy is a migration safety net for one deploy, not the runtime fallback that was explicitly ruled out: no code ever chooses between the store and the image.

**Risks**: cold start grows by one 11 MB read, which phase 3 measures before anything is removed. A wrong `MARKET_STORE_URI` in the deployed environment reads as a missing dataset, so `/scan` answers 501 rather than failing loudly; phase 3's check is `GET /api/v1/meta` returning the expected `end` date, not just a healthy response.

## Consequences

**Positive**:
- The data changes without a rebuild, which is the whole point of slice 6, and features 18, 19 and 20 get a store and a change signal to build on.
- The image gets smaller and builds faster: the synthetic generation step leaves the Dockerfile.
- No new runtime dependency and no new import at cold start, because Polars already reads cloud paths and already reads Parquet.
- Effectively free: 11 MB of S3 Standard in Singapore is about $0.0003 a month, and the store has no idle or inactivity policy that could take the demo down between visits.
- Versioning on the bucket makes a bad push recoverable.

**Negative / tradeoffs**:
- "Versioned migrations you can review" is weaker than DDL. A layout change is a committed rewrite script plus a version bump, reviewable as code but not a migration tool. Real migrations arrive with feature 21's SQL store.
- Two stores by the end of slice 7: objects for bars, SQL for rules, accounts and runs. That is the right fit per data shape and it is still two things to run.
- `meta` is no longer readable by eye in the S3 console, since it is now Parquet. `GET /api/v1/meta` is the way to read it.
- One request every day or two waits about 3 seconds while the market reloads. That is the whole cost of the inline choice, and it is why AC-11 checks that a warm exit lab run landing on a reload still meets X-7's 25 seconds.
- Every request now passes through a middleware that may do a small read, so the no change case costs one tiny Parquet read per 10 seconds of traffic rather than nothing at all.
- Real vendor prices will sit in the store's live prefix. Nothing deployed can read them, but the protection is now an IAM statement rather than the data never leaving the machine.

**Neutral**:
- `SYNTHETIC_DATA_DIR` is renamed rather than kept as an alias, and the blast radius is wider than the engine. Every one of these references it or `meta.json` and changes with it:
  - `engine/src/engine/data/store.py`, `.env.example:13`, `Makefile:142` (`dev-live`), `services/api/Dockerfile:24` and `:34`, `scripts/smoke_image.sh`
  - `scripts/check_synthetic.py:20` (D-1's hash set), `scripts/make_mocks.py:530` and `:619`
  - `engine/tests/dataset/test_store_and_sanity.py:51` and `:60`, `engine/tests/live/test_live_loader.py:191`
  - `tests/acceptance/support.py:338`, which is **QA lane and owned by `@comgood` in `CODEOWNERS`**. A builder cannot edit it, so this rename needs a coordinated PR with QA rather than a single lane commit. Treat that as a prerequisite, not a cleanup.
  - `engine/AGENTS.md` and `services/api/AGENTS.md` (`/sync` owns those edits)
- Four earlier specs document `SYNTHETIC_DATA_DIR` and go stale on this change: `0001` (its Configuration list and the image description), `0005`, `0006` (its surface table and configuration) and `0010` (`make dev-live`). Plus `docs/qa/ac-questions.md`, which tells QA how route tests supply a market. They are listed in Follow-up.
- An alias would avoid all of the above. It is not taken because two names for one setting in a project this small is the kind of thing that outlives its reason, and because the meaning changed: the old variable named a directory of files, the new one names a dataset root with a mode under it.
- `DataMeta` and both Parquet schemas are untouched, so no `contract-change` PR and no regenerated `api-client`.
- The bucket is created by hand now and imported by feature 24's Terraform later, rather than recreated.
- MinIO joins the development and test toolchain, as one service used by both `make dev` and CI. It is not deployed.

## Follow-up

- [ ] Feature 19's writer inherits this layout and the bars, securities, meta write order. The order makes an interrupted tick safe for readers (meta still points at the old dataset), but its spec should still pin how the writer recovers from its own partial tick, and whether it pins object versions while it works.
- [ ] Feature 20 should build its refresh on the change check from AC-7 rather than adding a second mechanism.
- [ ] Feature 24's Terraform imports the existing bucket and the prefix scoped policy rather than creating new ones.
- [ ] Feature 21 brings the SQL store for rules, and later accounts and runs. Start that decision from Aurora DSQL: it is the one candidate found with a perpetual free allowance (100k DPUs plus 1 GB) and no inactivity pause, and it is available in `ap-southeast-1` beside the function. Revisit then whether bars should join it; this spec expects not.
- [ ] The `SYNTHETIC_DATA_DIR` rename makes four specs stale: `0001` (Configuration required, and the image description naming the flat `/data`), `0005` (its market sourcing row and configuration), `0006` (its surface table, `market_dir()` description and configuration) and `0010` (`make dev-live`). Also `docs/qa/ac-questions.md`, which documents how route tests supply a market. `/sync` flags these; updating a spec's content is `/architect`'s to do.
- [ ] `tests/acceptance/support.py:338` is QA owned (`CODEOWNERS`, `@comgood`). Agree the rename with QA before step 1, or the build stalls at a file the builder lane may not touch.
- [ ] No `docker-compose` file exists in the repo today, so step 10 creates the first one. Worth deciding then whether feature 18's one command stack extends it or replaces it.
- [ ] MinIO is not yet named in `AGENTS.md`. It is area specific, so it belongs in `engine/AGENTS.md` rather than root. `/sync` owns that edit.
- [ ] The decline of an Agent Skill and MCP search for MinIO should be recorded on the `Declined:` line in `engine/AGENTS.md`, so a later stage does not offer it again.

## Rationale

Reasoning, the options weighed, and the references: see [rationale.md](rationale.md).
