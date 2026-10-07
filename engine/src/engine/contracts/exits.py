"""Exit configs: six exit variants tagged by `type`, grouped into named configs (doc 02 §5.3)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, ValidatorFunctionWrapHandler, WrapValidator
from pydantic_core import PydanticCustomError

from ._errors import ContractModel, Name, bounded, error_at


class StopPct(ContractModel):
    """Stop loss a fixed percent below the entry fill."""

    type: Literal["stop_pct"]
    pct: Annotated[float, bounded(1, 30)] = 8


class StopAtr(ContractModel):
    """Stop loss `k` ATRs (of length `n`) below the entry fill."""

    type: Literal["stop_atr"]
    k: Annotated[float, bounded(0.5, 6)] = 2
    n: Annotated[int, bounded(2, 50)] = 14


class Target(ContractModel):
    """Profit target a fixed percent above the entry fill."""

    type: Literal["target"]
    pct: Annotated[float, bounded(1, 100)] = 15


class TrailPct(ContractModel):
    """Trailing stop a fixed percent below the highest high since entry."""

    type: Literal["trail_pct"]
    pct: Annotated[float, bounded(2, 30)] = 10


class CloseBelowMa(ContractModel):
    """Exit at the next open after a close below the moving average."""

    type: Literal["close_below_ma"]
    ma: Literal["sma", "ema"] = "sma"
    n: Annotated[int, bounded(5, 200)] = 21


class TimeExit(ContractModel):
    """Exit after a fixed number of bars held."""

    type: Literal["time"]
    bars: Annotated[int, bounded(1, 120)] = 10


Exit = Annotated[
    StopPct | StopAtr | Target | TrailPct | CloseBelowMa | TimeExit,
    Field(discriminator="type"),
]

ExitType = Literal["stop_pct", "stop_atr", "target", "trail_pct", "close_below_ma", "time"]


def _distinct_types(value: Any, handler: ValidatorFunctionWrapHandler) -> Any:
    exits = handler(value)
    seen: set[str] = set()
    for i, exit_ in enumerate(exits):
        if exit_.type in seen:
            raise error_at(
                (i, "type"),
                PydanticCustomError(
                    "duplicate_exit_type",
                    "exit type {type} is already used in this config",
                    {"type": exit_.type},
                ),
                exit_.type,
            )
        seen.add(exit_.type)
    return exits


class ExitConfig(ContractModel):
    """A named set of 1 to 6 exits, each of a distinct type."""

    name: Name
    exits: Annotated[list[Exit], bounded(1, 6), WrapValidator(_distinct_types)]


def _distinct_names(value: Any, handler: ValidatorFunctionWrapHandler) -> Any:
    configs = handler(value)
    seen: set[str] = set()
    for i, config in enumerate(configs):
        if config.name in seen:
            raise error_at(
                (i, "name"),
                PydanticCustomError(
                    "duplicate_config_name",
                    "config name {name} is already used",
                    {"name": config.name},
                ),
                config.name,
            )
        seen.add(config.name)
    return configs


ExitConfigs = Annotated[list[ExitConfig], bounded(1, 6), WrapValidator(_distinct_names)]
"""1 to 6 configs with unique names. `configs[0]` is always the baseline config."""

STOP_TYPES: frozenset[str] = frozenset({"stop_pct", "stop_atr", "trail_pct"})
"""Exit types that define an initial stop, and so an R value (X-4)."""
