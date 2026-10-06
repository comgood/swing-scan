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
