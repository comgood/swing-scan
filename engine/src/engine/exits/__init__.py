"""Exits: the `Exit` protocol, the exit classes and the one shared `step()` (spec 0007)."""

from __future__ import annotations

from engine.contracts import ExitConfig, StopPct, TimeExit

from .protocol import BarView, EntryContext, Exit, ExitKind, Fill, FillAt, Position
from .step import STOP_ORDER, open_position, step
from .stop_pct import StopPctExit
from .time import TimeExitRule

LATER_EXITS: dict[str, int] = {
    "stop_atr": 11,
    "target": 11,
    "trail_pct": 11,
    "close_below_ma": 11,
}
"""Exit types a later scope feature builds; a config using one answers 501."""


class ExitNotBuilt(Exception):
    """A config uses an exit type whose scope feature has not landed."""

    def __init__(self, exit_type: str) -> None:
        self.exit_type = exit_type
        self.feature = LATER_EXITS[exit_type]
        super().__init__(exit_type)


def build_exits(config: ExitConfig) -> list[Exit]:
    """The config's exits as objects, in config order. Raises `ExitNotBuilt`."""
    built: list[Exit] = []
    for exit_ in config.exits:
        if isinstance(exit_, StopPct):
            built.append(StopPctExit(exit_.pct))
        elif isinstance(exit_, TimeExit):
            built.append(TimeExitRule(exit_.bars))
        else:
            raise ExitNotBuilt(exit_.type)
    return built


__all__ = [
    "LATER_EXITS",
    "STOP_ORDER",
    "BarView",
    "EntryContext",
    "Exit",
    "ExitKind",
    "ExitNotBuilt",
    "Fill",
    "FillAt",
    "Position",
    "StopPctExit",
    "TimeExitRule",
    "build_exits",
    "open_position",
    "step",
]
