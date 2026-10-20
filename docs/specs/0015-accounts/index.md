# 0015. Hand roll accounts on the existing Neon database, with a signed cookie that only your machine can issue

**Date**: 2026-10-20
**Status**: In Progress

## Summary

You can register, sign in, sign out and delete your account, and the rules you save belong to you rather than to the database at large. It is built by hand on the Neon Postgres and Alembic migration chain spec 0014 already set up, with no third vendor: passwords are hashed with Argon2id (a slow, memory hungry hash designed so that stealing the database does not hand over the passwords), and a signed cookie carries who you are. Like saved rules, the whole surface exists only on your own machine: the deployed demo answers 501 and never shows a login, so there is no public sign in to attack and no real person's data to lose. The thing to watch while building is the cookie, because the API binds `127.0.0.1` while the web app serves from `localhost`, and a browser treats those as different sites and quietly declines to send the cookie at all.

## Requirements

**User stories**:
- As the owner, I want to register and sign in, so the rules I save are mine rather than anonymous rows.
- As the owner, I want to stay signed in after I restart the API, so a day of work does not start with a login.
- As the owner, I want a second account to be unable to see or delete my rules, so the isolation is real and not merely intended.
- As the owner, I want my password unreadable everywhere, including in logs and error bodies, so a copied database or a pasted log leaks nothing.
- As the owner, I want no login at all on the public demo, so there is nothing out there to attack.
- As the owner, I want to delete my account and have my rules go with it, so nothing of mine is left behind.

**Acceptance criteria** (the contract, each criterion is IDed and independently checkable):

- **AC-1**: Register, then sign in, then sign out works end to end against the real API and the real database. A signed in browser is still signed in after the API process restarts, because the signing key comes from the environment and is never generated at startup.
- **AC-2**: A password never exists in readable form anywhere: the database holds only an Argon2id hash, no log line or error body contains the password or the hash, and the generated OpenAPI schema carries no password example. **Including the validation path**: FastAPI's default 422 body echoes the rejected input, so a password that fails the length rule must not come back in the response.
- **AC-3**: One account cannot read, load or delete another account's rules. The rules list returns only the signed in account's rows, and deleting another account's rule id returns 404 rather than 403, so the response does not confirm that the id exists. **In the browser as well as in the database**: signing out and signing in as a second account shows the second account's rules, never the first account's left in a client cache.
- **AC-4**: On the deployed API every auth endpoint answers 501, and the rules endpoints keep answering 501. The `/sign-in` and `/register` pages still ship in the static export, but they show the house "not available here" notice and the navigation never links to them.
- **AC-5**: Setting `AUTH_SECRET` and `DATABASE_URL` on the deployed function does not open the feature. The same host checks that gate live data mode (D-5) and saved rules gate this too, so Lambda and CI refuse regardless of configuration.
- **AC-6**: Registering an email that already exists is a 409: not a second account, and not a silent sign in. Uniqueness ignores case, so `You@x.com` and `you@x.com` collide, matching how spec 0014 made rule names collide.
- **AC-7**: A wrong email and a wrong password produce an identical 401 body, so the response never reveals whether an account exists.
- **AC-8**: A request carrying an expired token, a malformed token, a token signed with the wrong key, or a valid token for an account that no longer exists receives a 401 and a cleared cookie, never a 500.
- **AC-9**: Deleting an account deletes that account's rules, enforced by the database rather than by application code, and the browser ends up signed out.
- **AC-10**: The cookie is `httpOnly` and `SameSite=Lax`, and the browser actually sends it on the cross origin request from the web app to the API. Checked in a real browser, because this is the part that fails silently.
- **AC-11**: Migrations run as a reviewable, versioned chain extending spec 0014's: a fresh database reaches the current schema by running them in order, and the rules already sitting in your database survive the change with their owner set.
- **AC-12**: Signed out locally, the saved rules panel shows an empty state linking to `/sign-in`, rather than looking broken, erroring, or hiding itself as it does on the demo.
- **AC-13**: Every scenario that needs a real Postgres skips cleanly when none is configured, so `make ci` stays green, following the precedent D-4 set and spec 0014's AC-10 repeated. Your local run is the evidence for those criteria.
- **AC-14**: The contract change goes through the project's `contract-change` process: the regenerated `api-client`, updated mocks including the new 501 entries, and owner approval.
- **AC-15**: Scanning, backtesting, the exit lab and the meta endpoint keep working with no account at all, signed in or signed out, locally and on the deployed demo.

## Decision

**Chosen option**: Option 4: hand rolled on the existing Neon database, with a signed token in an `httpOnly` cookie and no sessions table.

