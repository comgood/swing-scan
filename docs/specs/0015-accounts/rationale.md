# 0015 rationale: accounts

The reasoning behind [index.md](index.md). `/develop` does not need this file; a human reviewing the decision does.

## Context

Saved rules landed in spec 0014 as rows with no owner. That was fine while there was exactly one writer, because the surface was gated to your own machine and nobody else could reach it. It left three things unfinished on purpose, all recorded in that spec's own follow up: the rules table has no owner column, rule name uniqueness is global rather than per person, and there is no request body limit because a local only endpoint did not need one. Feature 23 then wants to store backtest runs, and it will inherit whatever shape this decision sets, so the owner column cannot stay undecided much longer.

The forces pulling on the decision are unusual, and they pull against the normal advice. The project costs nothing at rest and is a learning and portfolio piece rather than a product, so a third vendor has a real price beyond money: a free tier to watch, an ADR to write under the project's own never list, and a chunk of the most interesting engineering moved somewhere an interviewer cannot look at it. The scope row for this feature is explicit that accounts run locally only and that the deployed demo runs with accounts switched off, which removes almost the entire threat model that normally decides an auth build: there is no public login to attack, no stranger registering, no password to reset for someone who is not you, and no real person's data to lose.

Two technical constraints shape it from below. The web app is a static export on Vercel Hobby, so there is no server beside it to hold a session, do a redirect, or proxy the API onto one origin; whatever carries identity has to work from the browser straight to the API. And the API is a FastAPI process that binds `127.0.0.1` locally and runs as a Lambda container in production, with the host binding load bearing rather than incidental: `live_mode_problems` refuses to start live data mode unless the bound host is exactly `127.0.0.1`, and `saved_rules_problems` delegates to it, so the gate that keeps this feature private is tied to that one address.

Not deciding has a cost beyond delay. Every rule row saved between now and the decision is a row with no owner, so the longer it waits the more awkward the migration becomes.

## Options considered

### Option 1: A hosted authentication provider

Put identity in a managed service, Clerk, Auth0, Supabase Auth, WorkOS or similar, and let it own registration, sign in, sessions, password storage and the forms. The API verifies a token the provider issued; the web app uses the provider's own React components.

**Pros**:
- The fastest path to a working login, and genuinely the most secure in a vacuum: password handling, token rotation, breach monitoring and the forms are all maintained by people whose job that is.
- It would make the login work on the deployed demo, which is the one thing the chosen option cannot do.
- Adds features free that are out of scope here: reset, verification, social sign in, multi factor.

**Cons**:
- A third vendor, which root `AGENTS.md`'s never list bars without an ADR, plus another free tier to track and another dashboard holding part of the system.
- It removes the engineering. The most interview ready piece of the project becomes configuration, and the spec becomes a note about which provider was chosen.
- Real complexity for a static export with no server: the callback and token refresh are all client side, and the provider's components bring their own styling that fights the project's design tokens.
- It solves threats this deployment does not have, at the cost of the only two things the project actually optimises for, which are cost and demonstrated understanding.

### Option 2: A self hosted authentication library

Install something like `fastapi-users`, hand it a user model and a database, and get registration, sign in, password hashing and the endpoints from the library.

**Pros**:
- Much less code to own than hand rolling, with the password handling and token logic written and tested by someone else.
- No vendor, no cost, and it stays entirely inside the API.
- Conventional enough that a reviewer recognises it instantly.

**Cons**:
- It brings SQLAlchemy models, which spec 0014 deliberately refused after weighing it, so this would undo that decision and put two data access patterns in the same small database.
- The library's user model wants to own the schema, which fights the migration chain of hand written SQL that spec 0014 chose precisely because it is reviewable.
- Most of what it provides is scope that is explicitly out: verification, reset, multiple backends. The part that is in scope is small.
- It hides the decision rather than removing it, so the interview answer becomes "the library does it", which is the weakest version of both worlds.

### Option 3: Hand rolled, an opaque token with a sessions table (recommended, not chosen)

Write it on the existing Neon database: an `accounts` table, Argon2id hashing, and a `sessions` table holding a random opaque token per sign in. The cookie carries the token; a request looks the row up to know who is calling, and sign out deletes the row.

