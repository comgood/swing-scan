"""Trial keys: hashes that count how many rule and exit variants a user has tried (R-9).

Canonical JSON is `model_dump(mode="json")` written with `sort_keys=True` and
`separators=(",", ":")`, hashed with SHA-256 and returned as hex.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import date
from typing import Any

from .exits import ExitConfig
from .rule import IndOperand, Rule


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def structure_key(rule: Rule) -> str:
    """Equal for rules that differ only in numbers or name; the condition count is implied."""
    shape = [
        [c.left.ind, c.op, c.right.ind if isinstance(c.right, IndOperand) else "value"]
        for c in rule.conditions
    ]
    return _sha256(canonical_json(shape))


def pair_key(rule: Rule, config: ExitConfig) -> str:
    """Equal exactly when the rule and config match, ignoring names and the order of exits."""
    exits = sorted((e.model_dump(mode="json") for e in config.exits), key=lambda e: e["type"])
    payload = {
        "rule": [c.model_dump(mode="json") for c in rule.conditions],
        "config": exits,
    }
    return _sha256(canonical_json(payload))


def entries_hash(entries: Iterable[tuple[str, date]]) -> str:
    """Hash of the sorted `ticker|YYYY-MM-DD` lines, joined by newlines."""
    lines = sorted(f"{ticker}|{day.isoformat()}" for ticker, day in entries)
    return _sha256("\n".join(lines))
