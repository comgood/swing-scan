"""FastAPI app. Run locally with `make dev`; on Lambda via the Lambda Web Adapter (spec 0001)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

import engine
from engine.api import NotYetImplemented
from engine.contracts import CONTRACT_VERSION

from . import state
from .auth import ENABLED as AUTH_ENABLED
from .routes import auth, backtest, catalog, rules, scan
from .settings import Settings

settings = Settings.from_env()

# `info.version` is the contract version; `/health` still reports the engine (spec 0002).
# One schema per model (no `-Input`/`-Output` pairs), so the generated TS names stay clean.
app = FastAPI(
    title="Swing Scan API",
    version=CONTRACT_VERSION,
    separate_input_output_schemas=False,
)

# Function URLs do not compress responses, so the app does (spec 0001).
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=settings.allowed_origin_regex,
    # DELETE for removing a saved rule (spec 0014); without it the preflight fails
    # before the request is ever made.
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
    # The session cookie (spec 0015). Without this the browser attaches it to nothing and
    # every signed in request looks signed out, with no error anywhere to explain it.
    #
    # Only when accounts actually run here. The deployed function allows Vercel preview
    # origins through `ALLOWED_ORIGIN_REGEX`, and there is no reason to make every one of them
    # a credentialed origin on a public API for a feature that answers 501 there.
    allow_credentials=AUTH_ENABLED,
)


@app.middleware("http")
async def check_the_store(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """The one place a request can notice the store's dataset changed (spec 0011, AC-7).

    Feature 20's refresh extends this hook rather than adding a second mechanism.
    """
    state.refresh_if_changed()
    return await call_next(request)


v1 = APIRouter(prefix="/api/v1")


@v1.get("/health")
def health() -> dict[str, str]:
    """Readiness check for the Lambda Web Adapter and the web app's warm up ping."""
    # The loaded dataset's own mode, so the web app's banner (U-1, U-2) describes the data on
    # screen rather than an environment variable someone forgot to set. Kept out of the
    # docstring: FastAPI publishes that as the route description, and this is not contract text.
    mode = state.market.meta.data_mode if state.market else settings.data_mode
    return {"status": "ok", "data_mode": mode, "version": engine.__version__}


v1.include_router(catalog.router)
v1.include_router(scan.router)
v1.include_router(backtest.router)
v1.include_router(rules.router)
v1.include_router(auth.router)
app.include_router(v1)


@app.exception_handler(NotYetImplemented)
async def not_yet_implemented(_: Request, exc: NotYetImplemented) -> JSONResponse:
    """Only this type maps to 501; a stray `NotImplementedError` stays a 500."""
    return JSONResponse(status_code=501, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI's 422 body, except that the auth routes never echo what was rejected.

    The default body carries `input`, the value that failed. On `/auth/*` that value is the
    password, so the default would hand a rejected password straight back in the response, and
    AC-2 says a password is never readable anywhere. `SecretStr` masks `repr` but **not** this,
    which a test pins.

    Only the auth routes are stripped. Everywhere else `input` is what lets the rule builder
    show which field went wrong (U-7), so dropping it project wide would break a real feature
    to fix a problem those routes do not have.
    """
    errors: list[dict[str, Any]] = [dict(error) for error in exc.errors()]
    if request.url.path.startswith("/api/v1/auth/"):
        for error in errors:
            error.pop("input", None)
            error.pop("ctx", None)
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": errors}))
