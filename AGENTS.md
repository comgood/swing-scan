# Swing Scan

A $0 swing trading scanner and backtester (portfolio project, not investment advice). pnpm + uv monorepo: `apps/web` (Next.js), `services/api` (FastAPI), `engine` (trading logic), `packages/api-client` (generated types).

## Stack

- **Language / Runtime**: TypeScript (strict) on Node 24 · Python 3.12 (uv)
- **Framework**: Next.js App Router, static export on Vercel Hobby · FastAPI + Pydantic v2 in a Lambda container (`ap-southeast-1`)
- **Key dependencies**: Polars + NumPy (engine), Tailwind + shadcn/ui, TanStack Query/Table, openapi-typescript + openapi-fetch, Lightweight Charts
- **Package manager**: pnpm (JS workspaces) + uv (Python workspace), one root `Makefile` for both
- **No database, no auth, no background jobs.** Source of truth: [spec 0001](docs/specs/0001-stack-architecture/index.md)

## Build approach

Tracer Bullet (one thin, real path through every layer first, then thicken it one strand at a time).

## Commands

```bash
make setup      # install from lockfiles (pnpm --frozen-lockfile, uv sync --frozen)
make dev        # API on 127.0.0.1:8000 + web on :3000
make build-web  # static export into apps/web/out
make hooks      # once per clone: install the pre-commit hooks
make lint && make typecheck
make format     # apply Prettier and Ruff fixes
make test       # pytest (oracle tests first once they exist)
make ci         # every check CI runs, in one command
```

Run every check through `make`; CI calls only `make` targets. Targets that print "not implemented yet" arrive with later scope features.

## Specs

Stored in `docs/specs/`. Format: `docs/specs/NNNN-title/index.md`. Criteria IDs (D, R, S, B, X, U) live in `docs/01-market-research-and-product-spec.md`; lanes and coordination in `docs/02-technical-design-and-roadmap.md` section 15.

## Rules

- **Clean Architecture, mapped to the spec layout.** Domain: `engine/{indicators,rules,exits,sim,baseline,metrics}` (pure logic; Polars and NumPy allowed, no I/O, no web code). Application: `engine.api` use cases (`scan`, `backtest`), thin orchestrators. Infrastructure: `engine/{data,synthetic}`, Parquet and vendor I/O. Presentation: `services/api` routers and `apps/web`.
- Dependencies point inward: `engine` never imports FastAPI, Starlette or uvicorn (`engine/tests/test_engine_boundary.py`); `services/api` depends on `engine`, never the reverse.
- Cross boundary data uses Pydantic models or plain DTOs; domain objects never reach the web app. Domain and use cases are unit tested without mocking infrastructure.
- Folders: engine by domain module, API by router, web by feature (`apps/web/src/features/<name>/`).
- Types: TypeScript `strict`; Python fully hinted, `mypy --strict` on `engine` and `services/api`.
- Tests: owner oracles in `tests/oracle/` define correctness and run first; builders add unit tests with each change; QA writes `tests/acceptance/` from criteria and contracts only.
- Lane ownership (doc 02 §15.2) is enforced by `CODEOWNERS`. Agents never edit root `AGENTS.md`; propose changes in the PR description. QA never opens builder implementation folders.
- **Never:** commit `data/`, `research/`, `*.parquet` or keys · call vendor APIs in CI or record cassettes · edit `tests/oracle/` · run `aws`/`terraform` write commands · add a service without an ADR · use `eval`/`exec` in rule compilation · special case an exit outside `step()` · change the random baseline seed default without an ADR.
- Contract changes go through a `contract-change` PR (doc 02 §15.6) with the regenerated `api-client`, updated mocks and owner approval.

## Tooling

ESLint + Prettier (web), Ruff lint + format and mypy strict (config in root `pyproject.toml`). Pre-commit (`.pre-commit-config.yaml`) runs lint, format, gitleaks, the data leak guard (D-6) and the `tests/oracle/` guard (`scripts/guards/`); typecheck runs in `make typecheck` and CI. CI (`.github/workflows/ci.yml`) on every PR: lint, typecheck, test, web build, guards, and an `oracle-approved` label check for `tests/oracle/`. Vitest, oracle first ordering and the OpenAPI to TS diff join CI with features 3, 5 and 6.

## Git

- integration: on
- branch prefix: feat/
- commit: per-milestone

## Agent skills

- [vercel-react-best-practices](.claude/skills/vercel-react-best-practices/): `vercel-labs/agent-skills`, React and Next.js performance
- [nextjs-app-router-patterns](.claude/skills/nextjs-app-router-patterns/): `wshobson/agents`, App Router structure and data fetching
- [tailwind-design-system](.claude/skills/tailwind-design-system/): `wshobson/agents`, Tailwind v4 tokens and components
- [aws-serverless](.claude/skills/aws-serverless/): `aws/agent-toolkit-for-aws`, Lambda container, Function URL, cold starts
- [aws-iam](.claude/skills/aws-iam/): `aws/agent-toolkit-for-aws`, OIDC deploy role and IAM policies
- [python-testing-patterns](.claude/skills/python-testing-patterns/): `wshobson/agents`, pytest fixtures and test structure
- [fastapi](.agents/skills/fastapi/): `fastapi/fastapi`, FastAPI and Pydantic conventions for `services/api`
- [shadcn](.agents/skills/shadcn/): `shadcn-ui/ui`, adding and styling shadcn/ui components in `apps/web`
- [multi-stage-dockerfile](.agents/skills/multi-stage-dockerfile/): `github/awesome-copilot`, multi stage image patterns for `services/api/Dockerfile`
- [pnpm](.agents/skills/pnpm/): `antfu/skills`, pnpm workspaces, lockfile and dependency config
- [ruff](.agents/skills/ruff/): `astral-sh/claude-code-plugins`, Ruff lint and format usage

MCP servers: shadcn/ui (recommended), TanStack docs (recommended)

## Context files

- [apps/web/AGENTS.md](apps/web/AGENTS.md) (Next.js version warning, FE lane conventions)
- [engine/AGENTS.md](engine/AGENTS.md) (trading logic package, layers and invariants)
- [services/api/AGENTS.md](services/api/AGENTS.md) (FastAPI presentation layer, Lambda image)
- [packages/api-client/AGENTS.md](packages/api-client/AGENTS.md) (generated OpenAPI types, never hand edited)
- [tests/AGENTS.md](tests/AGENTS.md) (oracle, acceptance and golden suites, QA rules)

_Drafted by /audit from the repo, worth a quick human pass. Edit freely: once a line stops matching this draft, later runs treat it as curated and will flag rather than overwrite it._
