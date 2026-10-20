"""Saved rules against a real Postgres (spec 0014 AC-1/AC-2/AC-4, spec 0015 AC-3); skipped
with none (AC-10).

A rule belongs to an account now, so these create a throwaway account, work as it, and delete
it afterwards. That makes the cascade part of the cleanup rather than a separate chore, and it
is what lets the isolation test below be a real two account check against the real database.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest

from engine.contracts import Condition, IndOperand, Rule, SavedRule, ValueOperand
from engine.data.accounts import create_account, delete_account
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


def _throwaway_account() -> uuid.UUID:
    """An account this run owns, with an address no other run shares."""
    account = create_account(f"test-{uuid.uuid4().hex}@example.invalid", "a long enough password")
    assert account is not None
    return account.id


@pytest.fixture
def owner() -> Iterator[uuid.UUID]:
    """An account for this test, deleted afterwards however the test ended.

    Deleting it is the whole cleanup: `rules.account_id` cascades, so no rule can outlive the
    account that owned it and nothing is left behind even on a failure.
    """
    account_id = _throwaway_account()
    yield account_id
    delete_account(account_id)


@pytest.fixture
def name() -> str:
    """A rule name no other run shares."""
    return f"test {uuid.uuid4().hex[:8]}"


def _find(rule_id: uuid.UUID, owner: uuid.UUID) -> SavedRule | None:
    return next((saved for saved in list_rules(owner) if saved.id == rule_id), None)


def test_a_rule_loads_back_equal_field_for_field(name: str, owner: uuid.UUID) -> None:
    rule = _every_operand_shape(name)
    saved = save_rule(rule, owner)
    assert saved is not None
    loaded = _find(saved.id, owner)
    assert loaded is not None
    # Dumps, so a field added to the contract later fails here rather than comparing by identity.
    assert loaded.rule.model_dump() == rule.model_dump()
    assert [c.left.ind for c in loaded.rule.conditions] == [c.left.ind for c in rule.conditions]


def test_the_same_name_in_another_case_is_refused(name: str, owner: uuid.UUID) -> None:
    first = save_rule(_every_operand_shape(name), owner)
    assert first is not None
    assert save_rule(_every_operand_shape(name.upper()), owner) is None
    assert [s.id for s in list_rules(owner) if s.rule.name.lower() == name] == [first.id]


def test_delete_removes_it_and_an_unknown_id_is_false(name: str, owner: uuid.UUID) -> None:
    saved = save_rule(_every_operand_shape(name), owner)
    assert saved is not None
    assert delete_rule(saved.id, owner) is True
    assert _find(saved.id, owner) is None
    assert delete_rule(uuid.uuid4(), owner) is False


# ---- Accounts and isolation against the real database (spec 0015) --------------------------


def test_two_accounts_may_each_use_the_same_rule_name(name: str, owner: uuid.UUID) -> None:
    """Uniqueness is per account now, so the global index 0001 created had to go (AC-6)."""
    other = _throwaway_account()
    try:
        assert save_rule(_every_operand_shape(name), owner) is not None
        assert save_rule(_every_operand_shape(name), other) is not None
    finally:
        delete_account(other)


def test_one_account_cannot_see_or_delete_another_s_rules(name: str, owner: uuid.UUID) -> None:
    """AC-3 against the real database: the isolation is a `where` clause, so the wrong owner
    gets an empty list and a delete that matches nothing, not somebody else's row."""
    other = _throwaway_account()
    try:
        mine = save_rule(_every_operand_shape(name), owner)
        assert mine is not None
        assert list_rules(other) == []
        assert delete_rule(mine.id, other) is False
        # Still there, so the refused delete really did nothing.
        assert _find(mine.id, owner) is not None
    finally:
        delete_account(other)


def test_deleting_an_account_cascades_its_rules(name: str) -> None:
    """AC-9: the database enforces it, so no code path can delete an account and leave rows."""
    doomed = _throwaway_account()
    saved = save_rule(_every_operand_shape(name), doomed)
    assert saved is not None
    assert delete_account(doomed) is True
    assert list_rules(doomed) == []
    assert delete_account(doomed) is False
