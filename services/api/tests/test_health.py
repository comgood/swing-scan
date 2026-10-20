from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from api.main import app
from api.settings import Settings

client = TestClient(app)


def test_health_reports_ok_and_synthetic_mode() -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["data_mode"] == "synthetic"


def test_cors_allows_local_web_origin() -> None:
    res = client.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_rejects_unknown_origin() -> None:
    res = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in res.headers


# ---- The deployed CORS configuration (spec 0001; infra/README.md section 6) -------------
#
# The deployed function allows the Vercel production domain by name and every preview
# deployment by pattern. Nothing above covers that: the app under test reads the local
# default. These lock the two origin values the deploy sets, because a preview pattern that
# stops matching breaks every preview silently, and one that over matches lets any host
# ending in the domain through.

DEPLOY_ENV = {
    "DATA_MODE": "synthetic",
    "ALLOWED_ORIGINS": "https://swing-scan-one.vercel.app",
    "ALLOWED_ORIGIN_REGEX": r"^https://swing-scan-[a-z0-9-]+\.vercel\.app$",
}


def _cors_kwargs() -> dict[str, Any]:
    """The CORS settings the real app mounted, so these tests follow `main.py` rather than
    a copy of it."""
    for middleware in app.user_middleware:
        if isinstance(middleware.cls, type) and issubclass(middleware.cls, CORSMiddleware):
            return dict(middleware.kwargs)
    raise AssertionError("the app has no CORS middleware")


def _client_with_deploy_origins() -> TestClient:
    """The app's own CORS middleware, re-mounted with the origins the deploy sets."""
    settings = Settings.from_env(DEPLOY_ENV, ["uvicorn", "api.main:app"])
    probe = FastAPI()
    probe.add_middleware(
        CORSMiddleware,
        **_cors_kwargs()
        | {
            "allow_origins": settings.allowed_origins,
            "allow_origin_regex": settings.allowed_origin_regex,
        },
    )

    @probe.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(probe)


def test_cors_is_wired_to_the_settings() -> None:
    """Drop `allow_origin_regex` from `main.py` and every Vercel preview loses the API."""
    settings = Settings.from_env()
    kwargs = _cors_kwargs()
    assert kwargs["allow_origins"] == settings.allowed_origins
    assert kwargs["allow_origin_regex"] == settings.allowed_origin_regex
    # DELETE removes a saved rule (spec 0014); without it the preflight fails first.
    assert "DELETE" in kwargs["allow_methods"]


@pytest.mark.parametrize(
    "origin",
    [
        "https://swing-scan-one.vercel.app",  # production, allowed by name
        "https://swing-scan-gnfq1yrk9-bridgegood.vercel.app",  # a real preview host
        "https://swing-scan-git-feat-x-comgood.vercel.app",  # a branch preview host
    ],
)
def test_deployed_cors_allows_production_and_previews(origin: str) -> None:
    res = _client_with_deploy_origins().get("/api/v1/health", headers={"Origin": origin})
    assert res.headers.get("access-control-allow-origin") == origin


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example.com",
        "https://swing-scan-one.vercel.app.evil.com",  # the unanchored regex trap
        "http://swing-scan-one.vercel.app",  # plain http, not https
        "https://other-app.vercel.app",  # someone else's Vercel project
    ],
)
def test_deployed_cors_rejects_everything_else(origin: str) -> None:
    res = _client_with_deploy_origins().get("/api/v1/health", headers={"Origin": origin})
    assert "access-control-allow-origin" not in res.headers
