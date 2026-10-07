"""AC-1 and AC-12: the committed OpenAPI file and mocks match the models.

CI also reruns `make openapi`, `make gen-client` and `make mocks` and fails on any diff.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, TypeAdapter

from api.main import app
from engine.contracts import (
    CONTRACT_VERSION,
    IndicatorSpec,
    MetaResponse,
    NotImplementedBody,
    PortfolioResult,
    ScanResponse,
    TemplateOut,
    TradeLabResult,
)

ROOT = Path(__file__).resolve().parents[3]
MOCKS = ROOT / "contracts" / "mocks"


def test_openapi_file_is_current() -> None:
    expected = app.openapi()
    expected.pop("servers", None)
    committed = json.loads((ROOT / "contracts" / "openapi.json").read_text())
    assert committed == json.loads(json.dumps(expected))
    assert committed["info"]["version"] == CONTRACT_VERSION
    assert "servers" not in committed


def test_discriminators_are_required_in_the_schema() -> None:
    schemas = json.loads((ROOT / "contracts" / "openapi.json").read_text())["components"]["schemas"]
    assert "kind" in schemas["IndOperand"]["required"]
    assert "type" in schemas["StopPct"]["required"]
    assert "mode" in schemas["PortfolioResult"]["required"]


class Issue(BaseModel):
    type: str
    loc: list[str | int]
    msg: str
    input: Any
    ctx: dict[str, Any] | None = None


class ValidationBody(BaseModel):
    detail: list[Issue]


MODELS: dict[str, Any] = {
    "meta.json": MetaResponse,
    "indicators.json": TypeAdapter(list[IndicatorSpec]),
    "templates.json": TypeAdapter(list[TemplateOut]),
    "scan.json": ScanResponse,
    "scan.empty.json": ScanResponse,
    "backtest.portfolio.json": PortfolioResult,
    "backtest.portfolio.truncated.json": PortfolioResult,
    "backtest.trade_lab.json": TradeLabResult,
    "backtest.no_entries.json": PortfolioResult,
    "422.rule.unknown_indicator.json": ValidationBody,
    "422.rule.n_out_of_range.json": ValidationBody,
    "422.rule.too_many_conditions.json": ValidationBody,
    "422.exits.duplicate_type.json": ValidationBody,
    "422.exits.too_many_configs.json": ValidationBody,
    "422.sim.out_of_range.json": ValidationBody,
    "501.scan.json": NotImplementedBody,
}


def test_the_mock_set_is_complete() -> None:
    assert sorted(p.name for p in MOCKS.glob("*.json")) == sorted(MODELS)


@pytest.mark.parametrize("name", sorted(MODELS))
def test_each_mock_validates_against_its_model(name: str) -> None:
    model = MODELS[name]
    text = (MOCKS / name).read_text()
    if isinstance(model, TypeAdapter):
        model.validate_json(text)
    else:
        model.model_validate_json(text)


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((MOCKS / name).read_text())
    return data


def test_portfolio_counts_agree_with_the_trades() -> None:
    data = load("backtest.portfolio.json")
    trades = data["trades"]
    assert data["trades_total"] == len(trades) and not data["trades_truncated"]
    for segment in ("is", "oos"):
        seg = [t for t in trades if t["segment"] == segment]
        metrics = data["metrics"][segment]
        assert metrics["n_trades"] == len(seg)
        wins = sum(t["return_pct"] > 0 for t in seg)
        assert metrics["win_rate_pct"] == pytest.approx(wins / len(seg) * 100, abs=1e-5)


def test_truncated_mock_keeps_2000_of_more() -> None:
    data = load("backtest.portfolio.truncated.json")
    assert data["trades_truncated"] and len(data["trades"]) == 2000 < data["trades_total"]
    n_total = data["metrics"]["is"]["n_trades"] + data["metrics"]["oos"]["n_trades"]
    assert n_total == data["trades_total"]
    assert "trades_truncated" in [w["code"] for w in data["warnings"]]


def test_trade_lab_mock_covers_the_ui_states() -> None:
    data = load("backtest.trade_lab.json")
    entries = data["entries"]
    assert entries["is_count"] + entries["oos_count"] == entries["count"]
    assert (entries["random_is_count"], entries["random_oos_count"]) == (
        entries["is_count"],
        entries["oos_count"],
    )
    rows = data["rows"]
    assert len(rows) == 5
    assert any(r["strategy"]["is"]["expectancy_r"] is None for r in rows)  # a config with no stop
    assert [w["code"] for w in data["warnings"]] == ["horizon_exits_over_10pct"]
    edges = [r["edge"][s]["expectancy_pct"] for r in rows for s in ("is", "oos")]
    assert min(edges) < 0 < max(edges)  # better and worse than random
    baseline_is = [t for t in data["baseline_trades"] if t["segment"] == "is"]
    assert rows[0]["strategy"]["is"]["n_trades"] == len(baseline_is)


def test_no_entries_mock_is_all_null() -> None:
    data = load("backtest.no_entries.json")
    assert data["trades"] == [] and data["metrics"]["is"]["n_trades"] == 0
    assert data["metrics"]["is"]["cagr_pct"] is None
    assert [w["code"] for w in data["warnings"]] == ["no_entries"]
