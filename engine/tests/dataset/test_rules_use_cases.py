"""The saved rules and accounts use cases reach their repositories (spec 0014, spec 0015).

`engine.api` imports `engine.data.rules` inside each call, so the deployed function never pays
`psycopg`'s import. A typo in one of those local imports would only show at runtime, and the
round trip tests that would catch it skip wherever no database is configured, which is CI. These
run everywhere: they prove the call reaches the repository and gives back what it returns.
"""

from __future__ import annotations

import uuid

import pytest

from engine import api as use_cases
from engine.contracts import Account, Condition, IndOperand, Rule, SavedRule, ValueOperand

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


OWNER = uuid.uuid4()
"""The signed in account. Every rules use case carries it now (spec 0015)."""


def test_save_rule_passes_the_rule_and_the_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = SavedRule(id=uuid.uuid4(), rule=RULE)
    seen: list[tuple[Rule, uuid.UUID]] = []

    def fake_save(rule: Rule, account_id: uuid.UUID) -> SavedRule:
        seen.append((rule, account_id))
        return saved

    monkeypatch.setattr("engine.data.rules.save_rule", fake_save)
    assert use_cases.save_rule(RULE, OWNER) is saved
    assert seen == [(RULE, OWNER)]


def test_save_rule_keeps_the_taken_name_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """`None` is how the repository says the name is taken; the route turns it into a 409."""
    monkeypatch.setattr("engine.data.rules.save_rule", lambda _rule, _account: None)
    assert use_cases.save_rule(RULE, OWNER) is None


def test_list_rules_passes_the_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    """The owner has to reach the repository, because that is where isolation lives: it is a
    `where` clause, not a filter the caller applies afterwards (spec 0015 AC-3)."""
    rows = [SavedRule(id=uuid.uuid4(), rule=RULE)]
    seen: list[uuid.UUID] = []

    def fake_list(account_id: uuid.UUID) -> list[SavedRule]:
        seen.append(account_id)
        return rows

    monkeypatch.setattr("engine.data.rules.list_rules", fake_list)
    assert use_cases.list_rules(OWNER) == rows
    assert seen == [OWNER]


@pytest.mark.parametrize("deleted", [True, False])
def test_delete_rule_passes_the_id_the_owner_and_the_answer(
    deleted: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    rule_id = uuid.uuid4()
    seen: list[tuple[uuid.UUID, uuid.UUID]] = []

    def fake_delete(sent: uuid.UUID, account_id: uuid.UUID) -> bool:
        seen.append((sent, account_id))
        return deleted

    monkeypatch.setattr("engine.data.rules.delete_rule", fake_delete)
    assert use_cases.delete_rule(rule_id, OWNER) is deleted
    assert seen == [(rule_id, OWNER)]


# ---- Accounts (spec 0015): the same proof, that each local import reaches its repository ----


def test_register_reaches_the_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    account = Account(id=OWNER, email="you@example.com")
    seen: list[tuple[str, str]] = []

    def fake_create(email: str, password: str) -> Account:
        seen.append((email, password))
        return account

    monkeypatch.setattr("engine.data.accounts.create_account", fake_create)
    assert use_cases.register("you@example.com", "a long enough password") is account
    assert seen == [("you@example.com", "a long enough password")]


def test_register_keeps_the_taken_email_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("engine.data.accounts.create_account", lambda _e, _p: None)
    assert use_cases.register("you@example.com", "a long enough password") is None


def test_sign_in_keeps_one_answer_for_both_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """`None` covers a wrong address and a wrong password alike, which is what lets the route
    send one identical 401 (spec 0015 AC-7)."""
    monkeypatch.setattr("engine.data.accounts.verify_account", lambda _e, _p: None)
    assert use_cases.sign_in("you@example.com", "a long enough password") is None


def test_account_by_id_reaches_the_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    """This is the read every gated request makes, so a typo in its local import would break
    the whole signed in surface at runtime."""
    account = Account(id=OWNER, email="you@example.com")
    monkeypatch.setattr("engine.data.accounts.account_by_id", lambda _id: account)
    assert use_cases.account_by_id(OWNER) is account


@pytest.mark.parametrize("deleted", [True, False])
def test_delete_account_passes_the_id_and_the_answer(
    deleted: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[uuid.UUID] = []

    def fake_delete(account_id: uuid.UUID) -> bool:
        seen.append(account_id)
        return deleted

    monkeypatch.setattr("engine.data.accounts.delete_account", fake_delete)
    assert use_cases.delete_account(OWNER) is deleted
    assert seen == [OWNER]
