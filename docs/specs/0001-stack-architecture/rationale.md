# 0001. Rationale: stack and architecture

## Context

Swing Scan is a learning and portfolio project: a swing trading scanner and research tool with a rule builder, an honest portfolio backtester, and an exit lab, built by one owner with up to four AI coding agents in about a week (doc 02, section 15). It will never be sold. The binding constraints are $0 a month, a public GitHub repo, and the free data terms: real prices may never be shown to anyone else, so the public demo runs on a generated market and real data stays on the owner's machine (doc 01, doc 01a).

The work splits into two very different halves. The numerical half (indicators over about 500 tickers by 1,260 to 2,700 days, a day by day portfolio simulator, trade by trade exit comparisons, a seeded random baseline) is correctness critical and lives naturally in the Python data ecosystem. The interactive half (a rule builder, sortable result tables, an exit lab comparison, an equity chart) is a typical modern web UI. The owner also wants the stack to match what companies hiring full stack developers use, because the repo is a resume piece.

Operationally there is no one to run servers: the stack must have nothing that needs patching or stays on between demos, must survive weeks of no traffic, and must fit free tiers that do not sleep in ways that break a recruiter's first click. Several agents will build in parallel, so the boundaries between web, API, and engine must be clear enough that lanes rarely touch the same files.

If this is not decided first, every later spec (contracts, design system, scan, backtest) would make its own hosting and tooling assumptions, and the scaffold could not be built.

## Options considered

Options considered were weighed in planning (doc 02 v0.1 to v2.3 and the devil's advocate review, doc 03); the full stacks compared were:

### Option 1: Next.js on Vercel + FastAPI engine in an AWS Lambda container (chosen)

A static first Next.js app on Vercel Hobby calls a FastAPI service packaged with the synthetic data as a container image on Lambda behind a Function URL, deployed by GitHub Actions with OIDC.

**Pros**:
- $0 with always free Lambda allowances and Vercel Hobby; neither sleeps the way some free hosts do.
- AWS, Docker, OIDC, Next.js, and FastAPI are all high signal on a CV.
- Python for the numbers, TypeScript for the UI, one Pydantic schema for both.

**Cons**:
- Lambda cold starts and hard limits (timeout, payload size, no state).
- AWS setup (ECR, IAM, OIDC, budget) is the fiddliest Day 1 task.

### Option 2: Next.js on Vercel + FastAPI container on Google Cloud Run

Same split, but the API runs as a plain container on Cloud Run's free tier.

**Pros**:
- Simplest container host; no adapter, generous request timeout, scales to zero.
- Fewer packaging surprises than Lambda.

**Cons**:
- Needs a card on file like AWS, with less weight on a resume than AWS for most postings.
- Cold starts still exist when scaled to zero.

### Option 3: All TypeScript (Next.js with API routes and a TypeScript engine)

One language and one deploy: the engine written in TypeScript and served from Next.js route handlers on Vercel.

**Pros**:
- One toolchain, one deploy, no generated client.
- Very common full stack shape in job postings.

**Cons**:
- Weaker numerical ecosystem (no Polars or NumPy equivalent with the same maturity) for the most correctness critical code.
- Vercel function limits and execution time on the free plan constrain backtests; loses the Python and AWS signal.

### Option 4: All Python (FastAPI with server rendered pages or a notebook style app)

The engine plus a Python rendered UI (templates, HTMX, or an app framework like Streamlit) on one host.

**Pros**:
- Fastest to build for one person; one language end to end.
- No CORS, no client generation.

**Cons**:
- Little frontend signal for full stack roles; the UI ceiling is lower for a rich rule builder and exit lab.
- Hosting a long lived Python web app for free usually means a host that sleeps.

## Rationale

Option 1 is the only stack that satisfies all three binding forces at once. The numerical core needs Python (the correctness critical simulator and the Polars indicator engine), the resume goal needs a mainstream React frontend and a major cloud, and the $0 constraint with an always available demo rules out hosts that sleep and anything that runs continuously. Splitting the code into a web app, a thin API, and a web free `engine` package also gives the parallel agent lanes clean file ownership, which an all in one app (Options 3 and 4) would not.

Cloud Run (Option 2) is genuinely simpler to deploy, and it stays the documented fallback after a 3 hour timebox. AWS won because resume signal is an explicit goal and AWS appears in more full stack postings; the cost of that choice is a fiddlier Day 1, which the timebox caps.

The finer choices follow the same forces. pnpm workspaces plus a uv workspace are enough for two packages per side, so a monorepo orchestrator would add setup without benefit. openapi-typescript with openapi-fetch generates only types, which keeps the "is the client stale" CI check a small, readable diff. TanStack Query absorbs the cold start and retry states the Lambda choice creates. ESLint with Prettier and Node 24 LTS are the boring defaults hiring teams expect. The engine and API are separate uv packages so the engine has no web dependencies and QA can test it directly. Singapore (`ap-southeast-1`) was the owner's choice for local latency, accepting slower first responses for US visitors.

## References

**Project sources**:
- `docs/02-technical-design-and-roadmap.md`: section 2 (tech stack and job market evidence), section 4 (architecture), section 8.2 (Lambda limits), section 12 (ADR-001 to ADR-016), section 15 (parallel lanes)
- `docs/01-market-research-and-product-spec.md`: the binding frame, acceptance criteria D-5, D-6, U-5
- `docs/01a-free-data-sources.md`: personal use only terms for free price data
- `docs/03-devils-advocate-review.md`: the $0 stack critique and the cut to a modular monolith
- `docs/scope/scope.md`: feature 1, Stack & architecture

**Practices & standards**:
- Monolith first; extract services only when a bottleneck forces it
- Boring, proven technology over new
- Measure before optimising (no Numba, queue, or cache layer until profiling shows a need)
- Short lived OIDC credentials instead of stored cloud keys
- Single source of truth for API contracts (schema generated clients)
