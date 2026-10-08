"""`close_below_ma`: a close below the moving average exits at the next open (B-6).

`at_close` only reports the condition; `step()` turns it into `pending_ma` and fills it at
the next bar's open.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .columns import Floats
from .protocol import BarView, EntryContext, Position


@dataclass(frozen=True, eq=False)
class CloseBelowMaExit:
    ma: Floats
    """The SMA or EMA per row of `market.bars`, NaN during warm up (never below the close)."""
    kind: Literal["ma"] = "ma"
    reason: Literal["ma"] = "ma"

    def on_entry(self, pos: Position, ctx: EntryContext) -> None:
        return None

    def level(self, pos: Position, bar: BarView) -> float | None:
        return None

    def at_close(self, pos: Position, bar: BarView) -> bool:
        if bar.row is None:
            raise ValueError("close_below_ma needs the bar's market row")
        return bar.close < float(self.ma[bar.row])  # NaN compares False: no exit in warm up