Accounts are two tables and five endpoints in the project's own code, on the database and migration chain spec 0014 already established, with Argon2id for hashing and PyJWT for the cookie's token. No third vendor, no SQLAlchemy models, and the surface is gated off anywhere but your own machine by the same two checks that gate saved rules, now three (basis: spec 0014, the two gate pattern).

**Implementation skills**: `fastapi` (`fastapi/fastapi`, `.agents/skills/fastapi/`) · `pydantic` (`.agents/skills/pydantic/`) · `neon-postgres` (`neondatabase/agent-skills`, `.agents/skills/neon-postgres/`) · `postgresql-table-design` (`wshobson/agents`, `.agents/skills/postgresql-table-design/`) · `python-testing-patterns` (`wshobson/agents`, `.claude/skills/python-testing-patterns/`) · `shadcn` (`shadcn-ui/ui`, `.agents/skills/shadcn/`) · `nextjs-app-router-patterns` (`wshobson/agents`, `.claude/skills/nextjs-app-router-patterns/`)

## Rationale

See [rationale.md](rationale.md) for the options weighed and the reasoning, including why the recommended option was not the one chosen and what that costs.

## Feature design

**Where the code lives**, following the three layers spec 0014 settled (basis: `AGENTS.md`, the Clean Architecture layout; spec 0014, the repository placement):

- the repository in **`engine/src/engine/data/accounts.py`**, beside `rules.py` and the market store, plain `psycopg` and plain SQL, no SQLAlchemy models;
- the use cases in **`engine.api`** (`register`, `sign_in`, `account_by_id`, `delete_account`), thin orchestrators over contract models;
- the router in **`services/api/src/api/routes/auth.py`**, calling only those use cases, plus a FastAPI dependency that resolves the signed in account for the rules router.

The token encode and decode helpers are presentation concerns, not domain ones, so they live in `services/api`, not in the engine. The engine never learns what a cookie is. `engine/tests/test_engine_boundary.py` bars FastAPI, Starlette and uvicorn from the engine; `argon2-cffi` is none of those, so hashing may live in the repository, while PyJWT stays on the API side.

**Data model sketch**

`accounts` (new):

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | uuid | no | primary key, a `uuid4()` from the application before insert, as spec 0014 does for a rule id |
| `email` | varchar(254) | no | the identifier, never mailed to. Stored as typed, unique on `lower(email)`, so case does not create a second account (AC-6) |
| `password_hash` | text | no | the Argon2id PHC string, which carries its own salt and parameters, so there is no salt column and no parameter for you to choose (AC-2) |
| `created_at` | timestamptz | no | default `now()`, the database's clock |

No `updated_at`: changing your email or password is out of scope, so nothing can ever update the row. No sessions table, by the chosen option.

`rules` (changed, from spec 0014):

| Change | Detail |
|---|---|
| add `account_id` | uuid, references `accounts(id)` **ON DELETE CASCADE**, constraint named `rules_account_id_fkey`. Added nullable in migration `0002` so it cannot fail on rows that already exist, then flipped to `NOT NULL` in `0003` after the backfill (AC-9, AC-11) |
| drop | the unique index on `lower(name)`, named `rules_name_lower_idx` by migration `0001` |
| add | a unique index on `(account_id, lower(name))`, named `rules_account_name_lower_idx`, so two accounts may each keep a rule called `Foo` while one account may not keep two |

**Relationship**: `accounts` 1:N `rules`, cascading on delete. One relationship, no join table, nothing else in the database gains an owner.

**The migration runs in three steps, and the ordering is load bearing**

A `NOT NULL` column cannot be added to a table that already holds rows, so the owner column arrives nullable and is tightened afterwards. The hazard is that Alembic wraps a whole `upgrade head` in **one transaction** by default: `0003` failing on orphan rows would roll `0002` back with it, leaving no `accounts` table to register into, and therefore no way to perform the backfill that `0003` is waiting for. The upgrade would be stuck with no route forward. Three things prevent that:

- `transaction_per_migration = True` in the Alembic configuration, so a failing `0003` leaves `0002` applied;
- `make migrate` stops at `0002` while any orphan rules remain, rather than going to `head` as spec 0014's target does;
- `0003` checks for `account_id IS NULL` rows first and raises a message naming `make claim-rules`, so the failure explains itself instead of surfacing as a constraint violation.

**The backfill is a make target, not a hand written statement.** `make claim-rules EMAIL=you@example.com` sets `account_id` on every orphan row to that account's id, and **fails unless exactly one account matches** that email, so it cannot silently pick an account when two exist. It is rerunnable: with no orphan rows it reports that and changes nothing.

