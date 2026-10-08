"""AC-6: routes validate the full request, answer 501 until built, and serve static data."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api import state
from api.main import app
from engine.contracts import CONTRACT_VERSION, TEMPLATES

client = TestClient(app, raise_server_exceptions=False)
RULE = TEMPLATES[0].rule.model_dump(mode="json")


def configs(count: int) -> list[dict[str, Any]]:
    return [{"name": f"C{i}", "exits": [{"type": "stop_pct", "pct": 8}]} for i in range(count)]


def test_scan_without_a_market_is_501(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(state, "market", None)
    res = client.post("/api/v1/scan", json={"rule": RULE})
    assert res.status_code == 501
    assert "feature 7" in res.json()["detail"]


@pytest.mark.parametrize("count", [1, 2, 6])
def test_backtest_without_a_market_is_501(count: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(state, "market", None)
    res = client.post("/api/v1/backtest", json={"rule": RULE, "configs": configs(count)})
    assert res.status_code == 501
    assert "feature 7" in res.json()["detail"]


def _fixture_market(monkeypatch: pytest.MonkeyPatch) -> None:
    from engine.data.fixtures import FrameSpec, make_market

    closes = [4.0, 4.0, 6.0, 6.5, 7.0, 7.5]
    monkeypatch.setattr(state, "market", make_market({"AAA": FrameSpec(1, closes)}))


@pytest.mark.parametrize("count", [2, 6])
def test_trade_mode_is_501_naming_feature_12(count: int, monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture_market(monkeypatch)
    res = client.post("/api/v1/backtest", json={"rule": RULE, "configs": configs(count)})
    assert res.status_code == 501
    assert "feature 12" in res.json()["detail"]


def test_a_feature_11_exit_is_501_naming_feature_11(monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture_market(monkeypatch)
    trail = [{"name": "T", "exits": [{"type": "trail_pct", "pct": 10}]}]
    res = client.post("/api/v1/backtest", json={"rule": RULE, "configs": trail})
    assert res.status_code == 501
    assert "trail_pct" in res.json()["detail"]
    assert "feature 11" in res.json()["detail"]


def test_one_config_runs_the_portfolio_backtest(monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture_market(monkeypatch)
    price = {"name": "price", "conditions": [RULE["conditions"][2]]}  # close > 5
    res = client.post("/api/v1/backtest", json={"rule": price, "configs": configs(1)})
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "portfolio"
    assert [t["exit_reason"] for t in body["trades"]] == ["end_of_test"]


def test_an_end_after_the_data_is_422_range_outside_data(monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture_market(monkeypatch)  # bars 1 to 6: 2020-01-02 to 2020-01-09
    body = {"rule": RULE, "configs": configs(1), "sim": {"end": "2021-01-04"}}
    res = client.post("/api/v1/backtest", json=body)
    assert res.status_code == 422
    (error,) = res.json()["detail"]
    assert error["type"] == "range_outside_data"
    assert error["loc"] == ["body", "sim", "end"]
    assert error["ctx"] == {"min": "2020-01-02", "max": "2020-01-09"}


def test_seven_configs_is_422_not_501() -> None:
    res = client.post("/api/v1/backtest", json={"rule": RULE, "configs": configs(7)})
    assert res.status_code == 422
    issue = res.json()["detail"][0]
    assert issue["loc"] == ["body", "configs"]
    assert issue["ctx"] == {"min": 1, "max": 6}


def test_422_uses_fastapis_default_body_with_loc_and_ctx() -> None:
    bad = {
        "rule": {
            **RULE,
            "conditions": [
                {**RULE["conditions"][0], "left": {"kind": "ind", "ind": "rsi", "n": 99}}
            ],
        }
    }
    res = client.post("/api/v1/scan", json=bad)
    assert res.status_code == 422
    issue = res.json()["detail"][0]
    assert set(issue) >= {"type", "loc", "msg", "input", "ctx"}
    assert issue["loc"] == ["body", "rule", "conditions", 0, "left", "n"]
    assert issue["ctx"] == {"min": 2, "max": 50}


@pytest.mark.parametrize("as_of", ["2024/01/02", "yesterday", 1704153600])
def test_malformed_as_of_is_422(as_of: object) -> None:
    res = client.post("/api/v1/scan", json={"rule": RULE, "as_of": as_of})
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "as_of"]


def test_indicators_come_from_the_registry() -> None:
    body = client.get("/api/v1/indicators").json()
    assert len(body) == 14
    assert {
        "name": "rs",
        "label": "Relative strength vs the benchmark",
        "windowed": True,
        "n_min": 2,
        "n_max": 252,
        "n_default": 126,
    } in body


def test_templates_are_served() -> None:
    body = client.get("/api/v1/templates").json()
    assert [t["id"] for t in body] == ["breakout_52w", "pullback_ema21"]


def test_meta_has_the_contract_version_and_no_data_yet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(state, "market", None)
    body = client.get("/api/v1/meta").json()
    assert body == {"contract_version": CONTRACT_VERSION, "data": None, "oos_start": None}


def test_a_stray_not_implemented_error_stays_a_500(monkeypatch: pytest.MonkeyPatch) -> None:
    from engine import api as use_cases
    from engine.data.fixtures import FrameSpec, make_market

    def broken(*_: object) -> None:
        raise NotImplementedError("a real bug")

    monkeypatch.setattr(state, "market", make_market({"AAA": FrameSpec(1, [1.0, 2.0])}))
    monkeypatch.setattr(use_cases, "scan_timed", broken)
    assert client.post("/api/v1/scan", json={"rule": RULE}).status_code == 500


def test_with_a_market_loaded_scan_answers_200(monkeypatch: pytest.MonkeyPatch) -> None:
    from engine.data.fixtures import FrameSpec, make_market

    market = make_market({"AAA": FrameSpec(1, [4.0, 6.0]), "BBB": FrameSpec(1, [4.0, 4.0])})
    monkeypatch.setattr(state, "market", market)
    rule = {"name": "price", "conditions": [{**RULE["conditions"][2]}]}  # close > 5
    res = client.post("/api/v1/scan", json={"rule": rule})
    assert res.status_code == 200
    body = res.json()
    assert body["as_of"] == "2020-01-03"
    assert [row["ticker"] for row in body["rows"]] == ["AAA"]
    assert body["rows"][0]["new_today"] is True
