# 0014. Save rules as one jsonb row in Neon Postgres, with writes that exist only on your machine

**Date**: 2026-10-18
**Status**: Accepted

## Summary

You can save a rule you built under its name, list what you saved, load one back into the builder and delete it. The rows live in a managed Postgres (Neon), with a real migration chain run by Alembic, and each rule is stored as the contract's own JSON in a single `jsonb` column. Saving works on your machine only: there are no accounts until feature 22, so on the public demo these endpoints answer 501 and the save control is hidden, the same way live data mode already exists locally and not in public. This is the first thing in the project that writes to a database.

## Requirements

**User stories**:
- As the owner, I want to save a rule I built, so I do not have to rebuild it from a link each time.
- As the owner, I want to see what I have saved and load one back into the builder exactly as it was.
- As the owner, I want a bad rule rejected with an error the form can already show, not a crash.
- As the owner, I do not want a public write endpoint on my demo while there are no accounts.

**Acceptance criteria**:

- **AC-1**: A saved rule survives a process restart and a container recycle: it is in the database, not in memory and not in browser storage.
- **AC-2**: A rule loaded back equals the rule that was saved, field for field, including condition order and every `n` the contract defaulted.
- **AC-3**: A malformed rule comes back as a 422 whose error paths match the ones `/scan` already produces, so `fieldErrorsFrom422` displays it with no new mapping.
- **AC-4**: Saving under a name that already exists is a 409, not a silent overwrite and not a duplicate. Name uniqueness ignores case, so `Foo` and `foo` collide.
- **AC-5**: Migrations run as a reviewable, versioned chain: a fresh database reaches the current schema by running them in order, and each one is a file of plain SQL in the repo.
- **AC-6**: On the deployed API every rules endpoint answers 501 and the web app hides the save control, with no database configured and no write path reachable. The web app does not distinguish "not available here" from "not configured locally", because it hides the control either way.
- **AC-7**: Setting a database URL on the deployed function does not open the feature: the same host rules that gate live data mode (D-5) also gate this, so Lambda and CI refuse regardless of configuration.
- **AC-8**: `DELETE /api/v1/rules/{id}` works from the browser. `main.py:34` currently sets `allow_methods=["GET", "POST"]`, so `DELETE` must be added or the preflight fails before the request is ever made.
- **AC-9**: The API opens its database connection inside the request, never at import, and a function that has been idle serves the next request without a stale connection error.
- **AC-10**: Every critical scenario that needs a real Postgres skips cleanly when none is configured, so `make ci` stays green, following the precedent D-4 already set for live data (`docs/qa/traceability.md`: "skips where there is none, so CI is green and the owner's local run is its evidence"). Your local run against Neon is the evidence for those criteria.
- **AC-11**: The contract change goes through the project's `contract-change` process: the regenerated `api-client`, updated mocks, and owner approval.

## Decision

**Chosen option**: Option 4: Neon Postgres, the whole rule in one `jsonb` column, Alembic migrations, local only writes.

One table holding the rule exactly as the contract produced it, a migration chain in the repo, `psycopg` over Neon's pooled endpoint connecting per request, and the whole surface disabled anywhere but your own machine. Option 3, the normalised version of the same database, was chosen first and dropped before the build; `rationale.md` records why.

**Implementation skills**: `neon-postgres` (`neondatabase/agent-skills`, `.agents/skills/neon-postgres/`) · `postgresql-table-design` (`wshobson/agents`, `.agents/skills/postgresql-table-design/`) · `fastapi` (`fastapi/fastapi`, `.agents/skills/fastapi/`) · `pydantic` (`.agents/skills/pydantic/`) · `python-testing-patterns` (`wshobson/agents`, `.claude/skills/python-testing-patterns/`) · `aws-serverless` (`aws/agent-toolkit-for-aws`, `.claude/skills/aws-serverless/`)

`neon-postgres` and `postgresql-table-design` were installed for this feature. Its conventions are authoritative where they conflict with generic advice, and `neon-postgres` is the first place to look for build step 2's pooled endpoint and psycopg questions.

## Feature design

**Where the code lives**

