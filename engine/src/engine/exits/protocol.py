"""The `Exit` protocol and the shapes `step()` works on (doc 02 §7.2, spec 0007).

Exits are small objects that only report levels and close conditions. The precedence
between them lives in one place, `step()`; no exit is special cased anywhere else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from engine.contracts import ExitReason

ExitKind = Literal["stop", "target", "time", "ma"]
FillAt = Literal["open", "intraday_stop", "intraday_target", "close"]


@dataclass(frozen=True)
class BarView:
    """One bar of a held position, as `step()` sees it."""

    open: float
    high: float
    low: float
    close: float
    b: int
    """Bar number in the trade: the entry bar is 1."""
    is_delisting: bool
    """The bar's date is the ticker's `delisted_on`."""
    is_final: bool
    """The window's last session, or the ticker's last bar in the cut market."""
    horizon: int | None = None
    """Trade mode only: the bar at which a `horizon` exit closes the trade."""
    row: int | None = None
    """Row in `market.bars`, for exits that read an indicator on this bar (`close_below_ma`)."""


@dataclass(frozen=True)
class EntryContext:
    """What an exit may read when the position opens (feature 11's `stop_atr` reads ATR)."""

    signal_row: int
    """Row of the signal bar in `market.bars`."""


@dataclass
class Position:
    """One open position. Prices are the slipped entry fill, as every level is."""

    ticker: str
    entry_index: int
    """Session index (portfolio) or bar index (trade walker) of the entry bar."""
    fill: float
    shares: float
    exits: list[Exit]
    initial_stop: float | None = None
    bars_held: int = 0
    stop_levels: dict[str, float] = field(default_factory=dict)
    pending_ma: bool = False
    high_water: float = 0.0
    mae_low: float = 0.0
    mfe_high: float = 0.0

    def __post_init__(self) -> None:
        self.high_water = self.mae_low = self.mfe_high = self.fill


@dataclass(frozen=True)
class Fill:
    """An exit: `price` is before slippage, which the caller applies (× (1 - slip))."""

    price: float
    reason: ExitReason
    at: FillAt


class Exit(Protocol):
    """One exit of a config. `kind` decides which step of the precedence reads it."""

    @property
    def kind(self) -> ExitKind: ...

    @property
    def reason(self) -> ExitReason: ...

    def on_entry(self, pos: Position, ctx: EntryContext) -> None:
        """Set any level that is fixed at entry (`stop_pct`, `stop_atr`, `target`)."""
        ...

    def level(self, pos: Position, bar: BarView) -> float | None:
        """The stop or target level on this bar (stop and target kinds)."""
        ...

    def at_close(self, pos: Position, bar: BarView) -> bool:
        """Whether to exit at this bar's close (time) or schedule the next open (ma)."""
        ...