**`downgrade` is supported for `0003` only.** Downgrading `0002` would re-create the global `lower(name)` unique index, which fails the moment two accounts have each saved a rule under the same name, so `0002`'s downgrade raises a message saying so rather than failing halfway through. Forward is the only route once two accounts exist, which is acceptable for a local database you can recreate.

On a fresh, empty database all three steps run straight through in one command: `0003` finds zero rows and succeeds immediately.

**State transitions**

A browser is either signed out or signed in, and the only states worth naming are the account's: `registered` then `deleted`, with no intermediate state because there is no email verification, no lockout and no password reset. The token has its own lifetime inside the signed in state: valid, then expired, and an expired token is treated exactly as signed out (AC-8).

**API surface**

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/api/v1/auth/register` | POST | `email:str` (req), `password:str` (req) | `id`, `email`, and the cookie set | none | 409 email taken, 422 invalid, 501 disabled |
| `/api/v1/auth/login` | POST | `email:str` (req), `password:str` (req) | `id`, `email`, and the cookie set | none | 401 bad credentials, 422 invalid, 501 disabled |
| `/api/v1/auth/logout` | POST | none | no body, the cookie cleared | none needed | 501 disabled |
| `/api/v1/auth/me` | GET | none | `id`, `email` | cookie | 401 signed out, 501 disabled |
| `/api/v1/auth/account` | DELETE | none | no body, the cookie cleared | cookie | 401 signed out, 501 disabled |
| `/api/v1/rules` | POST | `Rule` | `id`, `name`, `created_at` | cookie | 401, 409 duplicate name for this account, 422, 501 |
| `/api/v1/rules` | GET | none | this account's rules only | cookie | 401, 501 |
| `/api/v1/rules/{id}` | DELETE | `id` path | no body | cookie | 401, 404 (also when it is another account's rule), 501 |

Five auth endpoints, not six: there is no refresh endpoint, because the token is long lived and nothing rotates. `logout` requires no valid token on purpose, so a browser holding an expired or corrupt cookie can still clear it rather than being stuck signed in to nothing.

Three new response models and three rules endpoints changing their auth, so this is a **contract change**: a regenerated `packages/api-client`, updated mocks, and owner approval (AC-14).

**Value sourcing**

| Action | Value produced or displayed | Source |
|---|---|---|
| register | the account `id` | a `uuid.uuid4()` in the repository before insert, so the id exists before the row, as spec 0014 does |
| register | `created_at` | Postgres `now()` as a column default, so the database's clock is the only clock |
| register | the stored password | `argon2.PasswordHasher().hash(password)`, whose output PHC string embeds the salt and the cost parameters, so there is no salt column and no parameter choice of your own (AC-2) |
| register | the 409 on a taken email | the unique index on `lower(email)` raising, caught and translated, so two concurrent registrations cannot both win (AC-6) |
| register, login | the email as compared | `lower(email)` on both sides, matching how spec 0014 compares a rule name |
| register, login | the session token | `jwt.encode` with HS256 over the claims `sub` (the account id) and `exp` |
| register, login | the signing key | `AUTH_SECRET` read from the environment. Never generated at startup, which is exactly what makes a restart keep you signed in (AC-1) |
| register, login | the token expiry | 30 days from the server clock at sign in, carried in the `exp` claim and mirrored in the cookie's `Max-Age` |
| register, login | the cookie attributes | `httpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age` matching `exp`. `Secure` is set only when the request arrived over https, so the loopback http origin still works (AC-10) |
| login | the 401 body on a wrong email | one shared message, byte for byte identical to the wrong password case, so neither reveals whether the account exists (AC-7) |
| login | the comparison on a missing account | `PasswordHasher().verify` against a fixed dummy hash, so a missing account costs the same time as a wrong password and the timing does not leak either |
| any gated request | who the caller is | the `sub` claim, then a primary key read of `accounts` to confirm the row still exists. The read is the decision: without it, a deleted account keeps working for up to 30 days (AC-8) |
| save a rule | the owner written on the row | the authenticated account id from that lookup, never a field in the request body, so a caller cannot write a row onto another account |
| list rules | which rows come back | `WHERE account_id = <the authenticated id>`, so isolation is a condition on the statement rather than a filter applied afterwards (AC-3) |
| delete a rule | the 404 on another account's id | the same `WHERE account_id` on the delete, so a row that is not yours matches nothing and is indistinguishable from a row that does not exist (AC-3) |
| delete an account | what happens to its rules | `ON DELETE CASCADE` on `rules.account_id`, so the database enforces it in the same statement and no code path can forget (AC-9) |
| validate the email | the rule applied | length 1 to 254 after strip, and nothing more. It is an identifier that is never mailed to, so pulling in `email-validator` for a format check buys nothing here |
| validate the password | the rule applied | minimum 12 characters, maximum 128, no composition rules and no rotation (basis: NIST SP 800-63B, length over composition) |
| whether the feature is on | enabled, or 501 | all three of: `DATABASE_URL` present, `AUTH_SECRET` present, and the host checks passing. Any one failing means 501 (AC-4, AC-5) |
| the 501 body | its text | the existing `NotYetImplemented` helper, passed **feature 22**, so the wording stays the house wording and `contracts/mocks/501.*.json` gains entries |
| the web app's sign in affordance | shown or hidden | a 501 from `GET /api/v1/auth/me`, the same signal saved rules already uses to mean "not available here" (AC-4) |
| the web app's signed in state | your email in the header | the `email` from `GET /api/v1/auth/me`, cached by TanStack Query, so there is one source and no duplicate client state |
| register, login | the 422 body when the password is too short | a `RequestValidationError` handler on the auth routes that drops `input` and `ctx` from every error entry. FastAPI's default includes `input`, which is the rejected password itself, so without this handler AC-2 fails on its own validation path |
| register, login | the success status | 201 for register (a row was created), 200 for login. `logout` and account delete are 204 with no body |
| register, login | the cookie's name | `session`. No `__Host-` prefix, because that prefix requires `Secure` and the local origin is plain http |
| register, login | the `Secure` attribute | never set. The only origin that can reach this is http loopback, so a conditional is more code than the thing it guards. This has to change if the surface is ever served over https |
| register, login while already signed in | what happens to the old cookie | overwritten. There is nothing to reconcile, since no server state is tied to the previous token |
| any gated request | the decode settings | `algorithms=["HS256"]` pinned explicitly so the token's own header cannot choose, and `options={"require": ["exp", "sub"]}` so a token missing either claim is rejected rather than read with a default |
| any gated request | a `sub` that is not a UUID | a 401. It cannot be a database lookup, so it is treated as a bad token rather than a missing account |
| any 401 | the cookie | a `Set-Cookie` deletion with the same `Path` and attributes, sent whether or not a cookie arrived. Harmless when none was sent, and it stops a browser retrying a dead token forever |
| any gated request | the order the gates run in | the enabled check first, then the token, then the account lookup. So a signed out request on the deployed demo gets 501, not 401, which is what AC-4 asks for |
| any gated request | the database connection | one connection opened in the FastAPI dependency and shared by the account lookup and the rules statement, so a request is one connection rather than two |
| any gated request | a database or Neon failure | 503, not 500. Neon suspends when idle, so the first request after a quiet spell can genuinely fail, and that is a retry rather than a fault |
| login | the dummy hash for a missing account | built once at import by hashing a throwaway value with the same `PasswordHasher` instance, so its parameters match real hashes. Never a string literal, which would drift from the parameters and change the timing |
| login | which exceptions become the 401 | `VerifyMismatchError` and `InvalidHashError` both fold into the same 401 body. `check_needs_rehash` is deliberately ignored: there is one parameter set and no rehash path |
| register | the email as stored | the stripped value. Strip first, then check the length, then store, so what is stored is what the uniqueness index compares |
| register, login | the password as received | never stripped, because leading and trailing spaces are legitimate password characters |
| register | how the length limits are counted | in characters, not bytes. Argon2id has no 72 byte input limit, so the bcrypt style truncation trap does not apply here |
| any request | `AUTH_SECRET` shorter than 32 characters | treated as absent, so the feature answers 501. A short key is worse than no feature, and silently accepting one would be the quiet failure this whole gate exists to prevent |
| the deployed API | whether CORS sends credentials | `allow_credentials` is set only when auth is enabled. Unconditionally would make every origin matching `ALLOWED_ORIGIN_REGEX`, which is how Vercel previews are allowed, a credentialed origin on the public API |
| the web app | any status other than 200, 401 or 501 | a retry notice, reusing the existing `ErrorState`. So a 503 from a sleeping database reads as "try again" rather than as being signed out |
| the web app | the cache on sign in, sign out and account delete | `queryClient.clear()` on all three, so no account's rows survive into another account's session (AC-3) |
| the web app | a 401 arriving mid session | clear the `me` cache and render the signed out state, rather than leaving a header that claims you are signed in |
| the builder's save control | shown, hidden or disabled | hidden on a 501, exactly as spec 0014 does. On a 401 it is shown but disabled with a link to `/sign-in`, because locally the feature exists and you are merely signed out |
| `/sign-in` | where you land after signing in | back to `/`. There is no server to hold a return path, so there is no redirect target to preserve |

**Key invariants**

- The authenticated account is derived from the token plus a live row read. It is never taken from a request body, a query parameter or a header the caller controls.
- A rule's owner is written by the server. There is no code path in which the client names the owner.
- Rule name uniqueness is per account, so two accounts never collide with each other.
- `AUTH_SECRET` is never generated, never defaulted and never logged. Its absence turns the feature off rather than making it insecure.
- The plaintext password is hashed inside the request handler and is never assigned to anything that outlives the call, never logged, and never returned.
- Once migration `0003` lands, every rule row has an owner. The nullable window exists only between `0002` and `0003`.
- There is no sessions table, so a token cannot be revoked before it expires. Deletion takes effect because the account row disappears, which is the whole reason the per request lookup exists.
- The enabled check runs before the token check, always. A disabled surface answers 501 whatever the caller sends, so configuration state never leaks through an auth error.
- No account's data outlives its session in the browser. The client cache is cleared on sign in, sign out and account deletion, so isolation does not depend on a component happening to refetch.

**Security model**

- One role, no hierarchy. You own your rows, there is no administrator, and nothing is shared or public.
- Reads are gated alongside writes. There is nothing dangerous in a rule, but an open read would serve no purpose once rows have owners.
- Three independent gates, not one: no `DATABASE_URL` on the deployed function, no `AUTH_SECRET` on it either, and the D-5 style host check refusing to enable this on Lambda, in CI, or when not bound to loopback (AC-5) (basis: spec 0014, two gates on purpose).
- `AUTH_SECRET` and `DATABASE_URL` are credentials. They live in `.env`, which is gitignored and which gitleaks already scans in pre-commit, and neither is ever set in the deployed function's environment.
- Compliance scope: none. The only personal data is one email address, which is never mailed to, plus one password hash, both yours, on your machine. No payments, no health data, no third party data, so no regulatory regime applies and no audit log is warranted.
- **No rate limit on sign in, and no request body limit**, stated plainly because the project's own standard is to rate limit any public endpoint. These endpoints are not public: they do not exist in public, enforced by three gates rather than by a policy. The moment any of them is reachable by someone else, both become required, which Follow-up records against whichever feature opens them (basis: spec 0014's deferred body limit, same reasoning, same debt).
- Account enumeration is closed on sign in by the identical 401 body and the constant time dummy verify. It is deliberately left open on register, where a 409 does reveal that an email is taken, because the alternative is to accept a registration and say nothing, and that is a worse experience for a single user system with no email to confirm through (basis: OWASP authentication guidance, on the enumeration tradeoff at registration).

**Configuration required**

- `AUTH_SECRET`: the HS256 key signing the session cookie. Generate it with `openssl rand -hex 32`. It must be stable across restarts or AC-1 fails, so it is never generated at startup and never defaulted. Local only. **Absent, or shorter than 32 characters, means the feature answers 501**, because a weak key is worse than no feature. It joins the `Settings` dataclass and `.env.example` like every other variable, as `services/api/AGENTS.md` requires.
- `ALLOWED_ORIGINS`: must become `http://127.0.0.1:3000` locally, and the code default grows to hold both `127.0.0.1` and `localhost` spellings so a fresh clone is not broken either way. See the cookie note below.
- The web app's API base URL must be `http://127.0.0.1:8000` locally, for the same reason.
- No change to the deployed function's environment at all.

