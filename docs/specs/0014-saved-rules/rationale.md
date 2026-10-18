# 0014. Rationale: saved rules

Reasoning, options and references for [index.md](index.md).

## Context

> ⚠️ Premise note: this feature's data need is a name and a rule, and the project already has a validator for the rule, a serialisation for it (the `?r=` link codec) and an object store. The smallest thing that satisfies every line of the scope's done when is one JSON object per rule in the bucket feature 17 already created. A relational database with a normalised schema and a migration tool is a larger answer than this feature requires, and it arrives one feature early: feature 22 is what genuinely needs rows, constraints and ownership. The engineer chose the database knowingly, and the reasons are good ones (it is decided once, features 22 and 23 inherit it, and a real schema is the better thing to show), but the record should say plainly that the store is sized for what comes next rather than for what this feature needs.

Today a rule exists in three places, none of them durable: in the builder's form state, in a `?r=` link you can copy, and inside a scan or backtest request. Nothing survives a refresh unless you kept the link. The scope asks for saving under a name, listing, loading back and deleting, which is the first write path in the project.

The forces at play:

- **No accounts yet.** Feature 22 is where identity arrives. Until then any write endpoint on the hosted demo is unauthenticated, which is the whole reason the write surface is gated to your own machine rather than capped and rate limited.
- **The rule is already a validated contract.** `Rule` is frozen contract v1: a bounded `name`, 1 to 8 ordered `Condition`s, and `IndOperand`'s own validator deciding per indicator whether `n` is required, defaulted or disallowed. Any storage design that re-implements that validation is duplicating work that is already correct.
- **Order matters and rows do not have it.** `Rule.conditions` is a list. Normalised rows are a set, so the ordering has to be made explicit or the rule comes back scrambled.
- **`right` is a discriminated union.** It is either an indicator operand or a bare number, which a single table can hold only with nullable columns and a check constraint.
- **The function freezes.** Lambda suspends the execution environment between invocations, so anything connection oriented has to assume a socket does not survive to the next request.
- **Field growth is an explicit requirement.** The scope's done when asks that a saved rule keep working after the rule format grows a field, which is a direct constraint on the schema choice.
- **The 8 KB ceiling already exists** in the link codec, so the size limit has a precedent to match rather than a number to invent.
- **$0 and no operator.** The database must be free at rest and must not need anybody watching it.

## Options considered

### Option 1: one JSON object per rule in the existing bucket

A `rules/` prefix in the S3 bucket feature 17 created. One object per saved rule, the name as the key, the `Rule` JSON as the body.

**Pros**:
- Nothing new to run: no service, no driver, no migration tool, no connection in a freezing function.
- Field growth is free, which is the one requirement the scope states explicitly.
- Validation stays exactly where it already is, so the 422 comes from the existing contract with no new code.
- List, load and delete are one call each.

**Cons**:
- No transaction, so two tabs saving the same name is last write wins rather than a 409.
- No query beyond prefix listing, so nothing can ever ask which rules use a given indicator.
- Feature 22's password hashes do not belong in object storage, so a relational store is coming regardless, and the rule blobs would move then.
- "Where is your schema" is a harder question to answer well than it should be, on a project built to be read.

### Option 2: Aurora DSQL

AWS's distributed SQL, with a perpetual free allowance and availability in `ap-southeast-1`.

**Pros**:
- Free in perpetuity at this scale with no idle pause at all, so the first request after a quiet month is not slower than any other.
- Already inside AWS, beside the function, so one vendor and one set of credentials.
- Horizontally scalable, which is irrelevant here but costs nothing to have.

**Cons**:
- Sharper edges than Postgres: no sequences, optimistic concurrency control rather than locking, and a materially smaller body of documentation and community answers to lean on when something is strange.
- Less recognisable to a reader than Postgres, so the thing being shown needs more explaining.
- Its differences would have to be learned at the same time as the project's first database work.

### Option 3: Neon Postgres, normalised, Alembic, local only writes (chosen)

Managed Postgres on a free tier, two tables with real constraints, a migration chain, connecting per request over the pooled endpoint, and the whole surface disabled anywhere but your machine.

**Pros**:
- Plain Postgres: the most familiar, best documented thing to build and to read, and the migration chain is the reviewable artifact feature 17 wanted and could not have.
- Real constraints doing real work: a unique name gives the 409, a foreign key with cascade makes orphan conditions impossible, and a check constraint keeps the operand discriminator honest.
- Decided once. Features 22 and 23 inherit a working schema, a migration chain and a connection approach rather than each starting one.
- Local only writes mean no public abuse surface at all, so no caps, no rate limiting and no cleanup job to design.

**Cons**:
- The `Rule` shape now lives in three places: Pydantic, the SQLAlchemy model and the DDL.
- Every new field on a rule becomes a migration, and it must be nullable with a default or old rows break.
- A second vendor, which suspends after about 5 minutes idle, so the first save after a quiet spell pays a resume.
- Three new dependencies in an image whose cold start is a measured criterion.
- The feature cannot be demonstrated on the public site until feature 22 exists.

