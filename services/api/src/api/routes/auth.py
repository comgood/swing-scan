"""Accounts (spec 0015): register, sign in, sign out, who am I, delete. 501 off your machine.

Three gates, all in `saved_rules_problems`: a `DATABASE_URL`, an `AUTH_SECRET` long enough to
be worth signing with, and the D-5 host rules. Any one failing means every route here answers
501, so setting a database and a key on the deployed function still cannot open a public login.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response

from engine import api as use_cases
from engine.contracts import Account, Credentials, NotImplementedBody

from ..auth import BAD_CREDENTIALS, clear_session, current_account, require_enabled, set_session

router = APIRouter()

NOT_HERE: dict[int | str, dict[str, Any]] = {
    501: {"model": NotImplementedBody, "description": "Not available here"}
}

SignedIn = Annotated[Account, Depends(current_account)]


@router.post("/auth/register", response_model=Account, status_code=201, responses=NOT_HERE)
def register(body: Credentials, response: Response) -> Account:
    """Register and sign in, in one step. An email already taken is a 409.

    A 409 does tell you that an address is registered. That is the honest trade: the
    alternative is to accept a registration and say nothing, which for a single user system
    with no email to confirm through is a worse experience than the disclosure is a risk.
    Sign in, where it would matter, says nothing (AC-7).
    """
    require_enabled()
    account = use_cases.register(body.email, body.password.get_secret_value())
    if account is None:
        raise HTTPException(status_code=409, detail="That email already has an account.")
    set_session(response, account.id)
    return account


@router.post("/auth/login", response_model=Account, responses=NOT_HERE)
def login(body: Credentials, response: Response) -> Account:
    """Sign in. A wrong address and a wrong password give the identical 401."""
    require_enabled()
    account = use_cases.sign_in(body.email, body.password.get_secret_value())
    if account is None:
        raise HTTPException(status_code=401, detail=BAD_CREDENTIALS)
    set_session(response, account.id)
    return account


@router.post("/auth/logout", status_code=204, responses=NOT_HERE)
def logout() -> Response:
    """Sign out by discarding the cookie.

    Deliberately needs no valid token: a browser holding an expired or corrupt one must still
    be able to clear it, rather than being stuck signed in to nothing it can reach.
    """
    require_enabled()
    response = Response(status_code=204)
    clear_session(response)
    return response


@router.get("/auth/me", response_model=Account, responses=NOT_HERE)
def me(account: SignedIn) -> Account:
    """Who you are signed in as. The web app reads this to decide what to show."""
    return account


@router.delete("/auth/account", status_code=204, responses=NOT_HERE)
def delete_account(account: SignedIn) -> Response:
    """Delete your account and, by the database's cascade, every rule you saved.

    No password re prompt: the only person who can reach this is already the only person who
    can reach the machine it runs on.
    """
    use_cases.delete_account(account.id)
    response = Response(status_code=204)
    clear_session(response)
    return response
