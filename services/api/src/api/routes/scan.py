"""`POST /scan`: runs `engine.api.scan` on the loaded market; 501 while none is loaded."""

from __future__ import annotations

from fastapi import APIRouter

from engine import api as use_cases
from engine.api import NotYetImplemented
from engine.contracts import NotImplementedBody, ScanRequest, ScanResponse

from .. import state

router = APIRouter()


@router.post(
    "/scan",
    response_model=ScanResponse,
    responses={501: {"model": NotImplementedBody, "description": "Not implemented yet"}},
)
def scan(request: ScanRequest) -> ScanResponse:
    """Tickers whose rule is true on `as_of` (S-1)."""
    if state.market is None:
        raise NotYetImplemented(7, "Loading the market")
    return use_cases.scan(request, state.market)