**One consequence worth stating before it surprises you**: `AUTH_SECRET` joins `saved_rules_problems`, so the rules endpoints answer 501 until the secret is set. A local setup that works today stops working after this ships until you add one line to `.env`, which is correct (rules now need an account) but looks like a regression. The 501 body names the missing variable so the cause is in the response rather than in your memory.

**The cookie, the hostname and CORS, the one part that fails silently**

Browsers ignore the port when deciding whether two URLs are the same site, but not the hostname, and `localhost` and `127.0.0.1` are different hostnames. Today `make dev` serves the web app on `localhost:3000` while the API binds `127.0.0.1`, so a `SameSite=Lax` cookie would simply not be sent, with no error anywhere.

The API cannot move. `live_mode_problems` requires the bound host to be exactly `127.0.0.1` (`settings.py:49`), and `saved_rules_problems` delegates to it, so binding `localhost` would turn the feature off rather than fix the cookie. The web app moves instead: serve it from `127.0.0.1:3000`, point it at `127.0.0.1:8000`, and set `ALLOWED_ORIGINS` to match.

**Changing only `.env` is not enough, and getting this half right breaks more than the login.** `settings.py:77` hard codes `http://localhost:3000` as the default origin, so a fresh clone that has not set `ALLOWED_ORIGINS` and opens `localhost:3000` loses **every** API call, scanning and backtesting included, not just signing in. That would fail AC-15. So the code default becomes both `http://127.0.0.1:3000` and `http://localhost:3000`, and the build must also update every other place the hostname is written down: the web app's API base URL, the dev server host the `make dev` target passes, the end to end test configuration, and the README.

