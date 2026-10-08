"""`target`: a profit target a fixed percent above the entry fill (B-4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .protocol import BarView, EntryContext, Position


@dataclass(frozen=True)
class TargetExit:
    pct: float
    kind: Literal["target"] = "target"
    reason: Literal["target"] = "target"

    def on_entry(self, pos: Position, ctx: EntryContext) -> None:
        return None

    def level(self, pos: Position, bar: BarView) -> float | None:
        return pos.fill * (1 + self.pct / 100)

    def at_close(self, pos: Position, bar: BarView) -> bool:
        return False
