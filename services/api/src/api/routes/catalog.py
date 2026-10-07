"""Static reference data: the indicator registry, the rule templates and the dataset meta."""

from __future__ import annotations

from fastapi import APIRouter

from engine.contracts import (
    CONTRACT_VERSION,
    INDICATOR_SPECS,
    TEMPLATES,
    IndicatorSpec,
    MetaResponse,
    TemplateOut,
)

from .. import state

router = APIRouter()


@router.get("/indicators")
def indicators() -> list[IndicatorSpec]:
    """Every indicator with its `n` bounds, from the same registry that validates rules."""
    return list(INDICATOR_SPECS.values())


@router.get("/templates")
def templates() -> list[TemplateOut]:
    """The two built in rule templates (doc 02 §5.2)."""
    return TEMPLATES


@router.get("/meta")
def meta() -> MetaResponse:
    """The contract version, plus the dataset once scope feature 7 loads one."""
    # `data` and `oos_start` come from the loaded market once feature 7 exists.
    data = state.market.meta if state.market is not None else None
    return MetaResponse(contract_version=CONTRACT_VERSION, data=data, oos_start=None)
