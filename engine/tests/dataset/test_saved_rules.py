"""Saved rules against a real Postgres (spec 0014, AC-1, AC-2, AC-4); skipped with none (AC-10)."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest

from engine.contracts import Condition, IndOperand, Rule, SavedRule, ValueOperand
from engine.data.rules import delete_rule, list_rules, save_rule

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="no DATABASE_URL: saved rules run on your own machine, and your run is their evidence",
)


def _ind(ind: str, n: int | None = None, offset: int = 0, mult: float = 1.0) -> IndOperand:
    return IndOperand.model_validate(
        {"kind": "ind", "ind": ind, "n": n, "offset": offset, "mult": mult}
    )


def _every_operand_shape(name: str) -> Rule:
    """One rule carrying every operand shape the contract allows (AC-2)."""
    return Rule(
        name=name,
        conditions=[
            # A price field, which takes no `n`, against a fixed number.
            Condition(left=_ind("close"), op=">", right=ValueOperand(kind="value", value=5)),
            # `rs` is the one indicator with an `n` default (126), so this proves a defaulted
            # `n` round trips as the value the contract filled in, not as null.
            Condition(left=_ind("rs"), op=">", right=ValueOperand(kind="value", value=1)),
            # An explicit `n`, and an indicator on the right.
            Condition(left=_ind("close"), op=">", right=_ind("sma", 50)),
            # A non default offset and a non default mult.
            Condition(left=_ind("close"), op=">", right=_ind("highest", 252, offset=1)),
            Condition(left=_ind("volume"), op=">", right=_ind("avg_volume", 50, mult=1.5)),
        ],
    )


@pytest.fixture
def name() -> Iterator[str]:
    """A name no other run shares, and its rows gone afterwards however the test ended."""
    unique = f"test {uuid.uuid4().hex[:8]}"
    yield unique
    for saved in list_rules():
        if saved.rule.name.lower().startswith(unique):
            delete_rule(saved.id)


def _find(rule_id: uuid.UUID) -> SavedRule | None:
    return next((saved for saved in list_rules() if saved.id == rule_id), None)


def test_a_rule_loads_back_equal_field_for_field(name: str) -> None:
    rule = _every_operand_shape(name)
    saved = save_rule(rule)
    assert saved is not None
    loaded = _find(saved.id)
    assert loaded is not None
    # Dumps, so a field added to the contract later fails here rather than comparing by identity.
    assert loaded.rule.model_dump() == rule.model_dump()
    assert [c.left.ind for c in loaded.rule.conditions] == [c.left.ind for c in rule.conditions]


def test_the_same_name_in_another_case_is_refused(name: str) -> None:
    first = save_rule(_every_operand_shape(name))
    assert first is not None
    assert save_rule(_every_operand_shape(name.upper())) is None
    assert [saved.id for saved in list_rules() if saved.rule.name.lower() == name] == [first.id]


def test_delete_removes_it_and_an_unknown_id_is_false(name: str) -> None:
    saved = save_rule(_every_operand_shape(name))
    assert saved is not None
    assert delete_rule(saved.id) is True
    assert _find(saved.id) is None
    assert delete_rule(uuid.uuid4()) is False
