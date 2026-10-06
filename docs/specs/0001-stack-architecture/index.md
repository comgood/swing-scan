# 0001. Adopt a Next.js web app with a Python FastAPI engine on AWS Lambda

**Date**: 2026-10-06
**Status**: In Progress

## Summary

Swing Scan is built as two small apps in one repo: a Next.js website (the screens you click) on Vercel's free plan, and a Python API (FastAPI, which runs the scanner and backtester) packaged as a container and run on AWS Lambda in Singapore. A shared Python `engine` package holds all the trading logic, so the API is a thin wrapper and the QA tests can call the engine directly. Everything runs on free tiers (about $0 to $0.10 a month, mostly image storage), there is no database (the public data is a generated market baked into the API image), and GitHub Actions builds, tests, and deploys it. This was decided in planning (doc 02, sections 2, 4 and 12); this spec records it as the one place `/develop` reads the stack from.

## Decision

**Chosen option**: Option 1: Next.js on Vercel plus a FastAPI engine in a Lambda container (see `rationale.md`).

Build Swing Scan as a pnpm plus uv monorepo with a Next.js frontend on Vercel Hobby and a FastAPI service over a separate `engine` package, shipped as one container image to AWS Lambda (Function URL, `ap-southeast-1`), with no database and GitHub Actions for CI and OIDC deploys. (basis: doc 02 section 2 and ADR-001)

**Implementation skills**: `vercel-react-best-practices` (`vercel-labs/agent-skills`, `.claude/skills/vercel-react-best-practices/`) · `nextjs-app-router-patterns` (`wshobson/agents`, `.claude/skills/nextjs-app-router-patterns/`) · `tailwind-design-system` (`wshobson/agents`, `.claude/skills/tailwind-design-system/`) · `aws-serverless` (`aws/agent-toolkit-for-aws`, `.claude/skills/aws-serverless/`) · `aws-iam` (`aws/agent-toolkit-for-aws`, `.claude/skills/aws-iam/`) · `python-testing-patterns` (`wshobson/agents`, `.claude/skills/python-testing-patterns/`)

## Proposed stack