**Pros**:
- Sign out actually ends the session, server side, and a leaked token can be revoked immediately by deleting one row.
- Nothing is encoded in the cookie, so there is no signature to verify, no algorithm to confuse, and no claim that can be stale.
- The per request lookup pays for itself: it is the same read that confirms the account still exists.
- A sessions table makes "signed in on two browsers, sign one out" natural rather than impossible.

**Cons**:
- A third table, its own index, and an expiry sweep or a lazy expiry check, all to manage state that the chosen option keeps in the cookie.
- It needs a deliberate token generation and comparison path, which is one more small thing to get right.
- Revocation, its main advantage, is worth least in exactly this deployment, where there is one user on one machine and no stranger who could hold a stolen token.

### Option 4: Hand rolled, a signed token in an httpOnly cookie, no sessions table (chosen)

The same `accounts` table and the same Argon2id hashing, but the cookie carries a signed token (a JWT) holding the account id and an expiry. No sessions table. A gated request verifies the signature, reads the account id from the claim, and then reads that account row to confirm it still exists.

**Pros**:
- One table rather than two, no expiry sweep, no session rows accumulating, and nothing to clean up.
- Staying signed in across a restart is a property of the signing key rather than of anything stored, so it works as long as `AUTH_SECRET` comes from the environment.
- A standard, recognisable format, and PyJWT is a tiny, well maintained dependency that refuses the algorithm confusion mistakes a hand written verifier makes.
- The per request account read, added deliberately, recovers correct behaviour on account deletion, which is the only revocation case this deployment actually has.

**Cons**:
- **A token cannot be revoked.** If one leaks it stays valid until it expires, up to 30 days, and nothing server side shortens that.
- Sign out clears the cookie, which signs the browser out truthfully, but it cannot invalidate a copy of the token taken beforehand.
- The per request account read spends the main efficiency argument for a signed token, so the JWT ends up doing less work than a JWT usually does.
- Signing keys are a new kind of secret to hold, and an `AUTH_SECRET` that changes between restarts silently signs everyone out.

### Two shapes offered and declined, recorded so the record is complete

Neither became a full option, but both were put to the engineer during the design conversation and both were declined, so they belong here rather than looking like oversights.

**A signed cookie through Starlette's own `SessionMiddleware`, or `itsdangerous` directly**, would drop PyJWT and the encode and decode helpers entirely, since it is purpose built for exactly this: signing a small value into a cookie. It was declined in favour of the standard format. The reasoning is worth stating honestly, because `itsdangerous` is genuinely the simpler tool: a JWT is recognisable to any reviewer, carries its own expiry claim rather than needing a timestamp carried by hand, and PyJWT refuses the algorithm confusion mistakes that a thinner signer leaves to the caller. That is a readability and familiarity argument more than a technical one.

**A bearer token in `localStorage`** would remove the cookie, `SameSite`, CORS credentials and hostname problem completely, which is the single largest source of build risk in this spec. It was declined because any script on the page can read it, and "we put the credential where cross site scripting can reach it" is the first thing a reviewer flags, even on a surface only the owner can reach. The cookie work is the price of not having that conversation.

## Rationale

The local only constraint is what decides this, and it decides it against the usual advice. Normally "do not hand roll authentication" is close to absolute, because the cost of a subtle bug is every user's account. Here the scope row removes that: three independent gates keep the surface off the public internet, so a quiet bug in this code is reachable by one person, on one machine, who also wrote it. That is not an argument that the code is safe. It is an argument that the usual reason to buy instead of build has had most of its force taken away, while the reasons to build, cost and demonstrated understanding, are exactly what the project exists for (basis: the scope row for feature 22, local demo only; `AGENTS.md`'s never list on adding a service).

Options 1 and 2 both fail on the same point from two directions. Option 1 moves the interesting part out of the repository and adds a vendor the never list would make you justify, to defend against a public attacker this deployment does not have. Option 2 keeps it in the repository but requires undoing spec 0014's deliberate rejection of SQLAlchemy models, which would put two data access patterns into a database with two tables in it. Neither price buys anything the deployment needs.

