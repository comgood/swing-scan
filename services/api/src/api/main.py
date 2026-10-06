"""FastAPI app. Run locally with `make dev`; on Lambda via the Lambda Web Adapter (spec 0001)."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

import engine

from .settings import Settings

settings = Settings.from_env()

app = FastAPI(title="Swing Scan API", version=engine.__version__)

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


app.include_router(v1)
