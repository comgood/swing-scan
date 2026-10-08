"""Acceptance suite wiring: the `ac` marker, the pending or required gate, and shared fixtures.

Every test here carries `@pytest.mark.ac("<ID>", ...)` naming the doc 01 criteria it checks.
Tests whose IDs are all `pending` in `status.yaml` become non strict xfails: they run and
report, but never fail the build. A test with any `required` ID blocks CI when it fails.
Meta tests that check the harness itself carry `@pytest.mark.harness` instead and always block.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from acceptance.gate import MUST_IDS, StatusFileError, load_status
from acceptance.support import GeneratedApi

_HERE = Path(__file__).parent
_IDS_KEY = pytest.StashKey[dict[str, tuple[str, ...]]]()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "ac(*ids): doc 01 criterion IDs this acceptance test checks (gate input)"
    )
    config.addinivalue_line(
        "markers", "harness: a meta test of the acceptance harness itself, always required"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    try:
        status = load_status()
    except (StatusFileError, OSError) as exc:
        raise pytest.UsageError(str(exc)) from exc

    ids_by_node: dict[str, tuple[str, ...]] = {}
    for item in items:
        if _HERE not in Path(str(item.path)).parents:
            continue
        if item.get_closest_marker("harness") is not None:
            continue
        ids = tuple(i for mark in item.iter_markers("ac") for i in mark.args)
        if not ids:
            raise pytest.UsageError(
                f"{item.nodeid}: every acceptance test needs @pytest.mark.ac('<ID>') "
                "or @pytest.mark.harness"
            )
        unknown = [i for i in ids if i not in MUST_IDS]
        if unknown:
            raise pytest.UsageError(f"{item.nodeid}: unknown criterion IDs {unknown}")
        ids_by_node[item.nodeid] = ids
        if all(status[i] == "pending" for i in ids):
            item.add_marker(
                pytest.mark.xfail(
                    reason=f"pending {', '.join(ids)} (tests/acceptance/status.yaml)",
                    strict=False,
                )
            )
    config.stash[_IDS_KEY] = ids_by_node


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, exitstatus: int, config: pytest.Config
) -> None:
    ids_by_node = config.stash.get(_IDS_KEY, {})
    if not ids_by_node:
        return
    outcome_by_id: dict[str, set[str]] = {}
    for key in ("passed", "failed", "xfailed", "xpassed", "error", "skipped"):
        for report in terminalreporter.stats.get(key, []):
            nodeid = getattr(report, "nodeid", "")
            when = getattr(report, "when", "call")
            if nodeid not in ids_by_node or (key == "passed" and when != "call"):
                continue
            for crit in ids_by_node[nodeid]:
                outcome_by_id.setdefault(crit, set()).add(key)

    ready = sorted(
        (i for i, seen in outcome_by_id.items() if seen == {"xpassed"}),
        key=MUST_IDS.index,
    )
    failing_required = sorted(
        (i for i, seen in outcome_by_id.items() if seen & {"failed", "error"}),
        key=MUST_IDS.index,
    )
    status = load_status()
    n_required = sum(1 for s in status.values() if s == "required")
    terminalreporter.section("acceptance gate")
    terminalreporter.write_line(
        f"{n_required} required, {len(status) - n_required} pending "
        f"of {len(status)} MUST criteria (tests/acceptance/status.yaml)"
    )
    if failing_required:
        terminalreporter.write_line(f"required and failing: {', '.join(failing_required)}")
    if ready:
        terminalreporter.write_line(
            f"pending and fully passing (flip to required once green on main): {', '.join(ready)}"
        )


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """The real FastAPI app, in process."""
    from api.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def generated_api(tmp_path_factory: pytest.TempPathFactory) -> GeneratedApi:
    data_dir = tmp_path_factory.mktemp("synthetic")
    subprocess.run(
        [sys.executable, "-m", "engine.synthetic", "--seed", "42", "--out", str(data_dir)],
        check=True,
        capture_output=True,
        timeout=300,
    )
    return GeneratedApi(data_dir, tmp_path_factory.mktemp("api"))
