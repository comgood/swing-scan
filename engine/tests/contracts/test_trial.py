"""AC-9: trial keys ignore numbers and names, and pair keys ignore exit order."""

from __future__ import annotations

from datetime import date
from typing import Any

from engine.contracts import ExitConfig, Rule, entries_hash, pair_key, structure_key

from .conftest import cond, ind


def make(*conditions: dict[str, Any], name: str = "R") -> Rule:
    return Rule.model_validate({"name": name, "conditions": list(conditions)})


BREAKOUT = make(cond(ind("close"), ind("highest", 252, offset=1)))


def test_rules_that_differ_only_in_numbers_or_name_share_a_structure_key() -> None:
    shorter = make(cond(ind("close"), ind("highest", 100, offset=3, mult=1.2)), name="Other")
    assert structure_key(BREAKOUT) == structure_key(shorter)
    a = make(cond(ind("close"), {"kind": "value", "value": 5}))
    b = make(cond(ind("close"), {"kind": "value", "value": 10}))
    assert structure_key(a) == structure_key(b)


def test_structure_key_differs_on_indicator_operator_kind_or_count() -> None:
    base = structure_key(BREAKOUT)
    assert structure_key(make(cond(ind("close"), ind("sma", 50)))) != base
    lt = make({"left": ind("close"), "op": "<", "right": ind("highest", 252)})
    assert structure_key(lt) != base
    assert structure_key(make(cond(ind("close"), {"kind": "value", "value": 1}))) != base
    two = make(cond(ind("close"), ind("highest", 252)), cond(ind("close"), ind("highest", 252)))
    assert structure_key(two) != base


def config(name: str, *exits: dict[str, Any]) -> ExitConfig:
    return ExitConfig.model_validate({"name": name, "exits": list(exits)})


def test_pair_key_ignores_names_and_exit_order() -> None:
    a = config("A", {"type": "stop_pct", "pct": 8}, {"type": "time", "bars": 10})
    b = config("B", {"type": "time", "bars": 10}, {"type": "stop_pct", "pct": 8})
    renamed = make(cond(ind("close"), ind("highest", 252, offset=1)), name="Renamed")
    assert pair_key(BREAKOUT, a) == pair_key(renamed, b)


def test_pair_key_changes_with_any_number() -> None:
    a = config("A", {"type": "stop_pct", "pct": 8})
    assert pair_key(BREAKOUT, a) != pair_key(BREAKOUT, config("A", {"type": "stop_pct", "pct": 9}))
    other_rule = make(cond(ind("close"), ind("highest", 251, offset=1)))
    assert pair_key(BREAKOUT, a) != pair_key(other_rule, a)


def test_keys_are_sha256_hex() -> None:
    key = structure_key(BREAKOUT)
    assert len(key) == 64 and int(key, 16) >= 0


def test_entries_hash_is_order_independent() -> None:
    entries = [("AAA", date(2024, 1, 2)), ("BBB", date(2024, 1, 3))]
    assert entries_hash(entries) == entries_hash(list(reversed(entries)))
    assert entries_hash(entries) != entries_hash(entries[:1])