| Layer | Choice | Reason |
|---|---|---|
| Architecture pattern | **Modular monolith**: one API service over one engine package, one static web app | Solo builder, one week, about a dozen screens; no service boundary earns its cost (basis: monolith first) |
| Repo layout | **Monorepo**: pnpm workspaces for JS, a uv workspace for Python, a root `Makefile` that runs both | Two JS packages and two Python packages need no build orchestrator; `make` gives one entry point for agents and CI |
| Web language | **TypeScript** (strict mode) on **Node 24 LTS** | Type safety across the generated API client; Node 24 is the current Active LTS (verify at scaffold time) |
| Web framework | **Next.js (App Router) + React** | The most hired for React framework; static pages plus client components fit a tool UI (basis: doc 02 job market evidence) |
| Styling and components | **Tailwind CSS + shadcn/ui** | Fast, accessible primitives (forms, tables, dialogs) you own as source; feeds spec for feature 4 |
| Tables | **TanStack Table** | Sorting and column control for scan results and trade lists without a heavy grid |
| Charts | **TradingView Lightweight Charts** | Equity curve against the benchmark with the OOS marker; small, fast, Apache 2.0 with attribution |
| Data fetching | **TanStack Query** over **openapi-fetch** | Handles loading, error, retry and the cold start "warming up" state (U-5) without hand written state code |
| API client | **openapi-typescript** types generated from FastAPI's OpenAPI, committed in `packages/api-client` | Types only, small diffs; CI fails if the generated client is stale, so web and API cannot drift |
| JS lint and format | **ESLint + Prettier** | Industry default and what Next.js ships with |
| API language | **Python 3.12**, managed by **uv** | Fast, reproducible installs; one lockfile for the uv workspace |
| API framework | **FastAPI + Pydantic v2** | Pydantic models are the single source for rule and exit schemas and the OpenAPI contract |
| Engine | **`engine` package**: Polars (indicators, rules) + NumPy and plain Python loops (simulator) | Clear, testable code first; no Numba until profiling demands it (ADR-006) |
| Python lint and types | **Ruff** (lint and format) + **mypy** on `engine` | One fast linter; types where correctness matters most |
| Tests | **pytest** (oracle, golden, acceptance, unit) + **Vitest** (web) | Oracle tests run first and fail fast; Playwright is deferred |
| Primary data store | **None.** Synthetic Parquet built into the API image; live data in local `data/live/` only | Static, small (about 10 to 20 MB) data needs no database; keeps $0 and the licensing rule (ADR-002, ADR-003, ADR-004) |
| App state | **URL** (rule and exit configs as base64url JSON) + **localStorage/sessionStorage** (trial counter) | No accounts in week 1 (ADR-002) |
| Auth | **None** | The public demo is read only on synthetic data; live mode is localhost only (ADR-009) |
| Background jobs | **None.** Scans and backtests run synchronously in the request | Under the 30 s timeout at this data size; revisit at p95 > 10 s (ADR-005) |
| API hosting | **AWS Lambda**, container image in **ECR**, **Function URL** with `AuthType NONE` (no API Gateway), **AWS Lambda Web Adapter** (pinned version) on `python:3.12-slim`, **x86_64**, **2 GB** memory, **30 s** timeout, **reserved concurrency 5 if the account quota allows** (see Build and deploy conventions), region **`ap-southeast-1`** | Same uvicorn app locally and in the cloud; the always free allowance (1M requests, 400k GB seconds a month) covers demo traffic (ADR-001) |
| Web hosting | **Vercel Hobby**, static export (`output: 'export'`), project root `apps/web`, Git integration and PR previews | Nothing runs on Vercel's servers, so it is plain static hosting; $0 for a personal, non commercial project |
| CI/CD | **GitHub Actions** (public repo), **OIDC** to an IAM role for ECR push and Lambda update | No stored cloud keys; unlimited minutes on a public repo |
| Infrastructure setup | **Scripted AWS CLI steps** in `infra/README.md`, run by you; Terraform is deferred | Faster to ship in week 1; imported into Terraform later (ADR-010) |
| Cost guard | **AWS Budgets alarm at $1** plus a CloudWatch alarm on Lambda throttles | Catches any spend outside the free allowances and flags abuse; expected cost about $0 to $0.10 a month (ECR storage) |
| Observability | **CloudWatch logs** (7 day retention) and structured JSON logs from FastAPI; Sentry deferred | Enough to debug a demo; free |
| Repo hygiene | **pre-commit** + CI: Ruff, ESLint, Prettier, **gitleaks**, the data leak guard (D-6), and a guard that blocks agent edits to `tests/oracle/` | Public repo plus vendor terms; protects the owner approved oracles |
| Source hosting | **GitHub**, public repository | Required for free Actions minutes and as the portfolio artifact |

### Repository layout

```
apps/web/                Next.js app (FE lane)
packages/api-client/     generated OpenAPI types + openapi-fetch client
services/api/            FastAPI app, Dockerfile (uv workspace member)
engine/                  trading logic package, no web dependencies (uv workspace member)
contracts/               frozen OpenAPI snapshot, JSON schemas, mocks (feature 3)
tests/oracle/            owner approved oracle tests (protected)
tests/acceptance/        QA acceptance tests
tests/golden/            QA naive reference implementations
infra/                   AWS CLI setup steps (README) and IAM policy JSON
scripts/                 data and maintenance scripts (e.g. load-live)
data/  research/         gitignored, never committed
docs/                    planning docs, scope, specs, qa
```

`engine` must not import FastAPI or any web package; `services/api` depends on `engine`, never the reverse.

### Runtime topology

- Browser loads static pages from Vercel, then calls the Lambda Function URL directly. CORS allows the production domain and `localhost:3000` by exact match and Vercel preview URLs by pattern. CORS only stops other websites' browsers; it is not abuse protection.
- The API loads the synthetic Parquet at import time; it warms the indicator cache at import only if startup stays under 3 s, otherwise lazily on the first request. The web app pings `GET /api/v1/health` on page load to wake a cold Lambda.
- Every Vercel preview calls the production API. A pull request that changes the API contract is checked against the mocks in `contracts/`, not a live backend, until it merges.
- Live mode runs only on your machine: `DATA_MODE=live` with the API bound to `127.0.0.1`; the API refuses to start in live mode if `AWS_LAMBDA_FUNCTION_NAME` or `CI` is set, or if bound to any other address (D-5).