Separately, `main.py:32-40` configures CORS with no `allow_credentials`, so the browser would refuse to attach the cookie even once the hostnames agree. It must become `allow_credentials=True`, and the web app's `openapi-fetch` client needs `credentials: "include"` to match. **Set it only when auth is enabled, not unconditionally**: the deployed API allows Vercel preview origins through `ALLOWED_ORIGIN_REGEX`, and turning credentials on there would make every one of those a credentialed origin on the public API, for a feature that is switched off there anyway. Starlette does echo a matching regex origin back, so the two can combine; the reason not to is that there is no reason to.

**What the hostname alignment does not buy you.** A `SameSite=Lax` cookie is scoped to the host and ignores the port, so the cookie goes to **any** service running on `127.0.0.1`, not just the API. Any other local development server you have running can read it. That is acceptable here, because the only thing on that loopback address is your own work, but it means the alignment fixes delivery rather than giving clean isolation, and `SameSite` is doing less for you than it looks.

**Critical test scenarios** (each maps to a criterion above)

- Happy path: register, sign in, save a rule, read it back as that account's row, through the real API against the real Neon database, verifies **AC-1**, **AC-3**.
- Restart: a signed in browser is still signed in after the API process restarts, verifies **AC-1**.
- Isolation: two accounts each save a rule called `Foo`; each list shows exactly one row, and each delete of the other's id returns 404, verifies **AC-3**, **AC-6**.
- Readable password: the stored value parses as an Argon2id PHC string and does not contain the password; a sign in with logging at debug level emits no line containing it; and **a register call with a 5 character password returns a 422 whose body does not contain those 5 characters**, which is the case FastAPI's default body fails, verifies **AC-2**.
- Migration under load bearing ordering: `0003` against a database holding orphan rules fails with a message naming `make claim-rules`, and `0002` is **still applied** afterwards so the backfill can run; a fresh empty database runs all three steps in one command, verifies **AC-11**.
- Cross account cache: sign in as one account, sign out, sign in as a second, and the panel shows only the second account's rules, in a real browser rather than against the API, verifies **AC-3**.
- A sleeping database: a request whose connection fails returns 503 and the web app shows a retry notice, not a signed out state, verifies **AC-8**.
- Both hostname spellings: with the widened origin default, a scan works from `localhost:3000` and from `127.0.0.1:3000`, and signing in works from `127.0.0.1:3000`, verifies **AC-15**, **AC-10**.
- Duplicate email: registering `You@x.com` then `you@x.com` returns 409 and leaves one row, verifies **AC-6**.
- Indistinguishable failures: a wrong email and a wrong password return identical bodies, verifies **AC-7**.
- Bad tokens: expired, malformed, wrongly signed, and valid for a deleted account each return 401 with the cookie cleared, verifies **AC-8**.
- Cascade: deleting an account removes its rules, checked by querying the table directly after, verifies **AC-9**.
- The cookie in a real browser: sign in, then confirm the browser attaches the cookie to a cross origin rules request. **Not provable by an API level test**, since those bypass the browser's own rules entirely, so this is a real browser check, verifies **AC-10**.
- Migration: an empty database reaches the current schema by running the chain in order; and a database holding pre accounts rules reaches it too, with those rules owned afterwards, verifies **AC-11**.
- Disabled: with no `AUTH_SECRET`, every auth endpoint and every rules endpoint answers 501, and the pages show the notice, verifies **AC-4**.
- Host gate: with both variables set but the Lambda environment marker present, everything still answers 501, verifies **AC-5**.
- Signed out locally: the saved rules panel shows the empty state and its link, and axe finds nothing, verifies **AC-12**.
- No database: the whole suite runs, skips the database dependent cases, and `make ci` is green, verifies **AC-13**.
- Untouched: a scan, a backtest and an exit lab run all succeed signed out, verifies **AC-15**.
- The contract stayed in step: CI's OpenAPI to TypeScript diff check passes, meaning the regenerated client and the mocks match the app rather than lagging it, verifies **AC-14**.