### Option 4: the database, but with a JSON column for the rule

Neon Postgres as above, with one `rules` table holding the `Rule` as `jsonb` rather than normalised conditions.

**Pros**:
- Field growth needs no migration, satisfying the scope's requirement outright.
- One table, one insert, one read, and the round trip is trivially exact because nothing is decomposed.
- Still gets the unique name, the timestamps and the migration chain.

**Cons**:
- The database stores a blob it cannot reason about, so the constraints that make option 3 worth choosing (the operand discriminator, condition ordering) have nowhere to live.
- A schema that is one opaque column is a weaker thing to show than one that models the domain.

## Rationale

The engineer chose option 3 over my recommendation of option 1, and the reasoning that decides it is not really about this feature. Feature 22 needs accounts, which means users, password hashes, ownership and row level access; feature 23 needs run rows with status transitions. Both need a relational store with constraints, so the question is not whether this project gets a database but whether it gets one now, with the feature whose data is simplest, or later, with the feature whose data is most sensitive. Doing it now means the first database work in the project is a name and a list of conditions rather than credential storage, and it means features 22 and 23 inherit a migration chain that already works. That is a better sequence than it first appears, and it is worth more than the object store's smaller diff.

Neon over Aurora DSQL was the engineer's call and it is defensible on the same grounds: the project's first database should be the one with the most documentation behind it, not the one with the most interesting consistency model. Neon's 5 minute idle suspend costs roughly half a second on the first request after a quiet spell, which for a local only feature nobody is benchmarking is immaterial. DSQL's perpetual free allowance and absence of idle pause are genuinely better properties, and if feature 22 or 23 ever makes idle resume matter, that is the moment to revisit rather than now.

The normalised schema was also the engineer's choice over my recommendation of a JSON column, and it conflicts with the scope's own done when, which asks that a saved rule keep working after the rule format grows a field. A JSON column gives that for nothing; normalised columns give it only under a discipline. Rather than note the conflict and leave it, this spec resolves it: every migration that adds a field adds it nullable with a default, and the read path falls back to the `Rule` contract's own defaults. That makes AC-6 true and testable under the chosen schema, which is what the criterion actually asks for. The price, stated plainly in Consequences, is that the rule's shape now exists in three places and every field is a migration.

**Five corrections from a cross check, recorded because each was a confident claim the code contradicted.** They are worth keeping in the record because four of them would have produced a feature that fails its own round trip criterion.

- **The request body is the `Rule` itself, not `{name, rule}`.** The first draft invented a distinction between the name you file a rule under and the rule's own `name`, which `Rule` requires. That dropped `rule.name` on the way in, so AC-2's field for field round trip could not hold, and it also shifted every validation error path from `body.conditions.0...` to `body.rule.conditions.0...`, breaking the existing `fieldErrorsFrom422` mapping. One body shape fixes both.
- **The right operand's columns must be constrained exactly like the left's.** The first draft left `right_offset` and `right_mult` nullable with no default while `IndOperand` requires both, and its check constraint covered only `right_ind` against `right_value`. The API could therefore have written a row it could not read back.
- **`n` is stored already defaulted.** `IndOperand`'s validator fills `n` from `n_default` before a rule exists, so a windowed indicator's `n` is always a number and only a price field's is absent. The draft's "null in the column, then the contract decides" was true only for price fields. Storing what the contract produced is also the better behaviour: a later change to `n_default` must not silently turn a saved rule into a different rule.
- **The schema did not constrain what the draft claimed.** `op`, `right_kind`, the offsets, the multipliers and `n` were unconstrained text and numbers while `Op` and `IndName` are closed sets, so a hand written `INSERT` of `op = 'foo'` would store happily and fail on load. The constraints are now explicit, with the deliberate exception of the indicator names, which stay `text` because the registry grows with the contract and an enum would mean a migration per indicator.
- **Nothing in FastAPI or Starlette produces a 413.** The promised request size limit would have needed custom middleware handling a missing `Content-Length`, and it was unnecessary anyway: `Rule` bounds a valid body to 8 conditions of bounded fields plus a 40 character name. It is dropped, with the reasoning recorded, and handed to feature 22 as a requirement for the moment the surface stops being local only.

**And one layering correction, which took two passes to get right.** The draft put the repository in `services/api`. Root `AGENTS.md` places Infrastructure at `engine/{data,synthetic}`, so persistence belongs beside the market store in `engine/data`. That fixed half of it: `services/api/AGENTS.md:32` says "Routers call `engine.api` use cases only", so the routes cannot call the repository either, and this feature needs thin use cases in `engine.api` between them. The boundary test bars FastAPI, Starlette and uvicorn from the engine, and `psycopg` and SQLAlchemy are none of those, so the documented architecture and this feature agree once all three layers are in place.

