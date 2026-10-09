"""Every R-6 case through `POST /scan`: a 422 with the bad field's `loc` and the allowed range
or values in `ctx` (spec 0008, AC-12).

A right side operand is a tagged union on `kind`, so Pydantic puts the tag in its `loc`
(`right.ind.n`, `right.value.value`); the left side is a plain `IndOperand` (`left.n`). The
API keeps the tag by owner ruling 2026-10-09; the web app strips it (PR #60).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api import state
from api.main import app
from engine.data.fixtures import FrameSpec, make_market

client = TestClient(app, raise_server_exceptions=False)
CLOSE: dict[str, Any] = {"kind": "ind", "ind": "close", "n": None, "offset": 0, "mult": 1}
FIVE: dict[str, Any] = {"kind": "value", "value": 5}
CONDITIONS = "body", "rule", "conditions"


@pytest.fixture(autouse=True)
def _market(monkeypatch: pytest.MonkeyPatch) -> None:
    """A loaded market, so a 422 is proven to come before any scan work (not a 501)."""
    monkeypatch.setattr(state, "market", make_market({"AAA": FrameSpec(1, [10.0] * 3)}))


def cond(
    left: dict[str, Any] | None = None, op: str = ">", right: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {"left": left or CLOSE, "op": op, "right": right or FIVE}


def _only_issue(conditions: list[dict[str, Any]]) -> dict[str, Any]:
    res = client.post("/api/v1/scan", json={"rule": {"name": "custom", "conditions": conditions}})
    assert res.status_code == 422
    (issue,) = res.json()["detail"]
    return dict(issue)


INDICATORS = (
    "'open', 'high', 'low', 'close', 'volume', 'sma', 'ema', 'rsi', 'atr', 'highest', "
    "'lowest', 'avg_volume', 'ret' or 'rs'"
)


@pytest.mark.parametrize(
    ("conditions", "loc"),
    [
        ([cond(left={"kind": "ind", "ind": "macd", "n": 12})], (0, "left", "ind")),
        ([cond(), cond(right={"kind": "ind", "ind": "vwap"})], (1, "right", "ind", "ind")),
    ],
    ids=["left", "right"],
)
def test_an_unknown_indicator_lists_every_allowed_name(
    conditions: list[dict[str, Any]], loc: tuple[object, ...]
) -> None:
    issue = _only_issue(conditions)
    assert issue["type"] == "literal_error"
    assert tuple(issue["loc"]) == (*CONDITIONS, *loc)
    assert issue["ctx"] == {"expected": INDICATORS}


@pytest.mark.parametrize(
    ("operand", "side", "bounds"),
    [
        ({"ind": "sma", "n": 1}, "left", (2, 252)),
        ({"ind": "highest", "n": 253}, "left", (2, 252)),
        ({"ind": "rsi", "n": 51}, "left", (2, 50)),
        ({"ind": "rs", "n": 300}, "right", (2, 252)),
        ({"ind": "ema", "n": 0}, "right", (2, 252)),
    ],
)
def test_n_out_of_range_names_the_side_and_that_indicators_range(
    operand: dict[str, Any], side: str, bounds: tuple[int, int]
) -> None:
    bad = {"kind": "ind", **operand}
    rows = [cond(), cond(), cond(left=bad) if side == "left" else cond(right=bad)]
    issue = _only_issue(rows)  # row 3, so the index in `loc` is checked too
    assert issue["type"] == "out_of_range"
    tag = ("ind",) if side == "right" else ()
    assert tuple(issue["loc"]) == (*CONDITIONS, 2, side, *tag, "n")
    assert issue["ctx"] == {"min": bounds[0], "max": bounds[1]}
    assert issue["msg"] == f"must be between {bounds[0]} and {bounds[1]}"


@pytest.mark.parametrize("offset", [21, -1])
def test_offset_outside_0_to_20(offset: int) -> None:
    issue = _only_issue([cond(right={"kind": "ind", "ind": "sma", "n": 5, "offset": offset})])
    assert issue["type"] == "out_of_range"
    assert tuple(issue["loc"]) == (*CONDITIONS, 0, "right", "ind", "offset")
    assert issue["ctx"] == {"min": 0, "max": 20}


@pytest.mark.parametrize("mult", [0.0, 10.5])
def test_mult_outside_0_1_to_10(mult: float) -> None:
    issue = _only_issue([cond(left={**CLOSE, "mult": mult})])
    assert issue["type"] == "out_of_range"
    assert tuple(issue["loc"]) == (*CONDITIONS, 0, "left", "mult")
    assert issue["ctx"] == {"min": 0.1, "max": 10}


@pytest.mark.parametrize("count", [0, 9])
def test_an_empty_list_or_nine_conditions(count: int) -> None:
    issue = _only_issue([cond()] * count)
    assert issue["type"] == "out_of_range"
    assert tuple(issue["loc"]) == CONDITIONS
    assert issue["ctx"] == {"min": 1, "max": 8}


def test_eight_custom_conditions_is_the_limit_and_scans() -> None:
    rows = [cond(left={"kind": "ind", "ind": "close", "offset": k}) for k in range(8)]
    res = client.post("/api/v1/scan", json={"rule": {"name": "eight", "conditions": rows}})
    assert res.status_code == 200


def test_n_on_a_price_field_and_a_missing_n() -> None:
    issue = _only_issue([cond(left={**CLOSE, "n": 5})])
    assert (issue["type"], tuple(issue["loc"])) == ("n_not_allowed", (*CONDITIONS, 0, "left", "n"))
    issue = _only_issue([cond(right={"kind": "ind", "ind": "atr"})])
    assert issue["type"] == "n_required"
    assert tuple(issue["loc"]) == (*CONDITIONS, 0, "right", "ind", "n")
    assert issue["ctx"] == {"ind": "atr", "min": 2, "max": 252}


def test_an_unknown_operator_and_operand_kind() -> None:
    issue = _only_issue([cond(op="==")])
    assert (issue["type"], tuple(issue["loc"])) == ("literal_error", (*CONDITIONS, 0, "op"))
    assert "'crosses_above'" in issue["ctx"]["expected"]
    issue = _only_issue([cond(right={"kind": "macro", "value": 5})])
    assert (issue["type"], tuple(issue["loc"])) == ("union_tag_invalid", (*CONDITIONS, 0, "right"))
    assert issue["ctx"]["expected_tags"] == "'ind', 'value'"
