"""Accounts (spec 0015): the two shapes that cross the wire, and nothing more.

An email is only ever an identifier here. Nothing is ever sent to it, so there is no
verification, no reset, and deliberately no format check: pulling in `email-validator` to
police the shape of a string that is never mailed to buys nothing. Length is bounded because
a column is.

`Account` is what comes back. It never carries the hash, so there is no response model in
this project through which a password could leak (AC-2).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import SecretStr, StringConstraints

from ._errors import ContractModel, bounded

Email = Annotated[str, StringConstraints(strip_whitespace=True), bounded(1, 254)]
"""An account's identifier: 1 to 254 characters after trimming, the longest address a mail
system must accept. Stored trimmed, compared case insensitively."""

Password = Annotated[SecretStr, bounded(12, 128)]
"""A password: at least 12 characters, at most 128, and no composition rules.

Length over composition, which is current guidance rather than the old mixed case and symbol
advice. The 128 cap bounds the work Argon2id is asked to do. Counted in characters, not bytes:
Argon2id has no 72 byte input limit, so the bcrypt truncation trap does not apply.

`bounded`, not Pydantic's `min_length`, because every ranged contract field in this project
goes through it and reports both sides of the range (spec 0002); `engine/tests/contracts/
test_rule_validation.py` enforces that. It measures a `SecretStr` through its `__len__`.

`SecretStr` is defence in depth for the second half of AC-2, "no log line contains it": it
renders as `**********` anywhere it is printed or logged by accident. It does **not** protect
the 422 body, which carries the raw `input` and needed its own handler in `main.py`. That was
measured, not assumed.
"""


class Credentials(ContractModel):
    """What register and sign in take. The only place a password appears in the contracts."""

    email: Email
    password: Password


class Account(ContractModel):
    """Who you are signed in as. No hash, no token: the token lives in the cookie."""

    id: UUID
    email: str