**A second review round found six more, four of which would have stopped the build.** `main.py:34` sets `allow_methods=["GET", "POST"]`, so the `DELETE` endpoint's browser preflight would have failed with the route working perfectly in isolation. CI has no Postgres at all, so six criteria had nowhere to run while AC-9 deliberately disables the feature there; that is resolved by following D-4's existing precedent, where a test skips when its data source is absent and the owner's local run is the evidence, which `docs/qa/traceability.md` already records as acceptable for exactly this situation. Build steps 4 to 6 could not have been green separately, because CI fails on any `openapi.json` or generated client diff, so every endpoint has to land in one `contract-change` PR rather than routes first and the client after. And "deleted by the database" needed `passive_deletes=True` as well as `ondelete="CASCADE"`, or SQLAlchemy would quietly issue its own child deletes and the criterion would pass while being false.

Two smaller ones. The 501 path reuses `NotYetImplemented`, whose body names a scope feature number, so the rules routes pass feature 21 and the generated 501 mocks gain an entry; the draft spoke of reusing the 501 "signal" without noticing it carries required content. And `live_mode_problems` is currently called only inside `Settings.from_env` when the data mode is live, so the draft's per request gate had no mechanism; it is a pure function of `argv` and `env`, neither of which changes while the process lives, so the router calls it once at import and caches the result.

Two decisions I made rather than asked, with full design context. **Condition order is an explicit `position` column**, unique per rule, because a set of rows has no order and reading conditions back in primary key order would be a bug that appears only sometimes, which is the worst kind. **The connection is opened inside the request**, not at import, because the execution environment freezes between invocations and a module level connection is the standard way to get failures that only happen after an idle period; the handshake costs milliseconds in region, and the runner up, a module level connection with a reconnect path, buys that back at the cost of a retry branch on every query.

## References

**Project sources** (verifiable, in this repo):
- `engine/src/engine/contracts/rule.py`: `Rule` (a bounded `Name` plus 1 to 8 `Condition`s), `Condition` (`left`, `op`, `right`), `IndOperand` with its per indicator `n` validator and the `offset` and `mult` bounds, and `ValueOperand`. This is the shape the schema normalises and the validator the 422 comes from.
- `apps/web/src/features/rule-builder/url-codec.ts`: `MAX_ENCODED_LENGTH` of 8 KB, the existing size ceiling AC-4 matches, and `normaliseRule` as the precedent for treating a stored rule as untrusted input.
- `apps/web/src/lib`: `fieldErrorsFrom422` and `errorAt`, the existing 422 handling the save form reuses.
- `services/api/src/api/settings.py`: `live_mode_problems()`, the host check (not Lambda, not CI, bound to loopback) that AC-9 reuses to gate writes.
- `services/api/src/api/routes/scan.py` and `state.py`: the established meaning of 501 as "this is not available here", which the disabled rules endpoints reuse rather than inventing a new signal.
- Spec `0008`: the rule builder and the frozen rule contract this feature saves.
- Spec `0011`: the market data store, and its follow up expecting feature 21 to bring SQL, which this spec answers.
- `AGENTS.md` and doc 02 §15.6: the `contract-change` process for new endpoints, the Clean Architecture layering that keeps database access in the presentation and infrastructure layers rather than in `engine`, and the gitleaks pre-commit hook that covers `DATABASE_URL` in `.env`.
- `docs/01-market-research-and-product-spec.md`: D-5's host rule, the model for gating a capability to the owner's machine.

**Practices & standards**:
- One validator, at the boundary: the contract validates, the schema constrains, neither re-implements the other.
- Explicit ordering for a stored list, never insertion order or key order.
- Additive migrations only: a new column is nullable with a default, so existing rows stay valid.
- Connection per invocation in a freezing runtime, rather than a cached connection with a reconnect path.
- Defence in depth on a dangerous default: absent configuration and a host check, either of which alone would disable the write surface.
- Foreign keys with cascade, so referential cleanup is the database's job.
- Pooled endpoint for the application, direct endpoint for migrations, where the provider distinguishes them.

**Measured in this repo**:
- `IndOperand`'s `_check_n` validator (`engine/src/engine/contracts/rule.py:28` onward) fills `n` from `spec.n_default` when omitted and rejects an `n` on a non windowed indicator, which is what decides how `n` is stored.
- `Name` is bounded to 1 to 40 characters after strip (`engine/src/engine/contracts/_errors.py`), which is what bounds the `name` column.
- `Rule` requires `name` (`rule.py:76`), which is what makes a separate filing name a round trip bug rather than a convenience.
- Root `AGENTS.md` places Infrastructure at `engine/{data,synthetic}`, and `engine/tests/test_engine_boundary.py` bars only FastAPI, Starlette and uvicorn, which together settle where the repository lives.
- No 413, `max_body` or `content-length` handling exists anywhere in `services/api/src`, which is why the promised request size limit was removed rather than specified.

**Links** (web verified only):
- Pending the capped landscape check for this spec: Neon's pooled connection string form and its pooling mode, whether `psycopg` needs `prepare_threshold=0` against a transaction pooler, whether Alembic needs an unpooled connection, and Neon's region list. All four are verified in build step 2 rather than asserted here. Cited by name until confirmed, and no URL is written here that was not fetched.
