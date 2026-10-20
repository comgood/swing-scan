"""Accounts in Postgres (spec 0015): register, sign in, look one up, delete one.

Infrastructure, so it lives here beside the saved rules repository and the market store. Plain
SQL and `psycopg`, no ORM, as spec 0014 settled. The database owns identity (one email, case
insensitive) and the hash; nothing else about an account is stored, because nothing else is
needed: there is no verification, no reset, and no profile.

Every function returns `None` or a bool rather than raising, matching `rules.py`, so a route
needs no import from this module and `psycopg` stays out of the import graph of a surface that
answers 501 on the deployed function.
"""

from __future__ import annotations

import uuid
from typing import cast

import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from engine.contracts import Account

from ._db import connect

_hasher = PasswordHasher()
"""Argon2id at the library's own defaults, which are the ones it keeps current.

Deliberately not configured here: the parameters travel inside every hash it writes (the PHC
string carries them), so there is nothing to keep in step and nothing to get wrong.
"""

_DUMMY_HASH = _hasher.hash("a password no account has")
"""Hashed once at import so a sign in for an address with no account costs the same as a wrong
password (see `verify_account`). Built from the real hasher rather than written as a literal,
so it can never drift from the parameters real hashes use and change the timing it exists to
hide.
"""


def hash_password(password: str) -> str:
    """The Argon2id PHC string to store. Carries its own salt and cost parameters."""
    return _hasher.hash(password)


def create_account(email: str, password: str) -> Account | None:
    """Register an account, or `None` when that email is already taken.

    `None` rather than an exception for the same reason `save_rule` does it: the route stays
    free of this module. The unique index on `lower(email)` is what decides, so two requests
    racing to register one address cannot both win.
    """
    new_id = uuid.uuid4()
    try:
        with connect() as conn:
            conn.execute(
                "insert into accounts (id, email, password_hash) values (%s, %s, %s)",
                (new_id, email, hash_password(password)),
            )
    except psycopg.errors.UniqueViolation:
        return None
    return Account(id=new_id, email=email)


def verify_account(email: str, password: str) -> Account | None:
    """The account for these credentials, or `None` when either is wrong.

    One `None` for both cases on purpose: the route turns it into one 401 body, so the response
    cannot say whether the address exists (AC-7). The timing cannot say so either, because a
    missing account still pays a full Argon2id verify against `_DUMMY_HASH`. Skipping that is
    the classic way an account enumeration oracle survives an identical response body.
    """
    with connect() as conn:
        row = conn.execute(
            "select id, email, password_hash from accounts where lower(email) = lower(%s)",
            (email,),
        ).fetchone()

    stored = _DUMMY_HASH if row is None else cast("str", row[2])
    try:
        _hasher.verify(stored, password)
    except (VerifyMismatchError, InvalidHashError):
        return None
    if row is None:
        # The dummy hash matched, which means someone guessed the dummy's plaintext. Still no
        # account, so still no sign in.
        return None
    return Account(id=cast("uuid.UUID", row[0]), email=cast("str", row[1]))


def account_by_id(account_id: uuid.UUID) -> Account | None:
    """The account for an id, or `None` when no row has it.

    This is the read every gated request makes. It is what makes deleting an account take
    effect immediately: without it a signed cookie would keep working for its full 30 days
    after the row was gone, because there is no sessions table to revoke (spec 0015, AC-8).
    """
    with connect() as conn:
        row = conn.execute("select id, email from accounts where id = %s", (account_id,)).fetchone()
    if row is None:
        return None
    return Account(id=cast("uuid.UUID", row[0]), email=cast("str", row[1]))


def delete_account(account_id: uuid.UUID) -> bool:
    """Delete an account and, by `on delete cascade`, every rule it saved.

    `False` when no account has that id. The cascade is the database's job rather than a second
    statement here, so no code path can delete an account and leave its rules behind (AC-9).
    """
    with connect() as conn:
        cursor = conn.execute("delete from accounts where id = %s", (account_id,))
        return cursor.rowcount > 0