Between the two hand rolled shapes, Option 3 was recommended and Option 4 was chosen. The engineer's reasoning holds: revocation is the whole advantage of a sessions table, and in a deployment with one user on one machine there is no scenario where a token needs revoking before it expires. What Option 4 would have given up, though, is more than revocation. Account deletion is in scope, and a signed token for a deleted account keeps working for its full lifetime, which would have made deletion a lie and produced a confusing foreign key error instead of a clean 401. That is why the per request account lookup is part of the decision rather than an optimisation to skip: it costs one indexed primary key read on three endpoints and it is what makes deletion mean something. With that read in place, Option 4 gives up only the revocation of an already stolen token, which is the one thing this deployment genuinely cannot suffer from, and the remaining gap is recorded honestly as a negative consequence rather than argued away.

That lookup does narrow the gap between the two options, and the narrowing deserves to be said out loud rather than left implied. Once a database read happens on every gated request, Option 3's "but it reads a row" objection disappears, and what separates them is one table against one signing key. Option 4 is still the smaller shape: no second table, no expiry policy for session rows, no sweep or lazy expiry, and no decision about what happens to other sessions when one signs out. Option 3's remaining advantage is real sign out and revocation, which is worth a great deal in a system with users and close to nothing in a system with one user on one machine behind three gates. So this is a genuinely close call that went to the smaller shape, not a clear win, and if accounts ever became reachable by anyone else, revocation alone would be reason enough to revisit it. That reversal condition is the honest summary of the decision.

The build's real risk is not the cryptography, which is two library calls, and it is not the schema, which is one column and two indexes. It is the cookie. A `SameSite=Lax` cookie is not sent between `localhost` and `127.0.0.1`, because browsers compare hostnames and ignore ports, and the API cannot move to `localhost` without tripping the host gate that keeps the feature private in the first place. On top of that, the CORS middleware does not set `allow_credentials` today, so the cookie would be dropped even once the hostnames agree. Both failures are silent: no error, no log line, just an endpoint that behaves as though nobody is signed in. That is why the cookie work sits inside the Tracer Bullet thread rather than after it, and why one acceptance criterion insists on a real browser, since an API level test bypasses the browser rules that are the whole problem (basis: OWASP session management guidance on cookie attributes; `settings.py:49`, the pinned bound host).

A cross check on a different model read this spec before it was accepted and found about fourteen decisions the first draft left for the build to invent, four of which would have broken a stated criterion: FastAPI's default 422 body echoes the rejected password, Alembic's single transaction for `upgrade head` would have rolled the new `accounts` table back when `0003` hit orphan rows and left the backfill with nowhere to run, changing only `.env` rather than the code default would have broken scanning for anyone opening `localhost:3000`, and an uncleared client cache would have shown one account's rules to another. All are now settled in `index.md` rather than left to `/develop`. Worth recording that the first draft's gaps were in what it failed to specify, not in what it specified: every claim it made about the existing code checked out.

## References

**Project sources** (verifiable, in this repo):
- `AGENTS.md`, the Clean Architecture layout, the Tracer Bullet build approach, and the never list that bars adding a service without an ADR
- Spec [0014](../0014-saved-rules/index.md), which set the Neon database, the Alembic chain, the plain SQL and `psycopg` repository pattern, the two gate local only rule, the `lower()` uniqueness convention, and the three debts this spec inherits
- Spec [0010](../0010-live-research-mode/index.md) and criterion D-5, the host check this feature reuses as its third gate
- `services/api/src/api/settings.py`, whose `live_mode_problems` pins the bound host to `127.0.0.1` and so decides which side of the cookie problem has to move
- `services/api/src/api/main.py`, whose CORS configuration currently omits `allow_credentials`
- `services/api/AGENTS.md`, the rule that routers call `engine.api` use cases only
- The scope row for feature 22, which states that accounts are local demo only and that the hosted demo runs with them switched off

**Practices & standards**:
- OWASP password storage guidance, on Argon2id as the default choice and on not inventing your own salt or cost parameters
- NIST SP 800-63B, on a length minimum with no composition rules and no forced rotation
- OWASP session management guidance, on `httpOnly` and `SameSite` cookie attributes
- OWASP authentication guidance, on identical responses for a wrong identifier and a wrong secret, and on the enumeration tradeoff that registration cannot fully close
- Constant time comparison against a dummy hash on a missing account, so authentication timing does not disclose whether an account exists
- Database enforced referential integrity for deletion, rather than application code that can be forgotten
