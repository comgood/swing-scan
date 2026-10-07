"""AC-15: use case stubs and the contracts package's import boundary."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from engine import api
from engine.contracts import TEMPLATES, BacktestRequest, ScanRequest
from engine.data.fixtures import FrameSpec, make_market

CONTRACTS = Path(api.__file__).parent / "contracts"
ALLOWED = {"pydantic", "pydantic_core", "polars"}


def test_contracts_import_only_stdlib_pydantic_and_polars() -> None:
    imported: set[str] = set()
    for path in CONTRACTS.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
    outside = imported - ALLOWED - set(sys.stdlib_module_names)
    assert outside == set()


@pytest.fixture
def market() -> object:
    return make_market({"AAA": FrameSpec(1, [10.0, 11.0])})


def test_scan_stub_names_feature_8(market: object) -> None:
    with pytest.raises(api.NotYetImplemented) as caught:
        api.scan(ScanRequest(rule=TEMPLATES[0].rule), market)  # type: ignore[arg-type]
    assert caught.value.feature == 8


def test_backtest_stub_names_feature_9(market: object) -> None:
    request = BacktestRequest.model_validate(
        {
            "rule": TEMPLATES[0].rule.model_dump(),
            "configs": [{"name": "A", "exits": [{"type": "time"}]}],
        }
    )
    with pytest.raises(api.NotYetImplemented) as caught:
        api.backtest(request, market)  # type: ignore[arg-type]
    assert caught.value.feature == 9


def test_not_yet_implemented_is_not_a_not_implemented_error() -> None:
    assert not issubclass(api.NotYetImplemented, NotImplementedError)
