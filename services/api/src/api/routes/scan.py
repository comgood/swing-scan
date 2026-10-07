"""`POST /scan`: validates the full request now; 501 until scope feature 8."""

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
        raise NotYetImplemented(8, "scan")
    return use_cases.scan(request, state.market)
