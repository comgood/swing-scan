"""AC-5: requests round trip, and the canonical form writes every field in field order."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from engine.contracts import (
    TEMPLATES,
    BacktestRequest,
    ExitConfig,
    Rule,
    ScanRequest,
    SimParams,
)

from .conftest import cond, ind, rule

ALL_EXITS = [
    {"type": "stop_pct"},
    {"type": "stop_atr"},
    {"type": "target"},
    {"type": "trail_pct"},
    {"type": "close_below_ma"},
    {"type": "time"},
]

CANONICAL: list[BaseModel] = [
    *(t.rule for t in TEMPLATES),
    ScanRequest.model_validate({"rule": TEMPLATES[1].rule.model_dump(), "as_of": "2025-06-30"}),
    ScanRequest.model_validate({"rule": rule(cond(ind("rs"), ind("rsi", 14, offset=3, mult=1.5)))}),
    ExitConfig.model_validate({"name": "All six", "exits": ALL_EXITS}),
    BacktestRequest.model_validate(
        {
            "rule": TEMPLATES[0].rule.model_dump(),
            "configs": [
                {"name": "A", "exits": ALL_EXITS},
                {"name": "B", "exits": [{"type": "time"}]},
            ],
            "sim": {"start": "2021-01-04", "end": "2025-12-31", "seed": 7},
        }
    ),
    SimParams(),
]


@pytest.mark.parametrize("model", CANONICAL, ids=lambda m: type(m).__name__)
def test_round_trip_is_equal_and_byte_stable(model: BaseModel) -> None:
    wire = model.model_dump_json()
    again = type(model).model_validate_json(wire)
    assert again == model
    assert again.model_dump_json() == wire


def test_canonical_form_writes_every_field_in_field_order() -> None:
    dumped = json.loads(ScanRequest.model_validate({"rule": rule()}).model_dump_json())
    assert list(dumped) == ["rule", "as_of"]
    assert dumped["as_of"] is None
    operand = dumped["rule"]["conditions"][0]["left"]
    assert list(operand) == ["kind", "ind", "n", "offset", "mult"]


def test_non_canonical_input_becomes_canonical_on_first_parse() -> None:
    first = Rule.model_validate(rule(cond(ind("close"), ind("rs"))))
    assert first.conditions[0].right.n == 126  # type: ignore[union-attr]
    wire = first.model_dump_json()
    assert '"n":126' in wire
    assert Rule.model_validate_json(wire).model_dump_json() == wire
