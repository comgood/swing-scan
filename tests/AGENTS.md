# tests

## Overview

Repo level test suites that check the engine and API from the outside: owner approved oracles, QA acceptance tests and naive golden references. Unit tests live next to their package instead (`engine/tests/`, `services/api/tests/`).

## Key files

| Folder | Owns |
|---|---|
| `oracle/` | Owner written correctness oracles (protected, owner only) |
| `acceptance/` | QA tests written from criteria IDs and contracts; `status.yaml` marks each ID `pending` or `required` |
| `golden/` | QA's naive loop based reference implementations (R-2, B-14 to B-16, S-3) |
| `../apps/web/tests/acceptance/` | QA's Vitest UI acceptance tests (R-1, R-8, R-10, S-1, X-3, X-4, X-9, U-1 to U-8), run by the web suite |

## Commands

```bash
make test-oracle   # the 26 owner approved oracles; all pass since features 9, 11 and 12 landed
uv run pytest tests/acceptance
make test-acceptance   # golden + acceptance, with the gate summary
```

## Conventions

- `oracle/` is protected: agents never edit it. QA drafts fixtures in an `oracle-draft` PR; only the owner's `oracle-approved` label lets CI accept changes. Locally the pre-commit oracle guard blocks the commit; the owner commits with `ORACLE_EDIT_OK=1 git commit ...`.
- QA writes from `docs/01*`, `docs/specs/` and `contracts/` only, and never opens builder implementation folders.
- Acceptance tests call `engine.api.scan`, `engine.api.backtest` and FastAPI's `TestClient`, never engine internals.
- CI blocks only on `required` IDs. QA flips an ID to `required` once it passes on `main`; builders never edit QA files.
- A disputed criterion goes to `docs/qa/ac-questions.md#<ID>`; the test stays `pending` until the ruling.
- Every acceptance test carries `@pytest.mark.ac("<ID>")`; a missing or unknown ID aborts collection. `test_traceability.py` fails when `status.yaml`, `docs/qa/traceability.md` and the markers fall out of step.
- Tests that need a real market use the session `generated_api` fixture (`conftest.py`, `GeneratedApi` in `support.py`): the seed 42 market generated in a subprocess, since CI has no `data/`. The plain session `client` has no market loaded.
- UI acceptance tests emulate `next/navigation` with `apps/web/tests/acceptance/navigation.ts`; a page that reads `useSearchParams` needs it.
- The timing and budget tests (S-4, B-13, X-7, AC-11) carry `@pytest.mark.slow`, declared in root `pyproject.toml`. `make test` and `make test-acceptance` run them; CI drops them per pull request (`make test-acceptance-fast`, `-m "not slow"`) and runs them in its own job on `main`, a manual dispatch, or a `run-slow` label (`make test-slow`). A required ID behind a slow mark therefore blocks on `main`, not on the pull request.
- `oracle/` is not in the default `testpaths`, so the oracles never turn `make test` red; run them with `make test-oracle`.

## Related specs

- [0001 stack & architecture](../docs/specs/0001-stack-architecture/index.md)

_Drafted by /audit from the repo, worth a quick human pass. Edit freely: once a line stops matching this draft, later runs treat it as curated and will flag rather than overwrite it._
