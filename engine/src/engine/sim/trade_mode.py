"""Trade mode, the exit lab's loop (doc 02 §7.3, spec 0009).

Every entry is one unit notional trade, same ticker overlap allowed. The entry list is built
once and every config walks it with `walk_trade()`, so the only thing that changes between
configs is the exit objects `step()` reads. Nothing here looks at an exit type.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date

from engine.contracts import Trade
from engine.contracts.backtest import Segment

from ..exits import EntryContext, Exit
from .bars import BarArrays
from .walk import make_trade, walk_trade


@dataclass(frozen=True)
class EntryPoint:
    """One entry: the signal on `signal_row`, filled at the next row's open plus slippage."""

    ticker: str
    signal_row: int
    entry_row: int
    entry_date: date
    entry_fill: float
    segment: Segment


@dataclass(frozen=True)
class ConfigTrades:
    config_index: int
    strategy: list[Trade]
    random: list[Trade] = field(default_factory=list)


def entry_points(
    signal_rows: Iterable[int], bars: BarArrays, slip: float, oos_start: date
) -> list[EntryPoint]:
    """Entries at open(signal row + 1) × (1 + slip), sorted by (entry date, ticker).

    A signal is never on a ticker's last row (B-15), so the next row is the same ticker.
    """
    points = []
    for signal_row in signal_rows:
        row = signal_row + 1
        day = bars.date[row]
        points.append(
            EntryPoint(
                ticker=bars.ticker[row],
                signal_row=signal_row,
                entry_row=row,
                entry_date=day,
                entry_fill=float(bars.open[row]) * (1 + slip),
                segment="oos" if day >= oos_start else "is",
            )
        )
    return sorted(points, key=lambda p: (p.entry_date, p.ticker))


def walk_entries(
    entries: Sequence[EntryPoint],
    exits: list[Exit],
    bars: BarArrays,
    horizon: int,
    slip: float,
    oos_start: date,
) -> list[Trade]:
    """Each entry held through `step()` until an exit, the horizon or its last bar."""
    trades = []
    for entry in entries:
        outcome = walk_trade(
            entry.entry_row,
            entry.entry_fill,
            exits,
            bars,
            EntryContext(entry.signal_row),
            horizon=horizon,
        )
        trades.append(
            make_trade(
                outcome.position,
                outcome.fill,
                entry.entry_date,
                bars.date[outcome.exit_row],
                slip,
                oos_start,
            )
        )
    return trades


def run_trade_mode(
    strategy: Sequence[EntryPoint],
    random: Sequence[EntryPoint],
    exit_sets: Sequence[list[Exit]],
    bars: BarArrays,
    horizon: int,
    slip: float,
    oos_start: date,
) -> list[ConfigTrades]:
    """Both entry lists through every config's exits, one `ConfigTrades` per config."""
    return [
        ConfigTrades(
            config_index=i,
            strategy=walk_entries(strategy, exits, bars, horizon, slip, oos_start),
            random=walk_entries(random, exits, bars, horizon, slip, oos_start),
        )
        for i, exits in enumerate(exit_sets)
    ]