### Build and deploy conventions

These settle the setup choices the scaffold and later lanes would otherwise invent.

- **API image**: one `services/api/Dockerfile`, built with the repo root as context, in two stages. Stage 1 runs `uv sync --frozen` and `python -m engine.synthetic --seed 42 --out /data`. Stage 2 copies the virtual environment and `/data` onto `python:3.12-slim`, adds the pinned Lambda Web Adapter, and sets `SYNTHETIC_DATA_DIR=/data`, `AWS_LWA_PORT=8000`, `AWS_LWA_READINESS_CHECK_PATH=/api/v1/health`, and uvicorn with one worker. Target image size under 500 MB. CI checks that two builds produce Parquet with the same hash.
- **Image tags and deploys**: tag every image with the git commit SHA, never `latest`. Deploy with `update-function-code --image-uri <repo>:<sha>`. An ECR lifecycle policy keeps the last 5 images. Deploys run on push to `main` only, plus a manual `workflow_dispatch` that takes a SHA for rollback. The OIDC role trusts only `repo:<owner>/<repo>:ref:refs/heads/main`.
- **Concurrency quota**: on Day 1, run `aws lambda get-account-settings`. If the account limit leaves room (AWS keeps at least 10 unreserved), reserve 5; if not, skip the reservation, rely on the budget and throttle alarms, and request a quota increase.
- **Cold start**: measure on Day 1 and record it in the README. Over 8 s, or an image over 1 GB, reopens ADR-001 (Cloud Run fallback).
- **API conventions**: all routes under `/api/v1`. FastAPI `GZipMiddleware` is on, because Function URLs do not compress responses. Validation errors use FastAPI's default 422 body; the web app maps them to the offending field (U-7). Logs are JSON lines with a request ID per call.
- **Contract flow**: `make openapi` writes `contracts/openapi.json` (sorted keys, no server URL) from the FastAPI app; `make gen-client` regenerates `packages/api-client` types from that file with openapi-typescript. Both outputs are committed. CI reruns both and fails on any diff. The BE lane owns changes to `contracts/` after the `contracts-v1` freeze, through the change process in doc 02 section 15.6.
- **Makefile targets** (CI calls only these, so agents and CI behave the same): `setup`, `dev`, `lint`, `typecheck`, `test` (oracle tests first, stop on first failure), `test-oracle`, `openapi`, `gen-client`, `data`, `build-api`, `guards`, `load-live`, `ci` (runs every check).
- **Local dev**: `make dev` runs uvicorn on `127.0.0.1:8000` and `next dev` on port 3000 together. `.env.example` documents every variable; `ALLOWED_ORIGINS` defaults to `http://localhost:3000`.
- **Version pinning**: `.nvmrc` and `.python-version` hold exact versions; `packageManager` and `engines.node` are set in the root `package.json`. `pnpm-lock.yaml` and `uv.lock` are committed, and CI installs with `--frozen-lockfile` and `--frozen`. The base image is pinned to a minor tag. Automated dependency update bots stay off in week 1. Fallbacks: Node 22 LTS if Vercel lacks Node 24, and confirm Polars and NumPy wheels exist for Python 3.12 on x86_64.
- **Guards**: `gitleaks`, the data leak guard (D-6), and the `tests/oracle/` edit guard run both in pre-commit and as a required CI job, because local hooks can be skipped. `CODEOWNERS` assigns `tests/oracle/` to you.
- **Smoke test**: `scripts/smoke.sh` calls `/api/v1/health` and one small scan against the deployed URL after every deploy.
- **Human only setup**: you create the AWS resources (by following `infra/README.md`), the Vercel project, its env vars, and the GitHub secrets. No agent holds cloud or Alpaca credentials.

### Configuration required

