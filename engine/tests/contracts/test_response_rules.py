"""AC-14: nulls not NaN, finite floats only, caps on long lists, no CAGR in trade mode."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from engine.contracts import (
    PortfolioMetrics,
    PortfolioResult,
    ScanResponse,
    TradeLabResult,
    TradeMetrics,
)

MOCKS = Path(__file__).resolve().parents[3] / "contracts" / "mocks"


def metrics(**overrides: Any) -> dict[str, Any]:
    fields = dict.fromkeys(PortfolioMetrics.model_fields)
    return {**fields, "n_trades": 3, **overrides}


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
def test_a_non_finite_float_raises_at_construction(bad: float) -> None:
    with pytest.raises(ValidationError) as caught:
        PortfolioMetrics(**metrics(profit_factor=bad))
    assert caught.value.errors()[0]["type"] == "finite_number"


def test_undefined_numbers_serialise_as_null() -> None:
    dumped = json.loads(PortfolioMetrics(**metrics()).model_dump_json())
    assert dumped["profit_factor"] is None


def test_trade_mode_metrics_have_no_cagr_drawdown_or_sharpe() -> None:
    assert {"cagr_pct", "max_dd_pct", "sharpe"}.isdisjoint(TradeMetrics.model_fields)


def portfolio_mock() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((MOCKS / "backtest.portfolio.json").read_text())
    return data


def test_equity_is_capped_at_500_points() -> None:
    data = portfolio_mock()
    data["equity"] = data["equity"] * 3
    with pytest.raises(ValidationError) as caught:
        PortfolioResult.model_validate(data)
    assert caught.value.errors()[0]["loc"] == ("equity",)


def test_trades_are_capped_at_2000() -> None:
    data: dict[str, Any] = json.loads((MOCKS / "backtest.trade_lab.json").read_text())
    data["baseline_trades"] = data["baseline_trades"] * 20
    with pytest.raises(ValidationError) as caught:
        TradeLabResult.model_validate(data)
    assert caught.value.errors()[0]["loc"] == ("baseline_trades",)


def test_scan_rows_are_capped_at_500() -> None:
    data: dict[str, Any] = json.loads((MOCKS / "scan.json").read_text())
    data["rows"] = data["rows"] * 13
    with pytest.raises(ValidationError):
        ScanResponse.model_validate(data)


def test_oos_start_must_match_the_assumptions() -> None:
    data = portfolio_mock()
    data["oos_start"] = "2021-01-04"
    with pytest.raises(ValidationError):
        PortfolioResult.model_validate(data)


def test_split_serialises_is_under_its_json_key() -> None:
    dumped = PortfolioResult.model_validate(portfolio_mock()).model_dump(mode="json")
    assert set(dumped["metrics"]) == {"is", "oos"}