Root `AGENTS.md` places Infrastructure at `engine/{data,synthetic}`, Application at `engine.api` use cases, and Presentation at `services/api`. `services/api/AGENTS.md:32` is stricter still: "Routers call `engine.api` use cases only". So there are **three** layers here, not two:

- the repository lives in **`engine/src/engine/data/rules.py`**, beside the market store, which is where this project puts I/O. It is `psycopg` and plain SQL: **no SQLAlchemy models**. With one table and four statements there is nothing for an ORM to earn, and a model layer would put the `Rule` shape in a third place after Pydantic and the DDL;
- the use cases live in **`engine.api`** (`save_rule`, `list_rules`, `load_rule`, `delete_rule`), thin orchestrators that take and return contract models;
- the router in `services/api/src/api/routes/rules.py` calls **only** those use cases, never the repository.

`engine/tests/test_engine_boundary.py` bars FastAPI, Starlette and uvicorn from the engine. `psycopg` is neither, so this does not weaken the boundary.

**Alembic without SQLAlchemy models.** Alembic needs SQLAlchemy as a library but not as an ORM: migrations are `op.execute()` with the SQL written out, which is the reviewable artifact you wanted in the first place. You get the version chain and the tooling, and the schema stays something you read rather than infer from models.

An earlier draft put the repository in `services/api` and had routes call it directly, which contradicted both documented rules.

**Neon is a new external service, and root `AGENTS.md`'s never list says not to add one without an ADR.** This spec is the deliberation, so it serves as that record: the decision, the options weighed and the consequences are all here and in `rationale.md`. If the project keeps ADRs as a separate numbered series (`rule.py` references `ADR-013`), this decision needs an entry there pointing at this spec, which is in Follow-up.

**Data model**

One table. The rule travels as `jsonb`, exactly the shape `Rule` already validates and already serialises through the `?r=` link.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | uuid | no | primary key, a uuid4 generated by the application |
| `name` | varchar(40) | no | the rule's own `name`, bounded to match the `Name` contract. Unique on `lower(name)`, so uniqueness ignores case (AC-4) |
| `rule` | jsonb | no | the whole `Rule` as the contract produced it |
| `created_at` | timestamptz | no | default `now()` |
| `updated_at` | timestamptz | no | default `now()` |

**Why not normalised conditions.** An earlier draft had a second `rule_conditions` table with fourteen columns, a five way discriminator check, value checks on the operator and the operand kind, range checks on the offsets and multipliers, a `position` column to preserve order, and a cascade needing both `ondelete="CASCADE"` and `passive_deletes=True`. All of it existed to re-express constraints the `Rule` contract already enforces, in a second place, for data nothing ever queries inside. It also cost four acceptance criteria of its own and most of a round trip test matrix. Storing the contract's own output in one column deletes all of that: condition order is preserved because a JSON array is ordered, `n` round trips because nothing decomposes it, a new contract field needs no migration, and there is no child table to cascade. The `Rule` contract remains the single validator, which it was always going to be.

**What this gives up**, stated plainly: the database cannot reject a hand written bad row, and nothing can ever query across rules by indicator. Neither matters here, because every write goes through the contract and nothing in this project asks which rules use RSI. If a future feature needs that query, a generated column or an index on the `jsonb` answers it without a schema redesign.

**Forward compatibility** is free rather than disciplined: a rule saved before the contract grew a field still parses, and Pydantic fills the new field from its default on read.

**API surface**

Three endpoints, not four: the list returns **full rules**, so loading one back into the builder needs no separate fetch. There will be a handful of rules, each at most 8 conditions, so the payload is tiny and a `GET /rules/{id}` would be an endpoint, a response model and a mock for nothing.

