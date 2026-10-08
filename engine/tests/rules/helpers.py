"""Small builders for rule tests."""

from __future__ import annotations

from engine.contracts import Condition, IndName, IndOperand, Op, Rule, ValueOperand


def ind(name: IndName, n: int | None = None, offset: int = 0, mult: float = 1.0) -> IndOperand:
    return IndOperand(kind="ind", ind=name, n=n, offset=offset, mult=mult)


def val(value: float) -> ValueOperand:
    return ValueOperand(kind="value", value=value)


def rule(*conditions: tuple[IndOperand, Op, IndOperand | ValueOperand]) -> Rule:
    return Rule(
        name="test",
        conditions=[Condition(left=a, op=op, right=b) for a, op, b in conditions],
    )
