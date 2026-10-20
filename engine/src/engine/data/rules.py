"""Saved rules in Postgres (spec 0014): the rule travels as one `jsonb` column.

Infrastructure, so it lives here beside the market store and not in `services/api`. The whole
`Rule` is stored as the contract produced it, which is why condition order survives (a JSON
array is ordered), why a defaulted `n` round trips unchanged, and why a new contract field needs
no migration. The database owns identity (one name, case insensitive) and nothing else; `Rule`
stays the only validator.
"""

from __future__ import annotations

import uuid
from typing import cast

import psycopg

from engine.contracts import Rule, SavedRule

from ._db import DATABASE_URL_ENV, configured, connect

__all__ = ["DATABASE_URL_ENV", "configured", "delete_rule", "list_rules", "save_rule"]


def save_rule(rule: Rule, account_id: uuid.UUID) -> SavedRule | None:
    """Save a rule for this account, or `None` when it already has one by that name.

    The owner is a parameter, never a field in the rule: the route takes it from the signed in
    account, so a caller cannot write a row onto somebody else (spec 0015).

    `None` rather than an exception so the caller needs no import from this module, which keeps
    `psycopg` out of the import graph of a route that is disabled on the deployed function. It
    also matches `delete_rule`, where `False` means the id is unknown. Any other database error
    propagates and becomes a 500, which is what it is.
    """
    new_id = uuid.uuid4()
    try:
        with connect() as conn:
            conn.execute(
                "insert into rules (id, name, rule, account_id) values (%s, %s, %s, %s)",
                (new_id, rule.name, rule.model_dump_json(), account_id),
            )
    except psycopg.errors.UniqueViolation:
        # Unique on (account_id, lower(name)), so this is a name this account already used.
        return None
    return SavedRule(id=new_id, rule=rule)


def list_rules(account_id: uuid.UUID) -> list[SavedRule]:
    """This account's saved rules, newest first, whole, so loading one back needs no second
    request.

    Isolation is this `where`, not a filter applied after reading: a wrong owner returns no
    rows rather than rows somebody then has to remember to drop (spec 0015, AC-3).
    """
    with connect() as conn:
        rows = conn.execute(
            "select id, rule from rules where account_id = %s order by created_at desc",
            (account_id,),
        ).fetchall()
    # psycopg types a row as tuple[object, ...]; the casts say what the two columns are.
    return [
        SavedRule(id=cast("uuid.UUID", row[0]), rule=Rule.model_validate(row[1])) for row in rows
    ]


def delete_rule(rule_id: uuid.UUID, account_id: uuid.UUID) -> bool:
    """Delete one of this account's rules. False when it has no rule with that id.

    The owner is in the `where`, so another account's rule matches nothing and is
    indistinguishable from an id that was never real. The route answers 404 either way, which
    is why it does not disclose that the rule exists (spec 0015, AC-3).
    """
    with connect() as conn:
        cursor = conn.execute(
            "delete from rules where id = %s and account_id = %s", (rule_id, account_id)
        )
        return cursor.rowcount > 0