The request body is **the `Rule` itself**, not a wrapper. `Rule` already carries `name`, so a wrapper would mean two names to reconcile, and it would shift every validation error path from `body.conditions.0...` to `body.rule.conditions.0...`, breaking the existing `fieldErrorsFrom422` mapping for no gain.

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/api/v1/rules` | POST | `Rule` | `id`, `name`, `created_at` | none | 409 duplicate name, 422 bad rule, 501 disabled |
| `/api/v1/rules` | GET | none | list of `id`, `name`, `rule`, `created_at` | none | 501 disabled |
| `/api/v1/rules/{id}` | DELETE | `id` path | no body | none | 404, 501 disabled |

New endpoints, so this is a **contract change**: new response models, a regenerated `packages/api-client`, updated mocks, and owner approval (AC-11).

**No request size limit, and why.** An earlier draft promised a 413. Nothing in FastAPI or Starlette produces one, so it would need custom middleware handling a missing `Content-Length`. It is also unnecessary: `Rule` bounds the body to at most 8 conditions of bounded numeric fields plus a 40 character name, so a valid body is tiny and an invalid one is a 422. The surface is local only, so a deliberately huge body is a problem you would be causing yourself. **Feature 22 must add a body limit when it opens this publicly**, and that is recorded in Follow-up rather than half built here.

**Value sourcing**

| Action | Value produced or displayed | Source |
|---|---|---|
| save | the rule's `id` | a `uuid.uuid4()` in the repository before insert, so the id exists before the row |
| save | `created_at` and `updated_at` | Postgres `now()` as a column default, so the database's clock is the only clock |
| save | the name | `Rule.name` from the body, bounded by the existing `Name` contract to 1 to 40 characters after strip |
| save | the write | one `INSERT` into one table, so it is genuinely a single statement and needs no explicit transaction |
| save | the 422 body shape | the existing Pydantic validation error on a `Rule` body, whose paths match `/scan` because the body shape matches (AC-3) |
| load | fields added to the contract after a row was written | Pydantic's own default when parsing the stored JSON, so no migration and no backfill |
| whether the feature is on | enabled or 501 | both of: a `DATABASE_URL` being configured, and the host checks passing. Either failing means 501 (AC-6, AC-7) |
| the host check itself | how it is reached | `live_mode_problems(argv, env)` is currently called only inside `Settings.from_env`, and only when `data_mode == "live"` (`settings.py:57`), at import. It is a pure function of `argv` and `env`, so the rules router calls it directly at import time and caches the single boolean. Not per request: nothing it reads can change while the process lives, so a per request call would be waste dressed as caution |
| the 501 response | its body | the existing `NotYetImplemented` helper, which produces "… is not implemented yet; it arrives with scope feature N (name)". That means the rules routes pass **feature 21** as the number. The wording is the house wording and is reused rather than invented, which also means `contracts/mocks/501.*.json` gains an entry, since those mocks are generated from the app |
| the connection string | the pooled endpoint | `DATABASE_URL`, set to Neon's pooled (PgBouncer) host for the API |
| the migration connection | a direct endpoint | `DATABASE_URL_DIRECT`, Neon's unpooled host, for Alembic only. Step 2 confirms whether the pooled endpoint can run migrations; if it can, this variable is dropped rather than kept for show |
| psycopg against a transaction pooler | any required setting | confirmed in step 2. A transaction mode pooler commonly requires prepared statements to be disabled (`prepare_threshold=0` in psycopg 3); the step verifies it rather than this spec asserting it |
| the web app's save control | shown or hidden | a 501 from `GET /api/v1/rules`, the same signal `/scan` already uses to mean "not available here" (AC-6) |

**Key invariants**

- Condition order is whatever the JSON array holds, which is the order the contract produced. Nothing reorders it because nothing decomposes it.
- The connection is opened inside the request and closed with it. Never a module level connection, because the function freezes between invocations and a socket does not reliably survive that (AC-9).
- Writes are impossible anywhere but your machine, enforced by configuration absence **and** a host check, not by one of them.
- The `Rule` contract is the only validator. The database stores and constrains identity (the unique name) and nothing about the rule's internals.

**Security model**

- No authentication, because there are no accounts until feature 22. That is why the surface does not exist in public (AC-7).
- Two redundant gates: no `DATABASE_URL` on the deployed function, and the existing D-5 style host check refusing to enable this on Lambda, in CI, or when not bound to loopback.
- `DATABASE_URL` is a credential. It lives in `.env` (gitignored, and gitleaks already runs in pre-commit) and is never set in the deployed function's environment.
- No personal data. A rule is indicator names and numbers.
- Reads are gated with writes. An unauthenticated public read would leak nothing dangerous but serves no purpose with no accounts.

**Configuration required**

- `DATABASE_URL`: Neon's pooled connection string. Local only. Absent means 501.
- `DATABASE_URL_DIRECT`: Neon's unpooled connection string, for Alembic. Local only, dropped if step 2 shows the pooled endpoint handles migrations.
- No change to the deployed function's environment at all.

**Critical test scenarios**

- Round trip: a rule with every operand shape (a price field with no `n`, a windowed indicator with a defaulted `n`, one with an explicit `n`, a non default `offset` and `mult`, and both a `value` and an `ind` right operand) saves and loads back equal, verifies **AC-2**.
- Restart: a saved rule is still there after the API process restarts, verifies **AC-1**.
- Duplicate: saving `Foo` then `foo` returns 409 and leaves one row, verifies **AC-4**.
- Malformed: an unknown indicator and an out of range `n` each return a 422 whose paths match `/scan`'s, verifies **AC-3**.
- Migration: an empty database reaches the current schema by running the chain, verifies **AC-5**.
- Disabled: with no `DATABASE_URL`, every endpoint answers 501 and the web app hides the control, verifies **AC-6**.
- Host gate: with a `DATABASE_URL` set but the Lambda environment marker present, the endpoints still answer 501, verifies **AC-7**.
- Delete from the browser: a `DELETE` preflight succeeds against the deployed CORS configuration, verifies **AC-8**.
- Idle connection: a request after Neon's idle suspend (about 5 minutes) succeeds. **Manual by nature**, since no automated test waits five minutes, so it is a documented local check rather than a CI test, verifies **AC-9**.
- No database: the whole suite runs and skips the database dependent cases, and `make ci` is green, verifies **AC-10**.

Two scenarios the earlier normalised design needed are gone, not merely untested: a hand written bad row cannot be rejected by a schema that stores JSON, and a cascade cannot break when there is no child table. Forward compatibility is also no longer a scenario, because Pydantic's defaults handle it on read with no migration involved.

## Build plan

Tracer Bullet. The thread is one rule saved and loaded back through the real API against the real database, before the list, the delete or any UI polish.

1. Add `psycopg` and `alembic` to the API's dependencies, and the enablement check (`DATABASE_URL` present **and** the host checks pass), satisfies **AC-6**, **AC-7**
2. Set up Alembic and the first migration: one table, written as plain SQL in `op.execute()`, with the `lower(name)` unique index. Confirm here whether migrations need Neon's direct endpoint, and whether `psycopg` needs `prepare_threshold=0` against the pooler, satisfies **AC-5**
3. `engine/src/engine/data/rules.py`: four plain SQL statements (insert, select all, select one, delete) with the connection opened per request; plus the `engine.api` use cases the router will call, satisfies **AC-1**, **AC-2**, **AC-9**
4. **One `contract-change` PR covering all three endpoints**, because CI fails on any `openapi.json` or client diff: `POST`, `GET` list and `DELETE` together, with the `Rule` request body, the 409 on a duplicate name, `DELETE` added to `allow_methods` in `main.py`, the feature 21 number on the 501 path, the regenerated `api-client`, updated mocks including the new 501 entry, and owner approval, satisfies **AC-3**, **AC-4**, **AC-8**, **AC-11**
5. Prove the thread: save a rule through the real API against the real database and load it back equal, satisfies **AC-2**
6. The skip when no database is configured, so `make ci` stays green on the D-4 pattern, satisfies **AC-10**
7. The builder's save control and its error display on 422, hidden when the list endpoint answers 501, satisfies **AC-3**, **AC-6**
8. The saved rules list in the builder, loading one back into the form from the list's own payload, satisfies **AC-2**
9. Round trip tests across every operand shape, satisfies **AC-2**

## Consequences

**Positive**:
- One table, five columns, four statements. The schema is small enough to read in one glance and there is no second definition of `Rule` to keep in step.
- Migrations as a reviewable chain in the repo, which is what feature 17 wanted and object storage could not give.
- Validation is not duplicated anywhere: the `Rule` contract that already guards `/scan` guards this, and because the body shape matches, the 422 paths and the form's existing handling come free.
- Forward compatibility costs nothing: a rule saved before the contract grows a field still parses, because Pydantic fills the new field on read. No migration, no backfill, no discipline to remember.
- No public write endpoint, so no abuse surface, no rate limit to tune, no row cap, no cleanup job.
- Features 22 and 23 inherit a working migration chain rather than starting one.

**Negative / tradeoffs**:
- The database knows nothing about a rule's internals, so a bad row inserted by hand would be stored and then fail on read. Acceptable because every write goes through the contract, and there is no second writer.
- Nothing can query across rules by indicator. Not needed today; a generated column or a `jsonb` index would answer it later without a redesign.
- The feature cannot be shown on the hosted demo until feature 22, so a reviewer sees it only locally or in a recording.
- A second vendor. Neon suspends a free database after about 5 minutes idle, so the first save after a quiet spell pays a resume of roughly half a second.
- Connecting per request costs a handshake every time. Milliseconds in region, and the price of not debugging stale sockets after a thaw.
- Two new dependencies in the API image, which grows it and lengthens cold start. Worth re measuring after step 1, since the deployed function never uses them.
- No request size limit, which is fine for a local only surface and becomes feature 22's problem the moment it is not.
- **Five of the eleven criteria are not checked by CI**, because the feature is deliberately off there and no Postgres runs in the pipeline. Your local run is their evidence, which is the pattern D-4 already set, and it is still weaker than a test that runs on every PR.
- `main.py`'s CORS `allow_methods` grows to include `DELETE`, which is the first time this project has needed a method beyond `GET` and `POST`.

**Neutral**:
- A contract change, so the generated client, the mocks and owner approval are in scope.
- Spec `0011` expected feature 21 to bring the SQL store, and it does; `0011`'s suggestion to start from Aurora DSQL was considered and not taken.
- Nothing about the market data store changes. Bars stay in object storage; this database holds only rules.
- The repository sits in `engine/data` beside the market store, which is where the documented layering puts I/O.

## Follow-up

- [ ] **Five criteria are evidenced by your local run, not by CI**, following D-4's precedent. That is a deliberate consequence of gating the feature off in CI, and it means `docs/qa/traceability.md` needs those rows marked the way D-4's is, with your local run as the evidence. Worth confirming with QA, who own that file.
- [ ] If the project keeps ADRs as a separate numbered series (`rule.py` cites `ADR-013`), adding Neon needs an entry there pointing at this spec, since root `AGENTS.md`'s never list bars adding a service without one.
- [ ] **Feature 22 must add a request body limit** when it opens this surface publicly. It is deliberately absent here because the surface is local only and `Rule`'s own bounds make a valid body tiny; that reasoning stops applying the moment anyone else can post.
- [ ] Feature 22 adds accounts, and with them the ownership column, per account name uniqueness and row level access. The `lower(name)` unique constraint here becomes unique per owner then, which is a migration worth planning in 22's spec.
- [ ] Feature 23 stores backtest runs. It should extend this migration chain and reuse this connection approach rather than introducing a second one, and it should take the dataset identity from spec `0013`'s `Assumptions.data_end` rather than adding its own.
- [ ] Spec `0011`'s follow up pointing feature 21 at Aurora DSQL is resolved in favour of Neon, and should be read alongside this decision rather than as a live recommendation.
- [ ] Measure the cold start cost of the two new dependencies after step 1. If it is material, the rules router can import them lazily so the deployed function does not pay for code it never runs.
- [ ] `psycopg` and Alembic conventions are not yet in any `AGENTS.md`. They touch `engine/data` and `services/api`, so those two nested files are their home. `/sync` owns that edit.
- [ ] The official Neon MCP server (`neondatabase/mcp-server-neon`) would let the build read the real schema and run real queries instead of inferring them. Connecting it is a change to your own MCP settings, which I cannot make for you: it is added with `claude mcp add`, and its tools then appear automatically. Worth having before build step 2, which is the step that verifies the pooling and psycopg questions against the real database.
- [ ] `neon-postgres` and `postgresql-table-design` are installed but not yet named in any `AGENTS.md`. They are area specific, so `services/api/AGENTS.md` and `engine/AGENTS.md` are their home. `/sync` owns that edit. A skill for SQLAlchemy with Alembic was found and declined, which is now moot since there are no SQLAlchemy models.

## Rationale

Reasoning, the options weighed, and the references: see [rationale.md](rationale.md).
