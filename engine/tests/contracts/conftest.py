from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError


def ind(name: str, n: int | None = None, **extra: Any) -> dict[str, Any]:
    operand: dict[str, Any] = {"kind": "ind", "ind": name, **extra}
    if n is not None:
        operand["n"] = n
    return operand


def cond(left: dict[str, Any], right: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"left": left, "op": ">", "right": right or {"kind": "value", "value": 5}}


def rule(*conditions: dict[str, Any]) -> dict[str, Any]:
    return {"name": "Test", "conditions": list(conditions) or [cond(ind("close"))]}


def errors_of(model: type[BaseModel], data: Any) -> list[dict[str, Any]]:
    with pytest.raises(ValidationError) as caught:
        model.model_validate(data)
    return [dict(e) for e in caught.value.errors()]


def only_error(model: type[BaseModel], data: Any) -> dict[str, Any]:
    errors = errors_of(model, data)
    assert len(errors) == 1, errors
    return errors[0]
