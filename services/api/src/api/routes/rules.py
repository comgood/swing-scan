"""Saved rules (spec 0014): save one, list them, delete one. 501 anywhere but your machine.

Two gates, both in `saved_rules_problems`: no `DATABASE_URL` means there is nothing to write
to, and the D-5 host rules mean a `DATABASE_URL` set on Lambda by accident still cannot open an
unauthenticated write endpoint. Accounts (scope feature 22) are what open this up.

The check runs once at import, not per request: it is a pure function of `sys.argv` and the
environment, and neither changes while the process lives.
"""

from __future__ import annotations

import os
import sys
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from engine import api as use_cases
from engine.api import NotYetImplemented
from engine.contracts import NotImplementedBody, Rule, SavedRule

from ..settings import saved_rules_problems

router = APIRouter()

ENABLED = not saved_rules_problems(sys.argv, os.environ)
"""False on the deployed API, in CI, and locally until a `DATABASE_URL` is configured."""

NOT_HERE: dict[int | str, dict[str, Any]] = {
    501: {"model": NotImplementedBody, "description": "Not available here"}
}


def _require_enabled() -> None:
    if not ENABLED:
        raise NotYetImplemented(21, "Saving rules")


@router.post("/rules", response_model=SavedRule, responses=NOT_HERE)
def create_rule(rule: Rule) -> SavedRule:
    """Save a rule under its own name. A name already taken is a 409, never an overwrite."""
    _require_enabled()
    saved = use_cases.save_rule(rule)
    if saved is None:
        raise HTTPException(status_code=409, detail=f"A rule named {rule.name!r} is already saved.")
    return saved


@router.get("/rules", response_model=list[SavedRule], responses=NOT_HERE)
def saved_rules() -> list[SavedRule]:
    """Every saved rule, whole: the list is what loads one back into the builder."""
    _require_enabled()
    return use_cases.list_rules()


@router.delete("/rules/{rule_id}", status_code=204, responses=NOT_HERE)
def remove_rule(rule_id: UUID) -> Response:
    """Delete one saved rule. Unknown id is a 404, so a stale list says so rather than lying."""
    _require_enabled()
    if not use_cases.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="No saved rule has that id.")
    return Response(status_code=204)
