"""`stop_pct`: a stop a fixed percent below the entry fill (B-1, B-2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .protocol import BarView, EntryContext, Position


@dataclass(frozen=True)
class StopPctExit:
    pct: float
    kind: Literal["stop"] = "stop"
    reason: Literal["stop_pct"] = "stop_pct"

    def on_entry(self, pos: Position, ctx: EntryContext) -> None:
        pos.stop_levels[self.reason] = pos.fill * (1 - self.pct / 100)

    def level(self, pos: Position, bar: BarView) -> float | None:
        return pos.stop_levels.get(self.reason)

    def at_close(self, pos: Position, bar: BarView) -> bool:
        return False
