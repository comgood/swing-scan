"""AC-2: every R-6 case fails with a path and the allowed range or values."""

from __future__ import annotations

import typing
from typing import Any, get_args

import annotated_types
import pytest
from pydantic import BaseModel

import engine.contracts as contracts
from engine.contracts import INDICATOR_SPECS, Rule

from .conftest import cond, ind, only_error, rule


def test_unknown_indicator_lists_the_allowed_values() -> None:
    error = only_error(Rule, rule(cond(ind("macd", 12))))
    assert error["type"] == "literal_error"
    assert error["loc"] == ("conditions", 0, "left", "ind")
    assert "'rs'" in error["ctx"]["expected"]


@pytest.mark.parametrize(("name", "n"), [("sma", 1), ("sma", 253), ("rsi", 51), ("rs", 300)])
def test_n_out_of_range_reports_that_indicators_bounds(name: str, n: int) -> None:
    error = only_error(Rule, rule(cond(ind(name, n))))
    spec = INDICATOR_SPECS[name]  # type: ignore[index]
    assert error["type"] == "out_of_range"
    assert error["loc"] == ("conditions", 0, "left", "n")
    assert error["ctx"] == {"min": spec.n_min, "max": spec.n_max}


def test_missing_n_is_reported_at_n_with_the_range() -> None:
    error = only_error(Rule, rule(cond(ind("close"), ind("ema"))))
    assert error["type"] == "n_required"
    # A right operand is a tagged union, so Pydantic puts the tag in the path; it still ends at n.
    assert error["loc"] == ("conditions", 0, "right", "ind", "n")
    assert error["ctx"]["min"] == 2 and error["ctx"]["max"] == 252


def test_n_on_a_price_field_is_rejected_at_n() -> None:
    error = only_error(Rule, rule(cond(ind("close", 14))))
    assert error["type"] == "n_not_allowed"
    assert error["loc"] == ("conditions", 0, "left", "n")


@pytest.mark.parametrize(
    ("field", "value", "bounds"),
    [
        ("offset", -1, (0, 20)),
        ("offset", 21, (0, 20)),
        ("mult", 0.05, (0.1, 10)),
        ("mult", 11, (0.1, 10)),
    ],
)
def test_offset_and_mult_ranges(field: str, value: float, bounds: tuple[float, float]) -> None:
    error = only_error(Rule, rule(cond({"kind": "ind", "ind": "close", field: value})))
    assert error["type"] == "out_of_range"
    assert error["loc"] == ("conditions", 0, "left", field)
    assert error["ctx"] == {"min": bounds[0], "max": bounds[1]}


@pytest.mark.parametrize("count", [0, 9])
def test_condition_count_must_be_1_to_8(count: int) -> None:
    data = {"name": "Test", "conditions": [cond(ind("close"))] * count}
    error = only_error(Rule, data)
    assert error["type"] == "out_of_range"
    assert error["loc"] == ("conditions",)
    assert error["ctx"] == {"min": 1, "max": 8}


def test_unknown_kind_tag_lists_the_allowed_tags() -> None:
    error = only_error(Rule, rule(cond(ind("close"), {"kind": "pct", "value": 5})))
    assert error["type"] == "union_tag_invalid"
    assert error["loc"] == ("conditions", 0, "right")
    assert "'ind'" in error["ctx"]["expected_tags"]


def test_missing_kind_tag() -> None:
    error = only_error(Rule, rule(cond(ind("close"), {"value": 5})))
    assert error["type"] == "union_tag_not_found"
    assert error["loc"] == ("conditions", 0, "right")


def test_unknown_key_is_rejected() -> None:
    error = only_error(Rule, {**rule(), "min_price": 5})
    assert error["type"] == "extra_forbidden"


@pytest.mark.parametrize("name", ["", "   ", "x" * 41])
def test_rule_name_is_1_to_40_characters_after_trimming(name: str) -> None:
    error = only_error(Rule, {**rule(), "name": name})
    assert error["type"] == "out_of_range"
    assert error["loc"] == ("name",)


def test_rule_name_is_trimmed() -> None:
    assert Rule.model_validate({**rule(), "name": "  Breakout  "}).name == "Breakout"


def test_value_operand_must_be_finite() -> None:
    error = only_error(Rule, rule(cond(ind("close"), {"kind": "value", "value": float("inf")})))
    assert error["type"] == "finite_number"


# ---- No ranged field uses Pydantic's ge/le (they report only the failing side) ----------

FORBIDDEN = (
    annotated_types.Ge,
    annotated_types.Le,
    annotated_types.Gt,
    annotated_types.Lt,
    annotated_types.MinLen,
    annotated_types.MaxLen,
)


def _metadata(annotation: Any) -> list[Any]:
    found: list[Any] = []
    if typing.get_origin(annotation) is typing.Annotated:
        found.extend(annotation.__metadata__)
    for arg in get_args(annotation):
        found.extend(_metadata(arg))
    return found


def _contract_models() -> list[type[BaseModel]]:
    return [
        value
        for value in vars(contracts).values()
        if isinstance(value, type) and issubclass(value, BaseModel) and value is not BaseModel
    ]


def test_no_contract_field_uses_ge_le_or_length_constraints() -> None:
    models = _contract_models()
    assert len(models) > 30
    offenders = [
        f"{model.__name__}.{name}"
        for model in models
        for name, info in model.model_fields.items()
        for item in [*info.metadata, *_metadata(info.annotation)]
        if isinstance(item, FORBIDDEN)
    ]
    assert offenders == []
