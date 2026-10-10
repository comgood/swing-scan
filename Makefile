# Swing Scan task runner. CI calls only these targets so agents and CI behave the same (spec 0001).
# Targets marked "later" are added by the scope feature named in their message.

SHELL := /bin/bash
export PATH := $(HOME)/.local/bin:$(PATH)

API_IMAGE ?= swing-scan-api
API_PLATFORM ?= linux/amd64
API_BUILD_FLAGS ?=

.PHONY: setup setup-py setup-web dev dev-api dev-web lint format typecheck test test-fast test-py test-py-fast \
        test-web test-acceptance test-acceptance-fast test-slow hooks guards build-web \
        build-api build-api-local smoke smoke-image test-oracle openapi gen-client mocks contracts contracts-check data data-check load-live dev-live ci

setup: setup-web setup-py ## Install all JS and Python dependencies from the lockfiles

setup-py: ## Install the Python environment from uv.lock (CI: jobs that need no JS)
	uv sync --frozen

setup-web: ## Install the JS workspace from pnpm-lock.yaml (CI: jobs that need no Python)
	pnpm install --frozen-lockfile

dev: ## Run the API on 127.0.0.1:8000 and the web app on :3000 together
	$(MAKE) -j2 dev-api dev-web

dev-api:
	uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

dev-web:
	pnpm --filter web dev

lint: ## Lint and check formatting for web and Python
	pnpm --filter web lint
	pnpm --filter web format:check
	uv run ruff check .
	uv run ruff format --check .

format: ## Apply formatting to web and Python
	pnpm --filter web format
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Typecheck the web app and API client (tsc) and Python (mypy strict)
	pnpm --filter @swing-scan/api-client typecheck
	pnpm --filter web typecheck
	uv run mypy

# The Python suite in two halves so CI can run them in parallel jobs; `-m "not slow"` drops
# the timing and budget tests, which CI runs on main instead (spec 0009 assumed decision 11).
UNIT_TESTS := engine/tests services/api/tests
QA_TESTS := tests/golden tests/acceptance
NOT_SLOW := -m "not slow"

test: test-py test-acceptance test-web ## The whole suite: Python unit, QA golden and acceptance, then web

test-fast: test-py-fast test-acceptance-fast test-web ## Every test CI runs on a pull request (no slow timing tests)

test-py: ## The Python unit suites (engine and API), slow timing tests included
	uv run pytest $(UNIT_TESTS)

test-py-fast: ## The Python unit suites without the slow timing tests (CI, per pull request)
	uv run pytest $(UNIT_TESTS) $(NOT_SLOW)

test-web: ## The web Vitest suite (MSW on by default)
	pnpm --filter web test

test-acceptance: ## QA acceptance and golden suites; only IDs marked required in status.yaml can fail
	uv run pytest $(QA_TESTS) -rfEX

test-acceptance-fast: ## The same, without the slow timing tests (CI, per pull request)
	uv run pytest $(QA_TESTS) -rfEX $(NOT_SLOW)

test-slow: ## Only the slow timing and budget tests, with every duration and the printed numbers
	uv run pytest -m slow -rA -s --durations=0

openapi: ## Write contracts/openapi.json from the FastAPI app (spec 0002)
	uv run python scripts/export_openapi.py

gen-client: ## Regenerate the TypeScript types in packages/api-client from contracts/openapi.json
	pnpm --filter @swing-scan/api-client gen

mocks: ## Regenerate contracts/mocks/ from the seeded mock builder
	uv run python scripts/make_mocks.py

contracts: openapi gen-client mocks ## Regenerate every contract artefact after a model change

contracts-check: contracts ## CI: fail if a generated contract file is stale (AC-1, AC-12)
	@if [ -n "$$(git status --porcelain -- contracts packages/api-client)" ]; then \
		echo "Generated contract files are stale. Run 'make contracts' and commit the result:"; \
		git status --porcelain -- contracts packages/api-client; \
		git --no-pager diff --stat -- contracts packages/api-client; \
		exit 1; \
	fi

build-web: ## Static export of the web app into apps/web/out
	pnpm --filter web build

build-api: ## Build the Lambda container image (x86_64); CI runs it on every PR
	docker build --platform $(API_PLATFORM) $(API_BUILD_FLAGS) -f services/api/Dockerfile -t $(API_IMAGE) .

# Not the deploy image: an arm64 copy of the Dockerfile so Apple Silicon can smoke test locally.
build-api-local: ## Build an arm64 copy of the API image as $(API_IMAGE):local-arm64
	@tmp="$$(mktemp)"; trap 'rm -f "$$tmp"' EXIT; \
	sed 's#--platform=linux/amd64#--platform=linux/arm64#g' services/api/Dockerfile > "$$tmp"; \
	docker build --platform linux/arm64 -f "$$tmp" -t $(API_IMAGE):local-arm64 .

hooks: ## Install the pre-commit hooks into .git/hooks (run once per clone)
	uv run pre-commit install

guards: ## Data leak guard on every tracked file, plus gitleaks over the files
	uv run python scripts/guards/data_leak.py --all
	uv run pre-commit run gitleaks --all-files

smoke: ## Smoke test a deployed API: make smoke API_URL=https://...
	scripts/smoke.sh "$(API_URL)"

smoke-image: ## Run a built API image and smoke test it: make smoke-image [API_IMAGE=swing-scan-api:local-arm64]
	scripts/smoke_image.sh "$(API_IMAGE)"

ci: lint typecheck test build-web contracts-check data-check guards ## Every check CI runs, in one command

SEED ?= 42

data: ## Generate the synthetic market into data/synthetic (gitignored): make data SEED=42
	uv run python -m engine.synthetic --seed $(SEED) --out data/synthetic

data-check: ## CI: build the seed 42 market twice in a temp folder, same hashes, D-1 to D-3 hold
	uv run python scripts/check_synthetic.py

UNIVERSE ?= research/sp500.csv
LIVE_DIR ?= data/live

load-live: ## Local only: Alpaca daily bars into data/live (gitignored); keys from env, else .env
	@if [ -z "$$ALPACA_API_KEY_ID" ] && [ -f .env ]; then set -a; . ./.env; set +a; fi; \
	uv run python -m engine.live --universe $(UNIVERSE) --out $(LIVE_DIR)

dev-live: ## Local only: run the API in live mode on 127.0.0.1 with the web app (D-5)
	DATA_MODE=live SYNTHETIC_DATA_DIR=$(LIVE_DIR) $(MAKE) dev

test-oracle: ## Run the owner approved oracles (not in the default testpaths)
	uv run pytest tests/oracle
