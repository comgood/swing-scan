"""The per trade walker and the trade record, shared by both loops (doc 02 §7.3, spec 0007).

`walk_trade()` is the loop feature 12's trade mode runs; the portfolio day loop uses the same
`step()` and `make_trade()`, so one trade exits identically in both.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from engine.contracts import Trade

from ..exits import EntryContext, Exit, Fill, Position, open_position, step
from .bars import BarArrays


@dataclass(frozen=True)
class TradeOutcome:
    position: Position
    fill: Fill
    exit_row: int


def walk_trade(
    entry_row: int,
    entry_fill: float,
    exits: list[Exit],
    bars: BarArrays,
    ctx: EntryContext,
    horizon: int | None = None,
) -> TradeOutcome:
    """Hold one unit from `entry_row` until an exit; the ticker's last row always exits."""
    position = open_position(bars.ticker[entry_row], entry_row, entry_fill, 1.0, exits, ctx)
    view = bars.view
    row = entry_row
    while True:
        fill = step(position, view(row, row - entry_row + 1, is_final=False, horizon=horizon))
        if fill is not None:
            return TradeOutcome(position, fill, row)
        row += 1


def make_trade(
    position: Position,
    fill: Fill,
    entry_date: date,
    exit_date: date,
    slip: float,
    oos_start: date,
) -> Trade:
    """The contract `Trade`: slipped prices, return, R, MAE and MFE, unrounded."""
    entry = position.fill
    exit_price = fill.price * (1 - slip)
    risk = entry - position.initial_stop if position.initial_stop is not None else None

    def in_r(price: float) -> float | None:
        return (price - entry) / risk if risk else None

    return Trade(
        ticker=position.ticker,
        entry_date=entry_date,
        entry_price=entry,
        exit_date=exit_date,
        exit_price=exit_price,
        return_pct=(exit_price / entry - 1) * 100,
        bars_held=position.bars_held,
        exit_reason=fill.reason,
        r_multiple=in_r(exit_price),
        mae_pct=(position.mae_low / entry - 1) * 100,
        mfe_pct=(position.mfe_high / entry - 1) * 100,
        mae_r=in_r(position.mae_low),
        mfe_r=in_r(position.mfe_high),
        segment="oos" if entry_date >= oos_start else "is",
    )
