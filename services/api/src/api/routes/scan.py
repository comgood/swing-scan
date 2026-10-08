"""`POST /scan`: runs `engine.api.scan` on the loaded market; 501 while none is loaded."""

from __future__ import annotations

import json
import logging
import sys

from fastapi import APIRouter
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from engine import api as use_cases
from engine.api import NotYetImplemented, ScanTiming
from engine.contracts import NotImplementedBody, ScanRequest, ScanResponse

from .. import state

router = APIRouter()


def _scan_logger() -> logging.Logger:
    """`api.scan` at INFO, one JSON line per scan on stdout (CloudWatch on Lambda)."""
    logger = logging.getLogger("api.scan")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    return logger


scan_log = _scan_logger()


def log_scan(timing: ScanTiming) -> None:
    scan_log.info(
        json.dumps(
            {
                "event": "scan",
                "duration_ms": round(timing.duration_ms, 3),
                "n_conditions": timing.n_conditions,
                "n_rows": timing.n_rows,
                "cache": timing.cache,
                "as_of": timing.as_of.isoformat(),
            }
        )
    )


@router.post(
    "/scan",
    response_model=ScanResponse,
    responses={501: {"model": NotImplementedBody, "description": "Not implemented yet"}},
)
def scan(request: ScanRequest) -> ScanResponse:
    """Tickers whose rule is true on `as_of` (S-1)."""
    if state.market is None:
        raise NotYetImplemented(7, "Loading the market")
    try:
        response, timing = use_cases.scan_timed(request, state.market)
    except ValidationError as exc:
        # `as_of_not_session`: the same 422 body as any other request error, under `body`.
        errors = exc.errors(include_url=False)
        raise RequestValidationError(
            [{**error, "loc": ("body", *error["loc"])} for error in errors]
        ) from exc
    log_scan(timing)
    return response
