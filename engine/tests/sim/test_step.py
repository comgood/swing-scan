"""`step()` precedence and the exit bar cap on MAE and MFE (spec 0007, AC-1 to AC-4)."""

from __future__ import annotations

import pytest

from engine.exits import (
    BarView,
    EntryContext,
    Exit,
    Position,
    StopPctExit,
    TimeExitRule,
    open_position,
    step,
)

FILL = 10.0
CTX = EntryContext(signal_row=0)


def _position(*exits: Exit) -> Position:
    return open_position("AAA", 0, FILL, 1.0, list(exits), CTX)


def _bar(
    o: float,
    h: float,
    lo: float,
    c: float,
    b: int = 2,
    *,
    delist: bool = False,
    final: bool = False,
) -> BarView:
    return BarView(o, h, lo, c, b, is_delisting=delist, is_final=final)


def test_stop_pct_sets_the_initial_stop() -> None:
    position = _position(StopPctExit(8))
    assert position.stop_levels == {"stop_pct": pytest.approx(9.2)}
    assert position.initial_stop == pytest.approx(9.2)
    assert _position(TimeExitRule(3)).initial_stop is None


def test_an_intraday_stop_fills_at_the_level() -> None:
    fill = step(_position(StopPctExit(8)), _bar(9.8, 9.9, 9.0, 9.3))
    assert fill is not None
    assert fill.price == pytest.approx(9.2)
    assert (fill.reason, fill.at) == ("stop_pct", "intraday_stop")


def test_a_gap_below_the_stop_fills_at_the_open() -> None:
    fill = step(_position(StopPctExit(8)), _bar(9.0, 9.1, 8.9, 9.0))
    assert fill is not None
    assert (fill.price, fill.reason, fill.at) == (9.0, "stop_pct", "open")


def test_time_fills_at_the_close_of_bar_n_only() -> None:
    position = _position(TimeExitRule(3))
    assert step(position, _bar(10, 11, 9.5, 10.5, b=2)) is None
    fill = step(position, _bar(10.5, 11, 10, 10.7, b=3))
    assert fill is not None
    assert (fill.price, fill.reason, fill.at) == (10.7, "time", "close")


@pytest.mark.parametrize(
    ("bar", "reason"),
    [
        (_bar(10, 10, 9.0, 9.5, b=3, delist=True, final=True), "stop_pct"),  # stop beats all
        (_bar(10, 11, 9.5, 10.5, b=3, delist=True, final=True), "time"),  # time beats delisting
        (_bar(10, 11, 9.5, 10.5, b=2, delist=True, final=True), "delisted"),  # beats end_of_test
        (_bar(10, 11, 9.5, 10.5, b=2, final=True), "end_of_test"),
    ],
)
def test_same_bar_precedence(bar: BarView, reason: str) -> None:
    fill = step(_position(StopPctExit(8), TimeExitRule(3)), bar)
    assert fill is not None
    assert fill.reason == reason


def test_mae_and_mfe_take_full_bars_until_the_exit_bar() -> None:
    position = _position(StopPctExit(8))
    step(position, _bar(10, 10.4, 9.8, 10.2, b=1))
    # Intraday stop on bar 2: MAE takes the level, MFE only the open (the high 10.6 is ignored).
    step(position, _bar(9.7, 10.6, 9.0, 9.2))
    assert position.mae_low == pytest.approx(9.2)
    assert position.mfe_high == 10.4
    assert position.bars_held == 2


def test_a_gap_exit_bar_contributes_only_its_open() -> None:
    position = _position(StopPctExit(8))
    step(position, _bar(10, 10.4, 9.8, 10.2, b=1))
    step(position, _bar(9.0, 9.3, 8.7, 9.1))
    assert (position.mae_low, position.mfe_high) == (9.0, 10.4)


def test_a_close_exit_bar_contributes_the_full_bar() -> None:
    position = _position(TimeExitRule(1))
    step(position, _bar(10, 10.9, 9.4, 10.3, b=1))
    assert (position.mae_low, position.mfe_high) == (9.4, 10.9)


def test_extremes_start_at_the_fill() -> None:
    position = _position(TimeExitRule(1))
    step(position, _bar(10.5, 10.8, 10.2, 10.6, b=1))
    assert (position.mae_low, position.mfe_high) == (FILL, 10.8)
