"""`stop_atr`: a stop `k` ATRs below the entry fill, ATR(n) read at the signal bar (B-3)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .columns import Floats
from .protocol import BarView, EntryContext, Position


@dataclass(frozen=True, eq=False)
class StopAtrExit:
    k: float
    atr: Floats
    """ATR(n) per row of `market.bars`, NaN during warm up."""
    kind: Literal["stop"] = "stop"
    reason: Literal["stop_atr"] = "stop_atr"

    def on_entry(self, pos: Position, ctx: EntryContext) -> None:
        atr = float(self.atr[ctx.signal_row])
        if not math.isnan(atr):  # no ATR yet at the signal bar: this trade has no ATR stop
            pos.stop_levels[self.reason] = pos.fill - self.k * atr

    def level(self, pos: Position, bar: BarView) -> float | None:
        return pos.stop_levels.get(self.reason)

    def at_close(self, pos: Position, bar: BarView) -> bool:
        return False