## Build plan

Tracer Bullet (basis: `AGENTS.md`, the project build approach). The thread is one account registering, signing in, and saving one owned rule through the real API against the real database, in a real browser, before deletion, the pages, the backfill or any polish. The cookie work sits inside the thread rather than after it, because a cookie that is not sent makes every later step untestable.

1. [x] Add `argon2-cffi` and `PyJWT` to the API's dependencies. Add `AUTH_SECRET` to `Settings` and `.env.example` with the 32 character floor, and add its check to `saved_rules_problems` so the auth and rules surfaces share one gate rather than drifting apart, satisfies **AC-4**, **AC-5**
2. [x] Set `transaction_per_migration = True`, then migration `0002`, plain SQL in `op.execute()` extending spec 0014's chain: the `accounts` table, `rules.account_id` nullable with its named foreign key and `ON DELETE CASCADE`, `rules_name_lower_idx` dropped, `rules_account_name_lower_idx` added, and a `downgrade` that refuses rather than re-creating a global name index that cannot hold, satisfies **AC-9**, **AC-11**
3. [x] `engine/src/engine/data/accounts.py`: insert an account, select by `lower(email)`, select by id, delete by id, with the Argon2id hash and verify, the import time dummy hash built from the same hasher, the stripped email and unstripped password, and one connection per request as spec 0014 established, satisfies **AC-2**, **AC-6**
4. [x] The `engine.api` use cases plus the token encode and decode helpers in `services/api`: `algorithms=["HS256"]` pinned, `exp` and `sub` required, a non UUID `sub` as a 401, the constant time dummy verify on a missing account, the identical 401 body, and the cookie cleared on every 401, satisfies **AC-1**, **AC-7**, **AC-8**
5. [x] The 422 handler on the auth routes that strips `input` and `ctx`, so a rejected password never travels back in the response body, satisfies **AC-2**
6. [x] The cookie's plumbing: `allow_credentials` in `main.py` set only when auth is enabled, the `settings.py` origin default widened to both hostname spellings, and `127.0.0.1` adopted in the web app's API base URL, the `make dev` host, the end to end configuration and the README, satisfies **AC-10**, **AC-15**
7. [x] **Prove the thread**: register, sign in, save one rule and read it back as that account's row, against the real Neon database in a real browser, satisfies **AC-1**, **AC-3**, **AC-10**
8. [x] One `contract-change` PR covering all five auth endpoints and the three rules endpoints gaining 401: the FastAPI dependency that runs the enabled check before the token so the demo still answers 501, resolves the account from the cookie, shares its connection with the rules statement, and returns 503 on a database failure, plus the regenerated `api-client`, the updated mocks including the new 501 entries, and owner approval, satisfies **AC-3**, **AC-4**, **AC-8**, **AC-14**
9. [x] Ownership inside the rules repository: every statement filtered by `account_id`, the insert taking its owner from the authenticated account, a cross account delete answering 404, satisfies **AC-3**
10. [x] `make claim-rules EMAIL=...`, which fails unless exactly one account matches and is rerunnable, then migration `0003` flipping `account_id` to `NOT NULL` behind its own orphan row check, and `make migrate` stopping at `0002` while orphans remain, satisfies **AC-11**
11. [x] The `/sign-in` and `/register` routes, with the 501 notice path, no navigation link to either, and a return to `/` after signing in, satisfies **AC-4**
12. [x] The header's signed in state and its sign out, the saved rules panel's signed out empty state linking to `/sign-in`, the save control hidden on 501 and disabled with a link on 401, and `queryClient.clear()` on sign in and sign out, satisfies **AC-1**, **AC-3**, **AC-12**
13. [x] Account deletion: the endpoint, a confirm dialog in the header menu with no password re-prompt, the cascade checked against the real database, then `queryClient.clear()` and the browser left signed out at `/`, satisfies **AC-9**
14. [x] The web app's handling of anything that is not 200, 401 or 501: a retry notice through the existing `ErrorState`, and a mid session 401 clearing the `me` cache rather than leaving a stale header, satisfies **AC-3**, **AC-8**
15. [x] The skips when no database or no secret is configured, so `make ci` stays green on the D-4 pattern, satisfies **AC-13**
16. [x] Confirm scan, backtest, the exit lab and meta are untouched signed in and signed out, on both hostname spellings locally and on the demo, satisfies **AC-15**

