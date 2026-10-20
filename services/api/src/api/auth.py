"""The session cookie and the dependency that resolves it (spec 0015).

Presentation, not domain: the engine never learns what a cookie is, so this lives here and not
in `engine/`. There is no sessions table, by decision, so the cookie **is** the session: a
signed token carrying the account id and an expiry, and nothing else.

What that costs, stated where the code is: a token cannot be revoked before it expires. What
limits the damage is the account lookup on every gated request, which is the only reason
deleting an account takes effect at all.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import HTTPException, Request, Response

from engine import api as use_cases
from engine.api import NotYetImplemented
from engine.contracts import Account

from .settings import AUTH_SECRET_ENV, saved_rules_problems

log = logging.getLogger("api.auth")

COOKIE_NAME = "session"
"""No `__Host-` prefix: that prefix requires `Secure`, and the only origin that reaches this
is plain http on loopback."""

TOKEN_TTL = timedelta(days=30)
ALGORITHM = "HS256"

ENABLED = not saved_rules_problems(sys.argv, os.environ)
"""False on the deployed API, in CI, and locally until both `DATABASE_URL` and `AUTH_SECRET`
are set. One flag shared with the rules routes, because a rule now belongs to an account.

Read once at import, like the rules gate: it is a pure function of `sys.argv` and the
environment, and neither changes while the process lives. Tests monkeypatch it.
"""

WHY_DISABLED = saved_rules_problems(sys.argv, os.environ)
"""The reasons, so the 501 body can name what to fix rather than just refusing."""

BAD_CREDENTIALS = "That email and password do not match an account."
"""One message for a wrong address and a wrong password alike, so the response cannot say
which (AC-7). The repository also pays a full hash verify either way, so the timing cannot."""

SIGNED_OUT = "You are not signed in."


def require_enabled() -> None:
    """501 anywhere accounts do not run, checked **before** anything about the request.

    The order matters: a signed out request on the deployed demo has to read as "not available
    here", not as "sign in", because there is nothing there to sign in to (AC-4).
    """
    if not ENABLED:
        raise NotYetImplemented(22, f"Accounts ({'; '.join(WHY_DISABLED)})")


def _secret() -> str:
    """The signing key. Never generated, never defaulted: a key that changed between restarts
    would sign every browser out, which is exactly what AC-1 forbids."""
    secret = os.environ.get(AUTH_SECRET_ENV, "")
    if not secret:
        raise NotYetImplemented(22, "Accounts (no AUTH_SECRET is configured)")
    return secret


def issue_token(account_id: UUID) -> str:
    """A signed token for this account, good for `TOKEN_TTL`."""
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(account_id), "exp": now + TOKEN_TTL, "iat": now},
        _secret(),
        algorithm=ALGORITHM,
    )


def set_session(response: Response, account_id: UUID) -> None:
    """Attach the session cookie.

    `httponly` so no script can read it. `samesite="lax"` for CSRF: a cross site form post
    never carries it. Note what that does **not** buy, since it is easy to over trust: a Lax
    cookie is scoped to the host and ignores the port, so anything else you run on
    `127.0.0.1` receives it too.

    No `secure`: the only origin that can reach this is http on loopback, and a conditional
    would be more code than the thing it guards. This has to change the day it is served over
    https.
    """
    response.set_cookie(
        COOKIE_NAME,
        issue_token(account_id),
        max_age=int(TOKEN_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session(response: Response) -> None:
    """Remove the cookie, with the same name and path it was set with, or the browser keeps it."""
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax")


def _signed_out() -> HTTPException:
    """A 401 that also clears the cookie.

    The header is built here rather than written on an injected `Response`, because FastAPI
    throws that response away when a dependency raises: the status would be 401 and the cookie
    would silently stay in the browser, which is the bug `test_a_valid_token_for_a_deleted_
    account_is_401` exists to catch. The value comes from `clear_session` so the attributes
    cannot drift from the ones the cookie was set with.
    """
    probe = Response()
    clear_session(probe)
    return HTTPException(
        status_code=401, detail=SIGNED_OUT, headers={"set-cookie": probe.headers["set-cookie"]}
    )


def current_account(request: Request) -> Account:
    """The signed in account, or the right refusal.

    In this order, deliberately: 501 if accounts do not run here, then 401 for anything wrong
    with the token, then the database read that proves the account still exists. Every 401
    also clears the cookie, sent or not, so a browser holding a dead token stops presenting it
    rather than retrying for thirty days.
    """
    require_enabled()

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise _signed_out()

    try:
        # `algorithms` is pinned so the token's own header cannot choose how it is verified,
        # and both claims are required so a token missing one is rejected rather than read
        # with a default.
        claims = jwt.decode(
            token, _secret(), algorithms=[ALGORITHM], options={"require": ["exp", "sub"]}
        )
        account_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError):
        # Expired, tampered with, signed by a different key, or a `sub` that is not a uuid.
        # All the same answer: this is not a session.
        raise _signed_out() from None

    try:
        account = use_cases.account_by_id(account_id)
    except Exception:
        # The database is the only thing this call touches, and Neon suspends when idle, so a
        # failure here is infrastructure rather than the caller's fault: 503 and a retry, not a
        # 500 and not a spurious "you are signed out". Caught broadly on purpose, so `psycopg`
        # stays out of this layer's import graph, the same reason the repository returns `None`
        # instead of raising.
        log.exception("the account lookup failed")
        raise HTTPException(
            status_code=503, detail="The database is not reachable right now. Try again."
        ) from None

    if account is None:
        # A valid token for an account that no longer exists. This is the case the lookup is
        # here for: without it a deleted account would keep working until its token expired.
        raise _signed_out()
    return account
