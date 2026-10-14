"""`step(position, bar)`: the one place exit precedence lives (doc 02 §7.2, spec 0007).

For a held position on bar b (the entry bar is b = 1, where steps 2 to 7 run after the
open fill):

1. a pending MA exit fills at the open, `ma`;
2. stops: `L = max(levels)`; `open <= L` fills at the open, else `low <= L` fills at L;
   equal levels go to `stop_pct`, then `stop_atr`, then `trail_pct`;
3. target: `open >= T` fills at the open, else `high >= T` fills at T (only when no stop);
4. time: fills at the close;
5. delisting fills at the close, `delisted`; in trade mode `b == horizon` fills, `horizon`;
6. `close_below_ma` schedules an exit at the next open;
7. the final bar fills at the close, `end_of_test`.

MAE and MFE then update with the exit bar limited to what was knowable before the fill.
"""

from __future__ import annotations

from engine.contracts import ExitReason

from .protocol import BarView, EntryContext, Exit, Fill, Position

STOP_ORDER = ("stop_pct", "stop_atr", "trail_pct")
"""Tie break between stops at the same level (spec 0007)."""


def open_position(
    ticker: str,
    entry_index: int,
    fill: float,
    shares: float,
    exits: list[Exit],
    ctx: EntryContext,
) -> Position:
    """A new position with every exit's entry levels set. The initial stop (for R) is the
    highest stop level at entry, or None when the config has no stop."""
    position = Position(ticker, entry_index, fill, shares, exits)
    for exit_ in exits:
        exit_.on_entry(position, ctx)
    if position.stop_levels:
        position.initial_stop = max(position.stop_levels.values())
    return position


def _stop_rank(reason: ExitReason) -> int:
    return STOP_ORDER.index(reason) if reason in STOP_ORDER else len(STOP_ORDER)


def _stop(position: Position, bar: BarView) -> Fill | None:
    top: float | None = None
    reason: ExitReason = "stop_pct"
    for exit_ in position.exits:  # the highest level; a tie goes to the earlier STOP_ORDER
        if exit_.kind != "stop" or (level := exit_.level(position, bar)) is None:
            continue
        if (
            top is None
            or level > top
            or (level == top and _stop_rank(exit_.reason) < _stop_rank(reason))
        ):
            top, reason = level, exit_.reason
    if top is None:
        return None
    if bar.open <= top:
        return Fill(bar.open, reason, "open")
    if bar.low <= top:
        return Fill(top, reason, "intraday_stop")
    return None


def _target(position: Position, bar: BarView) -> Fill | None:
    for exit_ in position.exits:
        if exit_.kind != "target" or (level := exit_.level(position, bar)) is None:
            continue
        if bar.open >= level:
            return Fill(bar.open, exit_.reason, "open")
        if bar.high >= level:
            return Fill(level, exit_.reason, "intraday_target")
    return None


def _at_close(position: Position, bar: BarView) -> Fill | None:
    for exit_ in position.exits:
        if exit_.kind == "time" and exit_.at_close(position, bar):
            return Fill(bar.close, exit_.reason, "close")
    if bar.is_delisting:
        return Fill(bar.close, "delisted", "close")
    if bar.horizon is not None and bar.b == bar.horizon:
        return Fill(bar.close, "horizon", "close")
    for exit_ in position.exits:
        if exit_.kind == "ma" and exit_.at_close(position, bar):
            position.pending_ma = True
    if bar.is_final:
        return Fill(bar.close, "end_of_test", "close")
    return None


def _decide(position: Position, bar: BarView) -> Fill | None:
    if position.pending_ma:
        return Fill(bar.open, "ma", "open")
    return _stop(position, bar) or _target(position, bar) or _at_close(position, bar)


def _track_extremes(position: Position, bar: BarView, fill: Fill | None) -> None:
    """MAE and MFE through this bar; the exit bar contributes only what came before it."""
    if fill is None or fill.at == "close":
        low, high = bar.low, bar.high
    elif fill.at == "open":
        low = high = bar.open
    elif fill.at == "intraday_stop":
        low, high = fill.price, bar.open
    else:  # intraday_target
        low, high = bar.open, fill.price
    # Plain comparisons, not min() and max(): this runs once per held bar (spec 0009, AC-11).
    if low < position.mae_low:
        position.mae_low = low
    if high > position.mfe_high:
        position.mfe_high = high


def step(position: Position, bar: BarView) -> Fill | None:
    """Run one bar of a held position; return its exit fill, or None to keep holding."""
    position.bars_held = bar.b
    fill = _decide(position, bar)
    _track_extremes(position, bar, fill)
    if fill is None and bar.high > position.high_water:
        position.high_water = bar.high
    return fill
