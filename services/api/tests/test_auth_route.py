"""The auth routes (spec 0015): the gate, the cookie, the identical 401s, and the 422 that
must never carry a password back.

No database here. Every repository call is patched, because what these pin is the route and
cookie behaviour; the real round trip against Neon is the owner's local run, the same evidence
D-4 and spec 0014 settle for (`engine/tests/dataset/`).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api import auth
from api.main import app
from engine import api as use_cases
from engine.contracts import Account

client = TestClient(app, raise_server_exceptions=False)

ACCOUNT = Account(id=uuid.UUID("33333333-3333-4333-8333-333333333333"), email="you@example.com")
GOOD = {"email": "you@example.com", "password": "a long enough password"}
SECRET = "x" * 64


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Accounts running, as they do only on your own machine."""
    monkeypatch.setattr(auth, "ENABLED", True)
    monkeypatch.setenv(auth.AUTH_SECRET_ENV, SECRET)
    yield
    client.cookies.clear()


@pytest.fixture
def disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Accounts off, which is how CI and the deployed API always run."""
    monkeypatch.setattr(auth, "ENABLED", False)
    monkeypatch.setattr(auth, "WHY_DISABLED", ["no DATABASE_URL is configured"])


# ---- The gate comes first (AC-4, AC-5) ------------------------------------------------------


@pytest.mark.usefixtures("disabled")
@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/api/v1/auth/register", GOOD),
        ("POST", "/api/v1/auth/login", GOOD),
        ("POST", "/api/v1/auth/logout", None),
        ("GET", "/api/v1/auth/me", None),
        ("DELETE", "/api/v1/auth/account", None),
    ],
)
def test_every_auth_route_is_501_where_accounts_do_not_run(
    method: str, path: str, body: dict[str, str] | None
) -> None:
    res = client.request(method, path, json=body)
    assert res.status_code == 501
    assert "feature 22" in res.json()["detail"]


@pytest.mark.usefixtures("disabled")
def test_signed_out_reads_as_not_available_here_not_as_sign_in() -> None:
    """AC-4: the order of the checks is the point. On the deployed demo there is nothing to
    sign in to, so a signed out request must say 501, never 401."""
    assert client.get("/api/v1/auth/me").status_code == 501


# ---- The password never travels back (AC-2) -------------------------------------------------


@pytest.mark.usefixtures("enabled")
def test_a_rejected_password_is_not_echoed_in_the_422() -> None:
    """FastAPI's default 422 body carries `input`, the value that failed, which here is the
    password. Measured, not assumed: without the handler in `main.py` this test fails."""
    password = "tooshort"  # noqa: S105  # the point of the test is that it comes back stripped
    res = client.post("/api/v1/auth/register", json={"email": "a@b.co", "password": password})
    assert res.status_code == 422
    assert password not in res.text
    assert all("input" not in issue for issue in res.json()["detail"])


@pytest.mark.usefixtures("enabled")
def test_other_routes_keep_their_422_input() -> None:
    """The handler strips `input` on `/auth/*` only. Everywhere else the rule builder needs it
    to show which field went wrong (U-7), so stripping it project wide would break a feature."""
    bad = {"name": "Bad", "conditions": [{"left": {"kind": "ind", "ind": "macd"}, "op": ">"}]}
    res = client.post("/api/v1/scan", json={"rule": bad})
    assert res.status_code == 422
    assert any("input" in issue for issue in res.json()["detail"])


# ---- Register and sign in (AC-1, AC-6, AC-7) ------------------------------------------------


@pytest.mark.usefixtures("enabled")
def test_register_returns_201_and_sets_an_httponly_lax_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(use_cases, "register", lambda _e, _p: ACCOUNT)
    res = client.post("/api/v1/auth/register", json=GOOD)
    assert res.status_code == 201
    assert res.json() == {"id": str(ACCOUNT.id), "email": ACCOUNT.email}
    cookie = res.headers["set-cookie"]
    assert auth.COOKIE_NAME in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    # No Secure: the only origin that reaches this is http on loopback. If this ever changes,
    # the attribute has to come back with it.
    assert "Secure" not in cookie


@pytest.mark.usefixtures("enabled")
def test_a_taken_email_is_409_not_a_second_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(use_cases, "register", lambda _e, _p: None)
    res = client.post("/api/v1/auth/register", json=GOOD)
    assert res.status_code == 409
    assert "set-cookie" not in res.headers


@pytest.mark.usefixtures("enabled")
def test_a_wrong_password_and_an_unknown_email_are_the_same_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-7: the repository answers `None` for both, so the route cannot tell them apart even
    by accident, and the response cannot disclose whether an address is registered."""
    monkeypatch.setattr(use_cases, "sign_in", lambda _e, _p: None)
    wrong_password = client.post("/api/v1/auth/login", json=GOOD)
    unknown_email = client.post("/api/v1/auth/login", json={**GOOD, "email": "nobody@example.com"})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.text == unknown_email.text
    assert wrong_password.json()["detail"] == auth.BAD_CREDENTIALS


