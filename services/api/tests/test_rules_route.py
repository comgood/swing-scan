"""The rules routes (spec 0014): the 501 gate, the 422 paths, 409, 404, and the DELETE preflight."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api import auth
from api.main import app, settings

# The same module object the router holds as `use_cases`, patched here rather than through the
# router, which re-exports nothing.
from engine import api as use_cases
from engine.contracts import Account, Rule, SavedRule

client = TestClient(app, raise_server_exceptions=False)

RULE: dict[str, Any] = {
    "name": "Saved",
    "conditions": [
        {
            "left": {"kind": "ind", "ind": "close"},
            "op": ">",
            "right": {"kind": "value", "value": 5},
        }
    ],
}
SOME_ID = "11111111-1111-4111-8111-111111111111"
OWNER_ID = "22222222-2222-4222-8222-222222222222"


def _bad_rule(left: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": "Bad",
        "conditions": [{"left": left, "op": ">", "right": {"kind": "value", "value": 5}}],
    }


UNKNOWN_INDICATOR = _bad_rule({"kind": "ind", "ind": "macd", "n": 12})
N_OUT_OF_RANGE = _bad_rule({"kind": "ind", "ind": "rsi", "n": 60})


ACCOUNT = Account(id=uuid.UUID(OWNER_ID), email="owner@example.com")


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The gate open and somebody signed in, as it is only on your own machine.

    `current_account` is overridden rather than driven with a real cookie: these tests are
    about the rules routes, and the cookie, the token and the account lookup have their own
    tests in `test_auth_route.py`. The override is what supplies the owner every statement is
    now scoped to (spec 0015).
    """
    monkeypatch.setattr(auth, "ENABLED", True)
    app.dependency_overrides[auth.current_account] = lambda: ACCOUNT
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate shut, which is how CI and the deployed API always run.

    No dependency override here on purpose: the real `current_account` has to run so the 501
    is proved to come from the gate, and to come **before** the 401 (spec 0015 AC-4).
    """
    monkeypatch.setattr(auth, "ENABLED", False)
    # Pinned too, not just ENABLED: the real value is read from the environment at import, so
    # asserting on it would pass in CI and fail on a machine that has a .env.
    monkeypatch.setattr(auth, "WHY_DISABLED", ["no DATABASE_URL is configured"])


@pytest.mark.usefixtures("disabled")
@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/api/v1/rules", RULE),
        ("GET", "/api/v1/rules", None),
        ("DELETE", f"/api/v1/rules/{SOME_ID}", None),
    ],
)
def test_every_endpoint_is_501_without_the_gate(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    res = client.request(method, path, json=body)
    assert res.status_code == 501
    # Feature 22, not 21: a rule belongs to an account now, so the two surfaces share one gate
    # and one message, and the message names what is actually missing (spec 0015).
    detail = res.json()["detail"]
    assert "feature 22" in detail
    # The reason travels in the body, so the 501 names what to fix rather than just refusing.
    assert "no DATABASE_URL is configured" in detail


@pytest.mark.usefixtures("enabled")
@pytest.mark.parametrize("bad", [UNKNOWN_INDICATOR, N_OUT_OF_RANGE], ids=["unknown_ind", "bad_n"])
def test_a_bad_rule_is_422_on_the_same_paths_as_scan(bad: dict[str, Any]) -> None:
    """AC-3: the body is the `Rule` itself, so the paths are `/scan`'s without its `rule` wrapper.

    Run with the gate **open**, which is the only place the form ever sees this. It used to run
    with the gate shut, because the old route checked the gate inside its own body and FastAPI
    validated the body first. The gate is a dependency now (spec 0015), and FastAPI resolves
    dependencies before it reports body errors, so a malformed rule sent where accounts do not
    run is a 501 rather than a 422. That is the honest answer there (the endpoint genuinely is
    not available) and the web app hides the control on a 501 anyway, so nothing reads the
    difference.
    """
    saved = client.post("/api/v1/rules", json=bad)
    scanned = client.post("/api/v1/scan", json={"rule": bad})
    assert (saved.status_code, scanned.status_code) == (422, 422)

    def locs(res: Any, prefix: tuple[str, ...]) -> list[list[Any]]:
        return [list(issue["loc"][len(prefix) :]) for issue in res.json()["detail"]]

    # Only the prefix differs, which is the one thing `fieldErrorsFrom422` strips. The types and
    # the `ctx` are `Rule`'s own, since both routes validate the same model.
    assert locs(saved, ("body",)) == locs(scanned, ("body", "rule"))
    assert locs(saved, ()) != []
    assert all(issue["loc"][0] == "body" for issue in saved.json()["detail"])


@pytest.mark.usefixtures("enabled")
def test_a_saved_rule_comes_back_with_its_id(monkeypatch: pytest.MonkeyPatch) -> None:
    new_id = uuid.uuid4()
    monkeypatch.setattr(
        use_cases, "save_rule", lambda rule, _account: SavedRule(id=new_id, rule=rule)
    )
    res = client.post("/api/v1/rules", json=RULE)
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == str(new_id)
    assert body["rule"] == Rule.model_validate(RULE).model_dump(mode="json")


@pytest.mark.usefixtures("enabled")
def test_a_name_already_taken_is_409(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(use_cases, "save_rule", lambda _rule, _account: None)
    res = client.post("/api/v1/rules", json=RULE)
    assert res.status_code == 409
    assert "Saved" in res.json()["detail"]


@pytest.mark.usefixtures("enabled")
def test_the_list_returns_whole_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = SavedRule(id=uuid.uuid4(), rule=Rule.model_validate(RULE))
    monkeypatch.setattr(use_cases, "list_rules", lambda _account: [saved])
    res = client.get("/api/v1/rules")
    assert res.status_code == 200
    assert res.json() == [saved.model_dump(mode="json")]


@pytest.mark.usefixtures("enabled")
@pytest.mark.parametrize(("deleted", "status"), [(True, 204), (False, 404)])
def test_delete_is_204_or_404(deleted: bool, status: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(use_cases, "delete_rule", lambda _rule_id, _account: deleted)
    assert client.delete(f"/api/v1/rules/{SOME_ID}").status_code == status


def test_the_delete_preflight_passes_cors() -> None:
    """AC-8: without `DELETE` in `allow_methods` the browser never sends the request at all."""
    res = client.options(
        f"/api/v1/rules/{SOME_ID}",
        headers={
            "Origin": settings.allowed_origins[0],
            "Access-Control-Request-Method": "DELETE",
        },
    )
    assert res.status_code == 200
    assert "DELETE" in res.headers["access-control-allow-methods"]


@pytest.mark.usefixtures("enabled")
def test_every_statement_is_scoped_to_the_signed_in_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """spec 0015 AC-3: the owner comes from the session, never from anything the caller sends.

    This is the test that would fail if someone later took the owner from the request body,
    which is the mistake that turns isolation into a suggestion.
    """
    seen: list[uuid.UUID] = []

    def record_save(rule: Rule, account_id: uuid.UUID) -> SavedRule:
        seen.append(account_id)
        return SavedRule(id=uuid.uuid4(), rule=rule)

    monkeypatch.setattr(use_cases, "save_rule", record_save)
    monkeypatch.setattr(use_cases, "list_rules", lambda account_id: seen.append(account_id) or [])
    monkeypatch.setattr(
        use_cases, "delete_rule", lambda _id, account_id: bool(seen.append(account_id)) or True
    )

    client.post("/api/v1/rules", json=RULE)
    client.get("/api/v1/rules")
    client.delete(f"/api/v1/rules/{SOME_ID}")
    assert seen == [ACCOUNT.id, ACCOUNT.id, ACCOUNT.id]
