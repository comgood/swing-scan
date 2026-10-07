"""Rule builder criteria R-1 to R-10 (doc 01 section 6.2), through the contract and the scan."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from acceptance.support import (
    Frame,
    bar_date,
    build_market,
    flat,
    ind,
    make_rule,
    random_walk_frames,
    rule_json,
    run_scan,
    ui_owed,
    val,
)
from engine.contracts import TEMPLATES, Rule, structure_key
from golden.reference import hits

SCAN = "/api/v1/scan"


def _template_rules() -> list[Rule]:
    return [t.rule for t in TEMPLATES]


# ---------------------------------------------------------------- R-1 round trip


@pytest.mark.ac("R-1")
@pytest.mark.parametrize(
    "rule",
    [
        *(t.rule.model_dump(mode="json") for t in TEMPLATES),
        rule_json(
            (ind("close", offset=3, mult=0.5), "crosses_below", ind("rs")),
            (ind("ret", n=20), ">=", val(-1.25)),
            name="  every shape  ",
        ),
    ],
)
def test_rule_json_round_trips(rule: dict[str, Any]) -> None:
    first = Rule.model_validate(rule)
    wire = first.model_dump_json()
    again = Rule.model_validate_json(wire)
    assert again == first
    assert again.model_dump_json() == wire


@pytest.mark.ac("R-1")
def test_rule_survives_the_url_after_reload() -> None:
    ui_owed("R-1 (URL encoded form reproduces the rule after reload)")


# ---------------------------------------------------------------- R-2 golden templates


@pytest.mark.ac("R-2")
@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.id)
def test_template_hits_match_the_golden_reference(template: Any) -> None:
    frames = random_walk_frames(n_tickers=24, n_bars=330, seed=7)
    market = build_market(frames)
    rule = template.rule
    rule_dict = rule.model_dump(mode="json")
    golden = {t: f.golden(t) for t, f in frames.items()}
    expected_by_bar: dict[int, set[str]] = {}
    for ticker, bars in golden.items():
        frame = frames[ticker]
        for i, hit in enumerate(hits(bars, rule_dict)):
            if hit:
                expected_by_bar.setdefault(frame.start_bar + i, set()).add(ticker)
    for bar in range(250, 331):
        got = {row.ticker for row in run_scan(rule, market, bar_date(bar)).rows}
        assert got == expected_by_bar.get(bar, set()), f"bar {bar}"


# ---------------------------------------------------------------- R-3 crosses


@pytest.mark.ac("R-3")
@pytest.mark.parametrize(
    ("op", "closes", "hit_bar"),
    [
        ("crosses_above", [9, 9, 11, 11, 11, 11], 3),
        ("crosses_below", [11, 11, 9, 9, 9, 9], 3),
    ],
)
def test_cross_is_true_only_on_the_crossing_bar(op: str, closes: list[float], hit_bar: int) -> None:
    frame = Frame(1, list(closes), list(closes), list(closes), list(closes))
    market = build_market({"AAA": frame})
    rule = make_rule((ind("close"), op, val(10)))
    for bar in range(1, len(closes) + 1):
        tickers = [r.ticker for r in run_scan(rule, market, bar_date(bar)).rows]
        assert tickers == (["AAA"] if bar == hit_bar else []), f"bar {bar}"


# ---------------------------------------------------------------- R-4 offset window


@pytest.mark.ac("R-4")
def test_highest_with_offset_one_excludes_today() -> None:
    high = [5.0, 30.0, 6.0, 7.0, 8.0, 9.0, 10.0, 50.0]
    low = [1.0] * len(high)
    close = [2.0] * len(high)
    market = build_market({"AAA": Frame(1, list(close), high, low, close)})
    rule = make_rule((ind("highest", n=5, offset=1), ">", val(0)))
    # Bar 8: bars 3..7 -> max(6, 7, 8, 9, 10) = 10. Today's 50 and bar 2's 30 are outside.
    result = run_scan(rule, market, bar_date(8))
    assert result.columns == ["highest(5)[1]"]
    assert [r.operands for r in result.rows] == [[10.0]]
    # Bar 7: bars 2..6 -> 30.
    assert [r.operands for r in run_scan(rule, market, bar_date(7)).rows] == [[30.0]]
    # Bar 5 has only 4 prior bars: invalid, so no row.
    assert run_scan(rule, market, bar_date(5)).rows == []


# ---------------------------------------------------------------- R-5 warm up


@pytest.mark.ac("R-5")
def test_warm_up_bars_are_never_hits() -> None:
    close = [10.0 + i for i in range(30)]
    market = build_market({"AAA": Frame(1, list(close), list(close), list(close), close)})
    rule = make_rule((ind("close"), ">", ind("sma", n=50)))
    for bar in range(1, 31):
        assert run_scan(rule, market, bar_date(bar)).rows == [], f"bar {bar}"


# ---------------------------------------------------------------- R-6 validation


def _cond(left: dict[str, Any], right: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"left": left, "op": ">", "right": right or val(5)}


_OK = _cond(ind("close"))

R6_CASES: list[tuple[str, dict[str, Any], list[Any], str, dict[str, Any] | None]] = [
    # (case, rule, expected loc, expected type, expected ctx subset)
    (
        "unknown indicator",
        {"name": "r", "conditions": [_cond({"kind": "ind", "ind": "macd", "n": 12})]},
        ["body", "rule", "conditions", 0, "left", "ind"],
        "literal_error",
        None,
    ),
    (
        "n above range",
        {"name": "r", "conditions": [_cond(ind("sma", n=253))]},
        ["body", "rule", "conditions", 0, "left", "n"],
        "out_of_range",
        {"min": 2, "max": 252},
    ),
    (
        "rsi n above its own range",
        {"name": "r", "conditions": [_cond(ind("rsi", n=60))]},
        ["body", "rule", "conditions", 0, "left", "n"],
        "out_of_range",
        {"min": 2, "max": 50},
    ),
    (
        "offset above 20",
        {"name": "r", "conditions": [_cond(ind("close", offset=21))]},
        ["body", "rule", "conditions", 0, "left", "offset"],
        "out_of_range",
        {"min": 0, "max": 20},
    ),
    (
        "mult below 0.1",
        {"name": "r", "conditions": [_cond(ind("close"), ind("sma", n=20, mult=0.05))]},
        ["body", "rule", "conditions", 0, "right", "ind", "mult"],
        "out_of_range",
        {"min": 0.1, "max": 10},
    ),
    (
        "nine conditions",
        {"name": "r", "conditions": [_OK] * 9},
        ["body", "rule", "conditions"],
        "out_of_range",
        {"min": 1, "max": 8},
    ),
    (
        "empty list",
        {"name": "r", "conditions": []},
        ["body", "rule", "conditions"],
        "out_of_range",
        {"min": 1, "max": 8},
    ),
]


@pytest.mark.ac("R-6")
@pytest.mark.parametrize(
    ("rule", "loc", "err_type", "ctx"),
    [c[1:] for c in R6_CASES],
    ids=[c[0] for c in R6_CASES],
)
def test_invalid_rule_returns_422_with_path_and_range(
    client: TestClient,
    rule: dict[str, Any],
    loc: list[Any],
    err_type: str,
    ctx: dict[str, Any] | None,
) -> None:
    response = client.post(SCAN, json={"rule": rule})
    assert response.status_code == 422
    errors = response.json()["detail"]
    match = [e for e in errors if e["loc"] == loc]
    assert match, f"no error at {loc}; got {[e['loc'] for e in errors]}"
    error = match[0]
    assert error["type"] == err_type
    if ctx is not None:
        assert {k: error["ctx"][k] for k in ctx} == ctx
    if err_type == "literal_error":
        assert "sma" in error["ctx"]["expected"]  # the allowed values are listed


# ---------------------------------------------------------------- R-7 rs range


@pytest.mark.ac("R-7")
def test_rs_lies_in_0_to_99_and_the_top_return_gets_99() -> None:
    frames: dict[str, Frame] = {}
    n_bars = 140
    for i in range(12):
        slope = 0.01 * (i + 1) * (-1 if i % 3 == 0 else 1)
        close = [20.0 + slope * t for t in range(n_bars)]
        frames[f"T{i:02d}"] = Frame(1, list(close), list(close), list(close), close)
    market = build_market(frames)
    rule = make_rule((ind("rs", n=126), ">=", val(0)))
    result = run_scan(rule, market, bar_date(n_bars))
    assert result.columns == ["rs(126)"]
    values = {r.ticker: r.operands[0] for r in result.rows}
    assert set(values) == set(frames)
    assert all(0 <= v <= 99 for v in values.values())
    returns = {t: f.close[-1] / f.close[-127] - 1 for t, f in frames.items()}
    assert values[max(returns, key=lambda t: returns[t])] == 99


# ---------------------------------------------------------------- R-8 UI parity


@pytest.mark.ac("R-8")
def test_builder_rows_match_the_request_json() -> None:
    ui_owed("R-8")


# ---------------------------------------------------------------- R-9 structure key


@pytest.mark.ac("R-9")
@pytest.mark.parametrize(
    ("a", "b"),
    [
        (
            rule_json((ind("close"), ">", ind("highest", n=252, offset=1))),
            rule_json((ind("close"), ">", ind("highest", n=100, offset=1)), name="other"),
        ),
        (
            rule_json((ind("close", mult=1.5), ">", val(5))),
            rule_json((ind("close", offset=4), ">", val(50))),
        ),
    ],
)
def test_structure_key_ignores_numbers(a: dict[str, Any], b: dict[str, Any]) -> None:
    assert structure_key(Rule.model_validate(a)) == structure_key(Rule.model_validate(b))


@pytest.mark.ac("R-9")
@pytest.mark.parametrize(
    "variant",
    [
        rule_json((ind("close"), ">", ind("lowest", n=252, offset=1))),  # indicator
        rule_json((ind("close"), ">=", ind("highest", n=252, offset=1))),  # operator
        rule_json((ind("close"), ">", val(5))),  # right operand kind
        rule_json(  # condition count
            (ind("close"), ">", ind("highest", n=252, offset=1)),
            (ind("close"), ">", ind("highest", n=252, offset=1)),
        ),
    ],
    ids=["indicator", "operator", "operand kind", "count"],
)
def test_structure_key_differs_on_structure(variant: dict[str, Any]) -> None:
    base = Rule.model_validate(rule_json((ind("close"), ">", ind("highest", n=252, offset=1))))
    assert structure_key(Rule.model_validate(variant)) != structure_key(base)


# ---------------------------------------------------------------- R-10 visible price filter


@pytest.mark.ac("R-10")
def test_each_template_has_a_visible_close_above_5(client: TestClient) -> None:
    templates = client.get("/api/v1/templates").json()
    assert len(templates) == 2
    for template in templates:
        conditions = template["rule"]["conditions"]
        assert any(
            c["left"]["ind"] == "close"
            and c["left"]["offset"] == 0
            and c["left"]["mult"] == 1.0
            and c["op"] == ">"
            and c["right"] == {"kind": "value", "value": 5.0}
            for c in conditions
        ), template["id"]


@pytest.mark.ac("R-10")
def test_no_hidden_price_filter() -> None:
    # A penny stock that is true on the rule must be returned when the rule has no price filter.
    penny = flat(1, 30, price=0.5, spread=0.1)
    market = build_market({"PENNY": penny})
    rule = make_rule((ind("volume"), ">", val(0)))
    assert [r.ticker for r in run_scan(rule, market, bar_date(30)).rows] == ["PENNY"]
