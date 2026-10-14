# Verify: stack & architecture · spec 0001 · updated 2026-10-06
_Steps derived from the scope feature 1 Done when line (spec 0001 is a decision spec with no ACs). `/check verify` runs these; `/test` locks the durable ones._

## Commands
- [ ] `make setup` → pnpm and uv install from the lockfiles with no errors → Done when: runs locally
- [ ] `make test` → 4 passed (health, CORS allow, CORS reject, engine has no web imports) → Done when: runs locally
- [ ] `make lint typecheck build-web` → all pass; `apps/web/out/index.html` exists → Done when: web runs as a static export
- [ ] `make build-api` (Docker running) → image builds for linux/amd64; note the size (target under 500 MB) → Done when: API packaged for Lambda

## UI / manual
- [ ] `make dev`, open `http://localhost:3000` → status line reads "API reachable (data mode: synthetic, version 0.1.0)" → Done when: web and API connected locally
- [ ] After the steps in `infra/README.md`: `make smoke API_URL=<function-url>` → "smoke test passed" → Done when: API reachable on its free tier host
- [ ] Open the Vercel production (and one preview) URL → status line reads "API reachable" (proves CORS for prod and the preview pattern) → Done when: web reachable on its free tier host
- [ ] Record the first cold request time to `/api/v1/health` → under 8 s, else revisit ADR-001 → spec 0001 Follow-up

## Done when coverage
- Stack captured in a spec → spec 0001 (accepted in /architect)
- Web app and API run locally → setup, test, build, and `make dev` steps
- Both reachable on free tier hosts → smoke test and Vercel URL steps

# Verify: coding standards & tooling (scope feature 2) · spec 0001 · updated 2026-10-06
_Steps derived from the scope feature 2 Done when line. `/check verify` runs these; `/test` locks the durable ones._

## Commands
- [ ] `make hooks` once, then `make ci` → lint (ESLint, Prettier, Ruff), typecheck (tsc, mypy strict), 4 tests, web build and gitleaks all pass → Done when: CI runs lint, typecheck and tests
- [ ] `mkdir -p data && echo a,b > data/x.csv && git add -f data/x.csv && git commit -m t` → blocked by "data leak guard (D-6)"; then `git rm --cached data/x.csv` → D-6 (price data)
- [ ] Commit a file containing `PK` followed by 18 capital letters or digits → blocked by the data leak guard → D-6 (API key)
- [ ] Stage any file under `tests/oracle/` and commit → blocked by the oracle guard; `ORACLE_EDIT_OK=1 git commit` passes → oracle protection

## GitHub (after the first push)
- [ ] Open a PR → the `CI complete` check passes (it gates `lint, typecheck`, `python tests, contracts, data`, `acceptance, golden`, `web tests, build`, `api image` and `guards`) → Done when: CI on every PR
- [ ] A PR touching `tests/oracle/` without the `oracle-approved` label → the guards job fails; adding the label reruns it green
- [ ] Replace `@OWNER` in `.github/CODEOWNERS` with your GitHub username

## Done when coverage
- Root `AGENTS.md` reflects the real stack and lanes → written by `/audit` (commit 90392f8)
- CI runs lint, typecheck and tests on every PR → `make ci` step and the first PR step
- A commit with price data or an API key is blocked (D-6) → the data and key steps
