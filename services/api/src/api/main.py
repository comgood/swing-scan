"""FastAPI app. Run locally with `make dev`; on Lambda via the Lambda Web Adapter (spec 0001)."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

import engine
from engine.api import NotYetImplemented
from engine.contracts import CONTRACT_VERSION

from .routes import backtest, catalog, scan
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
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

v1 = APIRouter(prefix="/api/v1")


@v1.get("/health")
def health() -> dict[str, str]:
    """Readiness check for the Lambda Web Adapter and the web app's warm up ping."""
    return {"status": "ok", "data_mode": settings.data_mode, "version": engine.__version__}


v1.include_router(catalog.router)
v1.include_router(scan.router)
v1.include_router(backtest.router)
app.include_router(v1)


@app.exception_handler(NotYetImplemented)
async def not_yet_implemented(_: Request, exc: NotYetImplemented) -> JSONResponse:
    """Only this type maps to 501; a stray `NotImplementedError` stays a 500."""
    return JSONResponse(status_code=501, content={"detail": str(exc)})