## Consequences

**Positive**:
- No third vendor, no new free tier to watch, no ADR for a new service, and no change to the $0 at rest cost. It extends the database, the migration chain and the gate pattern that already exist.
- It closes three debts spec 0014 opened on purpose: the owner column, per account name uniqueness, and the cascade it could not write because it had no child table.
- It is the most interview ready part of the project, and it stays that way because the reasoning is here rather than inside a vendor's dashboard.
- The isolation is a `WHERE` clause on every statement rather than a filter applied after reading, so the failure mode is an empty result instead of a leak.
- Two tables, one relationship, five endpoints. Small enough to read in one sitting.
- Features 23's saved runs inherit a working owner column and a working auth dependency instead of inventing either.

**Negative / tradeoffs**:
- **A token cannot be revoked.** With no sessions table, a token that leaks stays valid for up to 30 days, and nothing you can do from the server shortens that. The per request account lookup limits the damage to a live account, and the local only gating limits it further, but the limitation is real and is the direct cost of the chosen option.
- The per request lookup spends the main efficiency argument for a token rather than a session row. It buys back correctness on deletion, which matters more here, but it means the JWT is doing less work than JWTs usually do, and **every gated request now costs a database round trip**, including the roughly half second Neon takes to wake from idle on the first one.
- **Losing or rotating `AUTH_SECRET` signs you out with no warning and no recovery.** There is no server side record of a session, so a changed key simply makes every existing token unreadable. That is the direct cost of keeping identity in the cookie.
- The 30 day expiry is fixed, with no sliding renewal, so an active session still ends abruptly on day 30 and asks you to sign in again. Adding renewal would mean reissuing the cookie on activity, which is the beginning of the session machinery this option exists to avoid.
- Downgrading migration `0002` is deliberately refused once two accounts exist, because the global name index it would restore cannot hold. Forward is the only route, which is fine for a local database and would not be for a shared one.
- **Hand rolled authentication is the thing most likely to contain a quiet bug**, and no amount of care fully removes that. What makes it acceptable is not the care, it is that three independent gates keep the surface off the public internet.
- The hostname alignment is a sharp edge for anyone else cloning the repo: use `localhost` and the cookie silently vanishes, with no error to search for. It needs a README line and a comment, and it will still catch someone.
- Two more dependencies in the API image, lengthening cold start for code the deployed function never runs.
- **The feature still cannot be shown on the hosted demo**, so accounts, like saved rules, are visible only locally or in a recording. That is the deliberate choice, but it means the two most substantial backend features in the project are the two an interviewer cannot click.
- Most of these criteria are not checked by CI, because the feature is off there and no Postgres runs in the pipeline. Your local run is the evidence, which is D-4's precedent and is still weaker than a test on every pull request.
- The rules list stays unpaginated. Fine for one person's rules, and it inherits spec 0014's reasoning rather than fixing it.
- No password reset, so forgetting the password means deleting the row and registering again.

