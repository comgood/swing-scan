"""The portfolio day loop (doc 02 §7.1 and §7.3, spec 0007).

Per session d:
1. every held position steps on its bars dated up to d (ticker A to Z); exits credit cash at
   fill × (1 - slip);
2. accepted signals from d - 1, minus tickers held at close d - 1 and tickers with no bar on d,
   ranked by `rs(126)` descending (nulls last) then ticker, fill the slots free at close d - 1;
3. each entry fills at open(d) × (1 + slip) for `min(equity(d - 1) / max_positions, cash)`,
   where cash is the cash at close d - 1 less today's earlier entries: no exit on d, whatever
   its fill time, funds an entry on d (spec 0007 decision 4). Then it steps on bar d as its
   first bar;
4. everything is marked at close(d), a ticker with no bar on d at its last close.

The loop aligns on dates and never reads a bar dated after d; `b` counts the ticker's own
bars, as in `walk_trade()`. Signals that find no slot are dropped, never queued.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from ..exits import EntryContext, Exit, Fill, Position, open_position, step
from .bars import BarArrays, Floats

START_EQUITY = 100.0


@dataclass(frozen=True)
class ClosedTrade:
    position: Position
    fill: Fill
    entry_row: int
    exit_row: int


@dataclass
class PortfolioRun:
    trades: list[ClosedTrade] = field(default_factory=list)
    equity: list[float] = field(default_factory=list)
    """Equity at each session's close, starting from 100."""
    invested: list[float] = field(default_factory=list)
    """Share of equity held in positions at each close, 0 to 1."""


def _rank_key(rs: Floats, bars: BarArrays) -> Callable[[int], tuple[bool, float, str]]:
    def key(row: int) -> tuple[bool, float, str]:
        value = float(rs[row])
        return (math.isnan(value), -value if not math.isnan(value) else 0.0, bars.ticker[row])

    return key


def run_portfolio(
    sessions: list[date],
    signals_by_session: dict[int, list[int]],
    rs126: Floats,
    bars: BarArrays,
    exits: list[Exit],
    max_positions: int,
    slip: float,
) -> PortfolioRun:
    """Walk `sessions`; `signals_by_session[i]` are the signal rows on session i."""
    run = PortfolioRun()
    cash = START_EQUITY
    equity = START_EQUITY
    held: dict[str, tuple[Position, int, int]] = {}  # ticker -> (position, entry row, row)
    key = _rank_key(rs126, bars)
    last = len(sessions) - 1

    def close(ticker: str, fill: Fill, row: int) -> None:
        nonlocal cash
        position, entry_row, _ = held.pop(ticker)
        cash += position.shares * fill.price * (1 - slip)
        run.trades.append(ClosedTrade(position, fill, entry_row, row))

    n_rows = len(bars.ticker)

    def next_bar(row: int, ticker: str, day: date) -> int | None:
        """The ticker's row after `row` when it is dated on or before `day`, else None."""
        nxt = row + 1
        if nxt < n_rows and bars.ticker[nxt] == ticker and bars.date[nxt] <= day:
            return nxt
        return None

    for i, day in enumerate(sessions):
        held_before = set(held)
        free = max_positions - len(held_before)
        budget = cash  # the cash at close d - 1: no exit on d funds an entry on d

        for ticker in sorted(held):
            position, entry_row, row = held[ticker]
            # Every bar of the ticker up to today, in order: none on a missing session (the
            # position keeps its last close), more than one if it traded off the calendar.
            while (nxt := next_bar(row, ticker, day)) is not None:
                row = nxt
                held[ticker] = (position, entry_row, row)
                final = i == last and bars.date[row] == day
                view = bars.view(row, row - entry_row + 1, is_final=final)
                if (fill := step(position, view)) is not None:
                    close(ticker, fill, row)
                    break

        # A ticker with no bar today cannot be bought at today's open; its signal is dropped.
        candidates = [
            r
            for r in signals_by_session.get(i - 1, [])
            if bars.ticker[r] not in held_before
            and (nxt := next_bar(r, bars.ticker[r], day)) is not None
            and bars.date[nxt] == day
        ]
        for signal_row in sorted(candidates, key=key)[: max(free, 0)]:
            notional = min(equity / max_positions, budget)
            if notional <= 0:
                continue
            budget -= notional
            row = signal_row + 1
            fill_price = float(bars.open[row]) * (1 + slip)
            ticker = bars.ticker[row]
            position = open_position(
                ticker, i, fill_price, notional / fill_price, exits, EntryContext(signal_row)
            )
            cash -= notional
            held[ticker] = (position, row, row)
            if (fill := step(position, bars.view(row, 1, is_final=i == last))) is not None:
                close(ticker, fill, row)

        value = sum(p.shares * float(bars.close[r]) for p, _, r in held.values())
        equity = cash + value
        run.equity.append(equity)
        run.invested.append(value / equity if equity > 0 else 0.0)
    return run


def signal_sessions(
    signal_rows: np.ndarray[tuple[int], np.dtype[np.int64]],
    bars: BarArrays,
    session_index: dict[date, int],
) -> dict[int, list[int]]:
    """Group signal rows by the session index of their date."""
    grouped: dict[int, list[int]] = {}
    for row in signal_rows.tolist():
        index = session_index.get(bars.date[row])
        if index is not None:
            grouped.setdefault(index, []).append(row)
    return grouped
