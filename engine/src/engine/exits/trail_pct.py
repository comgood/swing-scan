"""`trail_pct`: a stop a fixed percent below the high water mark (B-5).

`step()` raises `Position.high_water` after every bar the position survives, starting at the
entry fill, so the level on bar b reads the highest high through b - 1 and only rises.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .protocol import BarView, EntryContext, Position


@dataclass(frozen=True)
class TrailPctExit:
    pct: float
    kind: Literal["stop"] = "stop"
    reason: Literal["trail_pct"] = "trail_pct"

    def on_entry(self, pos: Position, ctx: EntryContext) -> None:
        pos.stop_levels[self.reason] = pos.fill * (1 - self.pct / 100)  # counts toward R

    def level(self, pos: Position, bar: BarView) -> float | None:
        return pos.high_water * (1 - self.pct / 100)

    def at_close(self, pos: Position, bar: BarView) -> bool:
        return False