# ---- A session that is not one (AC-8) -------------------------------------------------------


@pytest.mark.usefixtures("enabled")
@pytest.mark.parametrize(
    "token",
    [
        "not.a.jwt",
        "",
        # Signed with a different key: a valid shape that must not be trusted.
        __import__("jwt").encode({"sub": str(ACCOUNT.id), "exp": 9999999999}, "a" * 64),
        # Valid signature, no `exp`, which `options={"require": [...]}` rejects.
        __import__("jwt").encode({"sub": str(ACCOUNT.id)}, SECRET),
        # Valid signature and claims, but `sub` is not a uuid.
        __import__("jwt").encode({"sub": "not-a-uuid", "exp": 9999999999}, SECRET),
    ],
    ids=["malformed", "empty", "wrong key", "no exp", "sub not a uuid"],
)
def test_a_token_that_is_not_a_session_is_401_and_never_500(token: str) -> None:
    client.cookies.set(auth.COOKIE_NAME, token)
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.usefixtures("enabled")
def test_an_expired_token_is_401(monkeypatch: pytest.MonkeyPatch) -> None:
    import jwt

    expired = jwt.encode({"sub": str(ACCOUNT.id), "exp": 1_600_000_000}, SECRET)
    client.cookies.set(auth.COOKIE_NAME, expired)
    assert client.get("/api/v1/auth/me").status_code == 401


@pytest.mark.usefixtures("enabled")
def test_a_valid_token_for_a_deleted_account_is_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole reason the per request lookup exists. Without it this token would keep working
    for its full thirty days, because there is no sessions table to revoke it from."""
    monkeypatch.setattr(use_cases, "account_by_id", lambda _id: None)
    client.cookies.set(auth.COOKIE_NAME, auth.issue_token(ACCOUNT.id))
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert "set-cookie" in res.headers


@pytest.mark.usefixtures("enabled")
def test_a_database_failure_is_503_not_500_and_not_signed_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neon suspends when idle, so this is a real path. It is a retry, not a sign out: telling
    someone they are signed out when the database merely blinked is a lie the UI would act on."""

    def boom(_id: uuid.UUID) -> Account:
        raise OSError("connection refused")

    monkeypatch.setattr(use_cases, "account_by_id", boom)
    client.cookies.set(auth.COOKIE_NAME, auth.issue_token(ACCOUNT.id))
    assert client.get("/api/v1/auth/me").status_code == 503


# ---- Signing out, and deleting (AC-1, AC-9) -------------------------------------------------


@pytest.mark.usefixtures("enabled")
def test_logout_clears_the_cookie_without_needing_a_valid_one() -> None:
    """A browser holding a dead token must still be able to clear it."""
    client.cookies.set(auth.COOKIE_NAME, "not.a.jwt")
    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 204
    assert auth.COOKIE_NAME in res.headers["set-cookie"]


@pytest.mark.usefixtures("enabled")
def test_delete_account_signs_the_browser_out(monkeypatch: pytest.MonkeyPatch) -> None:
    deleted: list[uuid.UUID] = []
    monkeypatch.setattr(use_cases, "account_by_id", lambda _id: ACCOUNT)
    monkeypatch.setattr(
        use_cases, "delete_account", lambda account_id: bool(deleted.append(account_id)) or True
    )
    client.cookies.set(auth.COOKIE_NAME, auth.issue_token(ACCOUNT.id))
    res = client.delete("/api/v1/auth/account")
    assert res.status_code == 204
    assert deleted == [ACCOUNT.id]
    assert auth.COOKIE_NAME in res.headers["set-cookie"]


# ---- The research path never needed an account (AC-15) --------------------------------------


@pytest.mark.usefixtures("disabled")
@pytest.mark.parametrize("path", ["/api/v1/health", "/api/v1/templates", "/api/v1/indicators"])
def test_the_research_surface_is_untouched_signed_out(path: str) -> None:
    assert client.get(path).status_code == 200
