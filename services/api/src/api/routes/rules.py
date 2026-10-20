"""Saved rules (specs 0014, 0015): save one, list them, delete one. 501 anywhere but your
machine, and 401 until you sign in.

A rule belongs to an account now, so every statement is scoped to the owner the signed cookie
resolved to, never to anything the caller sends. Isolation is a `where` clause rather than a
filter applied afterwards, so the failure mode is an empty list, not somebody else's rules.

The three gates live in `saved_rules_problems` and are shared with the auth routes, so the two
surfaces cannot drift apart: a rule you cannot sign in to own would be unreachable anyway.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from engine import api as use_cases
from engine.contracts import Account, NotImplementedBody, Rule, SavedRule

from ..auth import current_account

router = APIRouter()

NOT_HERE: dict[int | str, dict[str, Any]] = {
    501: {"model": NotImplementedBody, "description": "Not available here"}
}

SignedIn = Annotated[Account, Depends(current_account)]
"""Resolving this is what enforces the gates: 501 where accounts do not run, then 401, then
the lookup proving the account still exists."""


@router.post("/rules", response_model=SavedRule, responses=NOT_HERE)
def create_rule(rule: Rule, account: SignedIn) -> SavedRule:
    """Save a rule under its own name. A name you already used is a 409, never an overwrite.

    The owner comes from `account`, never from the body, so there is no request that writes a
    rule onto somebody else. Uniqueness is per account, so two accounts may each have a "Foo".
    """
    saved = use_cases.save_rule(rule, account.id)
    if saved is None:
        raise HTTPException(status_code=409, detail=f"A rule named {rule.name!r} is already saved.")
    return saved


@router.get("/rules", response_model=list[SavedRule], responses=NOT_HERE)
def saved_rules(account: SignedIn) -> list[SavedRule]:
    """Your saved rules, whole: the list is what loads one back into the builder."""
    return use_cases.list_rules(account.id)


@router.delete("/rules/{rule_id}", status_code=204, responses=NOT_HERE)
def remove_rule(rule_id: UUID, account: SignedIn) -> Response:
    """Delete one of your saved rules. Unknown id is a 404, so a stale list says so.

    Another account's rule id is also a 404, not a 403: a 403 would confirm that the rule
    exists, which is the disclosure AC-3 closes.
    """
    if not use_cases.delete_rule(rule_id, account.id):
        raise HTTPException(status_code=404, detail="No saved rule has that id.")
    return Response(status_code=204)
