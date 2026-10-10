"""`POST /backtest`: 1 config is a portfolio backtest, 2 to 6 the exit lab; 501 with no market."""

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
        # Any other `ValidationError` is a bug building the response, so it stays a 500.
        errors = exc.errors(include_url=False)
        if not all(error["type"] in use_cases.REQUEST_ERRORS for error in errors):
            raise
        raise RequestValidationError(
            [{**error, "loc": ("body", *error["loc"])} for error in errors]
        ) from exc
