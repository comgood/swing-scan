# Swing Scan task runner. CI calls only these targets so agents and CI behave the same (spec 0001).
# Targets marked "later" are added by the scope feature named in their message.

SHELL := /bin/bash
export PATH := $(HOME)/.local/bin:$(PATH)

API_IMAGE ?= swing-scan-api
API_PLATFORM ?= linux/amd64

.PHONY: setup dev dev-api dev-web lint typecheck test build-web build-api smoke \
        test-oracle openapi gen-client data guards load-live ci

setup: ## Install all JS and Python dependencies from the lockfiles
	pnpm install --frozen-lockfile
	uv sync --frozen

dev: ## Run the API on 127.0.0.1:8000 and the web app on :3000 together
	$(MAKE) -j2 dev-api dev-web

dev-api:
	uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

dev-web:
	pnpm --filter web dev

lint: ## Lint the web app (Python lint arrives with the tooling feature)
	pnpm --filter web lint

typecheck: ## Typecheck the web app
	pnpm --filter web typecheck

test: ## Run the Python test suite
	uv run pytest

build-web: ## Static export of the web app into apps/web/out
	pnpm --filter web build

build-api: ## Build the Lambda container image (x86_64)
	docker build --platform $(API_PLATFORM) -f services/api/Dockerfile -t $(API_IMAGE) .

smoke: ## Smoke test a deployed API: make smoke API_URL=https://...
	scripts/smoke.sh "$(API_URL)"

test-oracle openapi gen-client data guards load-live ci:
	@echo "make $@ is not implemented yet (see docs/scope/scope.md, features 2, 3, 6, 7 and 14)"; exit 1
