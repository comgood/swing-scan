"""`POST /scan` on a loaded market: the `as_of` 422, the scan log line and warm start
(spec 0005, AC-6 to AC-8)."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api import state
from api.main import app
from engine.contracts import TEMPLATES, Market
from engine.data.fixtures import FrameSpec, bar_date, make_market

client = TestClient(app, raise_server_exceptions=False)
BREAKOUT = TEMPLATES[0].rule.model_dump(mode="json")
PRICE = {"name": "price", "conditions": [BREAKOUT["conditions"][2]]}  # close > 5


@pytest.fixture
def market(monkeypatch: pytest.MonkeyPatch) -> Market:
    loaded = make_market({"AAA": FrameSpec(1, [4.0, 6.0, 7.0]), "BBB": FrameSpec(1, [3.0] * 3)})
    monkeypatch.setattr(state, "market", loaded)
    return loaded


def _scan_lines(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "api.scan"]


@pytest.mark.usefixtures("market")
def test_a_weekend_as_of_is_a_422_with_the_data_range() -> None:
    res = client.post("/api/v1/scan", json={"rule": PRICE, "as_of": "2020-01-04"})
    assert res.status_code == 422
    (issue,) = res.json()["detail"]
    assert issue["type"] == "as_of_not_session"
    assert issue["loc"] == ["body", "as_of"]
    assert issue["ctx"] == {"min": "2020-01-02", "max": bar_date(3).isoformat()}
    assert issue["input"] == "2020-01-04"


@pytest.mark.usefixtures("market")
def test_a_scan_writes_one_json_line(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="api.scan"):
        res = client.post("/api/v1/scan", json={"rule": PRICE})
    assert res.status_code == 200
    body = res.json()
    assert [row["ticker"] for row in body["rows"]] == ["AAA"]
    assert body["rows"][0]["chg_pct"] == pytest.approx(100 * (7 / 6 - 1))
    (line,) = _scan_lines(caplog)
    assert set(line) == {"event", "duration_ms", "n_conditions", "n_rows", "cache", "as_of"}
    assert line["n_conditions"] == 1
    assert line["n_rows"] == 1
    assert line["cache"] in {"warm", "cold"}
    assert line["as_of"] == bar_date(3).isoformat()


@pytest.mark.usefixtures("market")
def test_a_422_writes_no_scan_line(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="api.scan"):
        client.post("/api/v1/scan", json={"rule": PRICE, "as_of": "2020-01-04"})
        client.post("/api/v1/scan", json={"rule": {"name": "x", "conditions": []}})
    assert _scan_lines(caplog) == []


def test_a_501_writes_no_scan_line(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(state, "market", None)
    with caplog.at_level(logging.INFO, logger="api.scan"):
        assert client.post("/api/v1/scan", json={"rule": PRICE}).status_code == 501
    assert _scan_lines(caplog) == []


def test_loading_a_market_warms_the_templates(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = make_market({"AAA": FrameSpec(1, [10.0] * 5)})
    monkeypatch.setattr(state, "read_market", lambda: fixture)
    monkeypatch.setattr(state, "market", state.load_market())
    with caplog.at_level(logging.INFO, logger="api.scan"):
        for template in TEMPLATES:
            rule = template.rule.model_dump(mode="json")
            assert client.post("/api/v1/scan", json={"rule": rule}).status_code == 200
    assert [line["cache"] for line in _scan_lines(caplog)] == ["warm", "warm"]


def test_a_missing_dataset_loads_no_market(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing() -> Market:
        raise FileNotFoundError("no dataset")

    monkeypatch.setattr(state, "read_market", missing)
    assert state.load_market() is None
