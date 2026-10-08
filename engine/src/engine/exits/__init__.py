"""Exits: the `Exit` protocol, the exit classes and the one shared `step()` (spec 0007)."""

from __future__ import annotations

from engine.contracts import (
    CloseBelowMa,
    ExitConfig,
    StopAtr,
    StopPct,
    Target,
    TimeExit,
    TrailPct,
)
from engine.indicators import IndicatorKey

from .close_below_ma import CloseBelowMaExit
from .columns import Column, floats
from .protocol import BarView, EntryContext, Exit, ExitKind, Fill, FillAt, Position
from .step import STOP_ORDER, open_position, step
from .stop_atr import StopAtrExit
from .stop_pct import StopPctExit
from .target import TargetExit
from .time import TimeExitRule
from .trail_pct import TrailPctExit


def build_exits(config: ExitConfig, column: Column) -> list[Exit]:
    """The config's exits as objects, in config order. `column` looks up the indicator
    columns `stop_atr` and `close_below_ma` read (pass `IndicatorCache.get`)."""
    built: list[Exit] = []
    for exit_ in config.exits:
        match exit_:
            case StopPct():
                built.append(StopPctExit(exit_.pct))
            case StopAtr():
                built.append(StopAtrExit(exit_.k, floats(column, IndicatorKey("atr", exit_.n))))
            case Target():
                built.append(TargetExit(exit_.pct))
            case TrailPct():
                built.append(TrailPctExit(exit_.pct))
            case CloseBelowMa():
                built.append(CloseBelowMaExit(floats(column, IndicatorKey(exit_.ma, exit_.n))))
            case TimeExit():
                built.append(TimeExitRule(exit_.bars))
    return built


__all__ = [
    "STOP_ORDER",
    "BarView",
    "CloseBelowMaExit",
    "Column",
    "EntryContext",
    "Exit",
    "ExitKind",
    "Fill",
    "FillAt",
    "Position",
    "StopAtrExit",
    "StopPctExit",
    "TargetExit",
    "TimeExitRule",
    "TrailPctExit",
    "build_exits",
    "open_position",
    "step",
]
