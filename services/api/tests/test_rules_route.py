"""The rules routes (spec 0014): the 501 gate, the 422 paths, 409, 404, and the DELETE preflight."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import app, settings
from api.routes import rules

# The same module object the router holds as `use_cases`, patched here rather than through the
# router, which re-exports nothing.
from engine import api as use_cases
from engine.contracts import Rule, SavedRule

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


def _bad_rule(left: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": "Bad",
        "conditions": [{"left": left, "op": ">", "right": {"kind": "value", "value": 5}}],
    }


UNKNOWN_INDICATOR = _bad_rule({"kind": "ind", "ind": "macd", "n": 12})
N_OUT_OF_RANGE = _bad_rule({"kind": "ind", "ind": "rsi", "n": 60})


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate open, as it is only on your own machine with a `DATABASE_URL`."""
    monkeypatch.setattr(rules, "ENABLED", True)


@pytest.fixture
def disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate shut, which is how CI and the deployed API always run."""
    monkeypatch.setattr(rules, "ENABLED", False)


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
    assert "feature 21" in res.json()["detail"]


@pytest.mark.usefixtures("disabled")
@pytest.mark.parametrize("bad", [UNKNOWN_INDICATOR, N_OUT_OF_RANGE], ids=["unknown_ind", "bad_n"])
def test_a_bad_rule_is_422_on_the_same_paths_as_scan(bad: dict[str, Any]) -> None:
    """AC-3: the body is the `Rule` itself, so the paths are `/scan`'s without its `rule` wrapper.

    The gate is shut here on purpose: FastAPI validates the body before the route runs, so a
    malformed rule is a 422 rather than the 501, which is what the form relies on.
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
    monkeypatch.setattr(use_cases, "save_rule", lambda rule: SavedRule(id=new_id, rule=rule))
    res = client.post("/api/v1/rules", json=RULE)
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == str(new_id)
    assert body["rule"] == Rule.model_validate(RULE).model_dump(mode="json")


@pytest.mark.usefixtures("enabled")
def test_a_name_already_taken_is_409(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(use_cases, "save_rule", lambda rule: None)
    res = client.post("/api/v1/rules", json=RULE)
    assert res.status_code == 409
    assert "Saved" in res.json()["detail"]


@pytest.mark.usefixtures("enabled")
def test_the_list_returns_whole_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = SavedRule(id=uuid.uuid4(), rule=Rule.model_validate(RULE))
    monkeypatch.setattr(use_cases, "list_rules", lambda: [saved])
    res = client.get("/api/v1/rules")
    assert res.status_code == 200
    assert res.json() == [saved.model_dump(mode="json")]


@pytest.mark.usefixtures("enabled")
@pytest.mark.parametrize(("deleted", "status"), [(True, 204), (False, 404)])
def test_delete_is_204_or_404(deleted: bool, status: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(use_cases, "delete_rule", lambda rule_id: deleted)
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
