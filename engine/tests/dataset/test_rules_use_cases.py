"""The saved rules use cases reach the repository (spec 0014 AC-1, AC-2), with no database.

`engine.api` imports `engine.data.rules` inside each call, so the deployed function never pays
`psycopg`'s import. A typo in one of those local imports would only show at runtime, and the
round trip tests that would catch it skip wherever no database is configured, which is CI. These
run everywhere: they prove the call reaches the repository and gives back what it returns.
"""

from __future__ import annotations

import uuid

import pytest

from engine import api as use_cases
from engine.contracts import Condition, IndOperand, Rule, SavedRule, ValueOperand

RULE = Rule(
    name="Delegation",
    conditions=[
        Condition(
            left=IndOperand(kind="ind", ind="close"),
            op=">",
            right=ValueOperand(kind="value", value=5),
        )
    ],
)


def test_save_rule_passes_the_rule_through(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = SavedRule(id=uuid.uuid4(), rule=RULE)
    seen: list[Rule] = []

    def fake_save(rule: Rule) -> SavedRule:
        seen.append(rule)
        return saved

    monkeypatch.setattr("engine.data.rules.save_rule", fake_save)
    assert use_cases.save_rule(RULE) is saved
    assert seen == [RULE]


def test_save_rule_keeps_the_taken_name_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """`None` is how the repository says the name is taken; the route turns it into a 409."""
    monkeypatch.setattr("engine.data.rules.save_rule", lambda _rule: None)
    assert use_cases.save_rule(RULE) is None


def test_list_rules_returns_the_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [SavedRule(id=uuid.uuid4(), rule=RULE)]
    monkeypatch.setattr("engine.data.rules.list_rules", lambda: rows)
    assert use_cases.list_rules() == rows


@pytest.mark.parametrize("deleted", [True, False])
def test_delete_rule_passes_the_id_and_the_answer(
    deleted: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    rule_id = uuid.uuid4()
    seen: list[uuid.UUID] = []

    def fake_delete(sent: uuid.UUID) -> bool:
        seen.append(sent)
        return deleted

    monkeypatch.setattr("engine.data.rules.delete_rule", fake_delete)
    assert use_cases.delete_rule(rule_id) is deleted
    assert seen == [rule_id]
