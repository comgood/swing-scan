# tests

## Overview

Repo level test suites that check the engine and API from the outside: owner approved oracles, QA acceptance tests and naive golden references. Unit tests live next to their package instead (`engine/tests/`, `services/api/tests/`).

## Key files

| Folder | Owns |
|---|---|
| `oracle/` | Owner written correctness oracles (protected, owner only) |
| `acceptance/` | QA tests written from criteria IDs and contracts; `status.yaml` marks each ID `pending` or `required` |
| `golden/` | QA's naive loop based reference implementations (R-2, B-14 to B-16, S-3) |

## Commands

```bash
make test-oracle   # oracles only, stop on first failure (arrives with scope feature 6)
uv run pytest tests/acceptance
```

## Conventions

- `oracle/` is protected: agents never edit it. QA drafts fixtures in an `oracle-draft` PR; only the owner's `oracle-approved` label lets CI accept changes. Locally the pre-commit oracle guard blocks the commit; the owner commits with `ORACLE_EDIT_OK=1 git commit ...`.
- QA writes from `docs/01*`, `docs/specs/` and `contracts/` only, and never opens builder implementation folders.
- Acceptance tests call `engine.api.scan`, `engine.api.backtest` and FastAPI's `TestClient`, never engine internals.
- CI blocks only on `required` IDs. QA flips an ID to `required` once it passes on `main`; builders never edit QA files.
- A disputed criterion goes to `docs/qa/ac-questions.md#<ID>`; the test stays `pending` until the ruling.

## Related specs

- [0001 stack & architecture](../docs/specs/0001-stack-architecture/index.md)

_Drafted by /audit from the repo, worth a quick human pass. Edit freely: once a line stops matching this draft, later runs treat it as curated and will flag rather than overwrite it._
