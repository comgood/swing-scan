"""Saved rules in Postgres (spec 0014): the rule travels as one `jsonb` column.

Infrastructure, so it lives here beside the market store and not in `services/api`. The whole
`Rule` is stored as the contract produced it, which is why condition order survives (a JSON
array is ordered), why a defaulted `n` round trips unchanged, and why a new contract field needs
no migration. The database owns identity (one name, case insensitive) and nothing else; `Rule`
stays the only validator.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast

import psycopg

from engine.contracts import Rule, SavedRule

DATABASE_URL_ENV = "DATABASE_URL"


def configured() -> bool:
    """Whether a database is configured at all. Absent means the routes answer 501."""
    return bool(os.environ.get(DATABASE_URL_ENV))


@contextmanager
def _connect() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """A connection for one request, opened and closed inside it.

    Never a module level connection: on Lambda the execution environment is frozen between
    invocations, so a socket held across one does not reliably survive, and the failure shows
    up as a mystery error after an idle period rather than at the point of the mistake.

    `prepare_threshold=0` because `DATABASE_URL` is the pooled endpoint, which is PgBouncer in
    transaction mode: a prepared statement cannot outlive its checkout, and reusing one fails
    with `prepared statement "_pg3_0" already exists`.
    """
    url = os.environ.get(DATABASE_URL_ENV)
    if not url:
        raise RuntimeError(f"{DATABASE_URL_ENV} is not set; saved rules are not available here.")
    with psycopg.connect(url, prepare_threshold=0) as conn:
        yield conn


def save_rule(rule: Rule) -> SavedRule | None:
    """Save a rule under its own name, or `None` when that name is already taken.

    `None` rather than an exception so the caller needs no import from this module, which keeps
    `psycopg` out of the import graph of a route that is disabled on the deployed function. It
    also matches `delete_rule`, where `False` means the id is unknown. Any other database error
    propagates and becomes a 500, which is what it is.
    """
    new_id = uuid.uuid4()
    try:
        with _connect() as conn:
            conn.execute(
                "insert into rules (id, name, rule) values (%s, %s, %s)",
                (new_id, rule.name, rule.model_dump_json()),
            )
    except psycopg.errors.UniqueViolation:
        return None
    return SavedRule(id=new_id, rule=rule)


def list_rules() -> list[SavedRule]:
    """Every saved rule, newest first. Returns whole rules, so loading one back needs no
    second request."""
    with _connect() as conn:
        rows = conn.execute("select id, rule from rules order by created_at desc").fetchall()
    # psycopg types a row as tuple[object, ...]; the casts say what the two columns are.
    return [
        SavedRule(id=cast("uuid.UUID", row[0]), rule=Rule.model_validate(row[1])) for row in rows
    ]


def delete_rule(rule_id: uuid.UUID) -> bool:
    """Delete one rule. False when no rule has that id, which the route turns into a 404."""
    with _connect() as conn:
        cursor = conn.execute("delete from rules where id = %s", (rule_id,))
        return cursor.rowcount > 0