- `NEXT_PUBLIC_API_URL`: the Lambda Function URL (Vercel env, set for Production and Preview) or `http://127.0.0.1:8000` locally.
- `DATA_MODE`: `synthetic` (default, the only value allowed in the cloud) or `live` (localhost only).
- `SYNTHETIC_DATA_DIR`: where the API reads the generated Parquet (`/data` in the image, a local path in dev).
- `ALLOWED_ORIGINS`: comma separated exact CORS origins (production domain, `http://localhost:3000`).
- `ALLOWED_ORIGIN_REGEX`: pattern for Vercel preview URLs of this project.
- `AWS_LWA_PORT`, `AWS_LWA_READINESS_CHECK_PATH`: Lambda Web Adapter settings, baked into the image.
- `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`: local `.env` only, for `make load-live`; never in CI, the image, or the repo.
- GitHub Actions secrets/variables: `AWS_ROLE_ARN`, `AWS_REGION=ap-southeast-1`, `ECR_REPOSITORY`, `LAMBDA_FUNCTION_NAME` (no AWS access keys).

## Consequences

**Positive**:
- One language per side (TypeScript for UI, Python for numbers) and one schema source (Pydantic) keep the web app and engine in step.
- About $0 to $0.10 a month with a $1 alarm; nothing to patch or keep running between demos.
- The CV shows Next.js, TypeScript, Python, FastAPI, Docker, AWS Lambda, OIDC, and GitHub Actions, all actually used.
- The `engine` package boundary lets four agents work in parallel lanes (doc 02 section 15) and lets QA test the engine without the API.

**Negative / tradeoffs**:
- Lambda cold starts (image pull plus data load, target under 6 s) make the first request slow; the warm up ping and "warming up" state only hide it.
- Hard limits: 30 s timeout as configured, about 6 MB response payload, no persistent state; heavy runs must stay synchronous and small or move to a queue later.
- The API in Singapore adds noticeable latency for visitors in the US and Europe.
- The Function URL is public (`AuthType NONE`): someone determined can use up the concurrency slots and take the demo offline for a while. Cost stays capped by the free allowance, the budget alarm, and the throttle alarm; real protection (a CDN with a firewall) is out of scope.
- Vercel previews always talk to the production API, so contract changes are only proven against mocks until they merge.
- After the AWS Free plan's first 6 months the account must move to the Paid plan to keep the always free allowances; ECR storage costs a few cents.
- Two toolchains (pnpm and uv) and a generated client to keep fresh add setup work on Day 1.
- No database means no saved rules, run history, or server side trial log until a later spec adds one.
- Scripted CLI infrastructure is not reproducible the way Terraform is; it must be imported later to claim IaC on the CV.

**Neutral**:
- Vercel Hobby is licensed for personal, non commercial use, which matches this project and would need a plan change if that ever changed.
- Lightweight Charts requires an attribution notice in the UI or README.
- Cloud Run stays the documented fallback if Lambda packaging exceeds a 3 hour timebox on Day 1 (ADR-001).

## Follow-up

- [ ] Confirm Node 24 LTS on Vercel and Polars and NumPy wheels for Python 3.12 on x86_64 at scaffold time (fallback: Node 22 LTS).
- [ ] Day 1: check the Lambda concurrency quota (`aws lambda get-account-settings`) before reserving 5.
- [ ] Later: switch Lambda to arm64 (cheaper) once the build runs on an arm runner.
- [ ] Day 1 checks from doc 02 (task D1.6): Alpaca display terms, GitHub's 60 day scheduled workflow rule, and the Lambda 6 MB response limit.
- [ ] Measure the Lambda cold start in `ap-southeast-1` and record it in the README; if over 8 s or the image exceeds 1 GB, revisit ADR-001.
- [ ] `/audit` should record the repo layout, lane ownership, the protected `tests/oracle/` folder, and the no real data rule in root `AGENTS.md`, plus an `## Agent skills` section listing the six installed skills above and an `MCP servers:` line for shadcn/ui and TanStack.
- [ ] Connect the chosen MCP servers yourself (your MCP settings, e.g. `claude mcp add`): a shadcn/ui component server and the official TanStack docs server. Agents use them automatically once connected.

## Rationale

See [`rationale.md`](rationale.md) for the context, the options compared, and the reasoning.
