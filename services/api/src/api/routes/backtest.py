"""`POST /backtest`: one config runs the portfolio backtest; 501 for what is not built yet."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

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
        raise NotYetImplemented(7, "Loading the market")
    try:
        return use_cases.backtest(request, state.market)
    except ValidationError as exc:
        # `range_outside_data`: the same 422 body as any other request error, under `body`.
        errors = exc.errors(include_url=False)
        raise RequestValidationError(
            [{**error, "loc": ("body", *error["loc"])} for error in errors]
        ) from exc
