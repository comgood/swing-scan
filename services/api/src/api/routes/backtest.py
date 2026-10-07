"""`POST /backtest`: validates the full request now; 501 until scope feature 9."""

from __future__ import annotations

from fastapi import APIRouter

from engine import api as use_cases
from engine.api import NotYetImplemented
from engine.contracts import BacktestRequest, BacktestResponse, NotImplementedBody

from .. import state

router = APIRouter()


@router.post(
    "/backtest",
    response_model=BacktestResponse,
    responses={501: {"model": NotImplementedBody, "description": "Not implemented yet"}},
)
def backtest(request: BacktestRequest) -> BacktestResponse:
    """1 config runs a portfolio backtest; 2 to 6 configs run the exit lab (trade mode)."""
    if state.market is None:
        raise NotYetImplemented(9, "backtest")
    return use_cases.backtest(request, state.market)