**Neutral**:
- A contract change, so the generated client, the mocks and owner approval are in scope.
- Root `AGENTS.md` currently says "no auth", which stops being true. `/sync` owns that line.
- Nothing about the engine's trading logic, the market store or the synthetic writer changes. Scan and backtest never learn that accounts exist.
- The `rules` table keeps its `jsonb` column and its single validator. Accounts add a column and two indexes, not a redesign.

## Follow-up

- [ ] **Most criteria are evidenced by your local run, not by CI**, on D-4's and spec 0014's precedent. `docs/qa/traceability.md` needs those rows marked that way, and QA owns that file.
- [ ] Root `AGENTS.md` says "no auth" in its stack line. That becomes wrong when this ships, and `/sync` owns the edit.
- [ ] **The rate limit and the request body limit are both still owed**, and both are now owed by whichever feature first makes a write endpoint reachable by someone other than you. Spec 0014 pointed its body limit debt at feature 22; feature 22 does not open the surface, so the debt moves rather than closes. Say so wherever that next feature is specced.
- [ ] Adding Neon was spec 0014's ADR; this spec adds no new service, so no new ADR is owed. If the project keeps the separate numbered ADR series that `rule.py` cites, this decision still wants a pointer entry there.
- [ ] Feature 23's saved runs should take their owner column and their auth dependency from here rather than adding a second pattern, and should keep taking the dataset identity from spec 0013's `Assumptions.data_end`.
- [ ] `argon2-cffi` and PyJWT conventions belong in `services/api/AGENTS.md` and `engine/AGENTS.md` once the build settles them. `/sync` owns that.
- [ ] Measure cold start after step 1. If the two dependencies cost anything material, the auth router can import them lazily, since the deployed function never reaches that code.
- [ ] If you ever do want an interviewer to click a login, the smallest honest version is a seeded read only demo account on the deployed API, which needs the rate limit and the body limit above first. Worth a decision of its own rather than a quiet relaxation of the gates.
