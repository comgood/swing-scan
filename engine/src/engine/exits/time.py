"""`time`: exit at the close of bar N, the entry bar being bar 1 (B-7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .protocol import BarView, EntryContext, Position


@dataclass(frozen=True)
class TimeExitRule:
    bars: int
    kind: Literal["time"] = "time"
    reason: Literal["time"] = "time"

    def on_entry(self, pos: Position, ctx: EntryContext) -> None:
        return None

    def level(self, pos: Position, bar: BarView) -> float | None:
        return None

    def at_close(self, pos: Position, bar: BarView) -> bool:
        return bar.b == self.bars
