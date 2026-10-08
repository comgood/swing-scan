"""Feature 11 exits behind the one `step()`: hand values and same bar precedence (B-3 to B-6)."""

from __future__ import annotations

import math

import numpy as np
import polars as pl
import pytest

from engine.contracts import ExitConfig
from engine.exits import (
    BarView,
    CloseBelowMaExit,
    EntryContext,
    Exit,
    Position,
    StopAtrExit,
    StopPctExit,
    TargetExit,
    TimeExitRule,
    TrailPctExit,
    build_exits,
    open_position,
    step,
)
from engine.indicators import IndicatorKey

FILL = 10.0
NAN = math.nan


def _position(*exits: Exit, signal_row: int = 0) -> Position:
    return open_position("AAA", 0, FILL, 1.0, list(exits), EntryContext(signal_row))


def _bar(o: float, h: float, lo: float, c: float, b: int = 2, row: int = 0) -> BarView:
    return BarView(o, h, lo, c, b, is_delisting=False, is_final=False, row=row)


def _atr(*values: float, k: float = 2) -> StopAtrExit:
    return StopAtrExit(k, np.array(values))


ATR_AT_9 = _atr(2.0, k=0.5)  # 10 - 0.5 x 2.0 = 9.0, the level of a 10% stop or trail


# ------------------------------------------------------------------ stop_atr (B-3)


def test_stop_atr_is_fill_minus_k_times_the_signal_bar_atr() -> None:
    position = _position(_atr(9.9, 2.0, 9.9), signal_row=1)
    assert position.stop_levels == {"stop_atr": pytest.approx(6.0)}
    assert position.initial_stop == pytest.approx(6.0)

    fill = step(position, _bar(7.0, 7.2, 5.5, 6.5))
    assert fill is not None
    assert fill.price == pytest.approx(6.0)
    assert (fill.reason, fill.at) == ("stop_atr", "intraday_stop")


def test_stop_atr_without_an_atr_at_the_signal_bar_sets_no_stop() -> None:
    position = _position(_atr(NAN))
    assert position.stop_levels == {}
    assert position.initial_stop is None
    assert step(position, _bar(5.0, 5.0, 1.0, 2.0)) is None


# ------------------------------------------------------------------ target (B-4)


def test_target_fills_at_the_level_intraday() -> None:
    fill = step(_position(TargetExit(15)), _bar(10.5, 11.6, 10.4, 11.0))
    assert fill is not None
    assert fill.price == pytest.approx(11.5)
    assert (fill.reason, fill.at) == ("target", "intraday_target")


def test_a_gap_above_the_target_fills_at_the_open() -> None:
    fill = step(_position(TargetExit(15)), _bar(12.0, 12.5, 11.9, 12.2))
    assert fill is not None
    assert (fill.price, fill.reason, fill.at) == (12.0, "target", "open")


def test_target_waits_below_the_level() -> None:
    assert step(_position(TargetExit(15)), _bar(10.5, 11.49, 10.4, 11.0)) is None


def test_the_stop_beats_the_target_on_the_same_bar() -> None:
    fill = step(_position(StopPctExit(8), TargetExit(15)), _bar(10.0, 12.0, 9.0, 11.0))
    assert fill is not None
    assert fill.price == pytest.approx(9.2)
    assert fill.reason == "stop_pct"


# ------------------------------------------------------------------ trail_pct (B-5)


def test_trail_rises_with_the_highs_and_exits_at_10_8() -> None:
    position = _position(TrailPctExit(10))
    assert position.initial_stop == pytest.approx(9.0)
    assert step(position, _bar(10.0, 10.0, 9.5, 9.8, b=1)) is None  # level 9.0
    assert step(position, _bar(10.0, 12.0, 9.1, 11.5, b=2)) is None  # level 9.0, high 12
    fill = step(position, _bar(11.2, 11.3, 10.7, 10.9, b=3))  # level 10.8
    assert fill is not None
    assert fill.price == pytest.approx(10.8)
    assert (fill.reason, fill.at) == ("trail_pct", "intraday_stop")


def test_trail_level_never_falls() -> None:
    trail = TrailPctExit(10)
    position = _position(trail)
    step(position, _bar(10.0, 12.0, 9.5, 11.0, b=1))
    step(position, _bar(11.0, 11.5, 10.9, 11.0, b=2))  # a lower high
    assert trail.level(position, _bar(11, 11, 11, 11, b=3)) == pytest.approx(10.8)


# ------------------------------------------------------------------ close_below_ma (B-6)


def test_a_close_below_the_ma_exits_at_the_next_open() -> None:
    position = _position(CloseBelowMaExit(np.array([10.0, 10.0])))
    assert step(position, _bar(10.2, 10.3, 9.8, 9.9, row=0)) is None
    assert position.pending_ma
    fill = step(position, _bar(9.5, 9.7, 9.3, 9.6, b=3, row=1))
    assert fill is not None
    assert (fill.price, fill.reason, fill.at) == (9.5, "ma", "open")


@pytest.mark.parametrize("ma", [10.0, NAN])
def test_a_close_at_the_ma_or_in_warm_up_holds(ma: float) -> None:
    position = _position(CloseBelowMaExit(np.array([ma])))
    assert step(position, _bar(10.2, 10.3, 9.8, 10.0)) is None
    assert not position.pending_ma


def test_the_entry_bar_can_schedule_the_ma_exit() -> None:
    position = _position(CloseBelowMaExit(np.array([10.0])))
    assert step(position, _bar(10.0, 10.1, 9.6, 9.7, b=1)) is None
    assert position.pending_ma


def test_the_pending_ma_exit_beats_a_gap_through_the_stop() -> None:
    position = _position(StopPctExit(8), CloseBelowMaExit(np.array([10.0, 10.0])))
    step(position, _bar(10.0, 10.1, 9.6, 9.7, row=0))
    fill = step(position, _bar(8.0, 8.1, 7.5, 7.9, b=3, row=1))
    assert fill is not None
    assert (fill.price, fill.reason) == (8.0, "ma")


def test_close_below_ma_needs_the_market_row() -> None:
    bar = BarView(10, 10, 9, 9, 2, is_delisting=False, is_final=False)
    with pytest.raises(ValueError, match="row"):
        step(_position(CloseBelowMaExit(np.array([10.0]))), bar)


# ------------------------------------------------------------------ stop precedence


@pytest.mark.parametrize(
    ("exits", "reason"),
    [
        ([TrailPctExit(10), StopPctExit(10)], "stop_pct"),
        ([ATR_AT_9, StopPctExit(10)], "stop_pct"),
        ([TrailPctExit(10), ATR_AT_9], "stop_atr"),
        ([TrailPctExit(10), ATR_AT_9, StopPctExit(10)], "stop_pct"),
    ],
)
def test_equal_stop_levels_go_stop_pct_then_stop_atr_then_trail(
    exits: list[Exit], reason: str
) -> None:
    position = _position(*exits)
    assert set(position.stop_levels.values()) == {9.0}  # an exact tie
    fill = step(position, _bar(9.5, 9.6, 8.8, 9.1))
    assert fill is not None
    assert fill.price == pytest.approx(9.0)
    assert fill.reason == reason


def test_the_highest_stop_wins() -> None:
    position = _position(StopPctExit(8), TrailPctExit(10))
    step(position, _bar(10.0, 12.0, 11.0, 11.5, b=1))  # trail 10.8 is now above 9.2
    fill = step(position, _bar(11.0, 11.2, 10.5, 10.6))
    assert fill is not None
    assert fill.price == pytest.approx(10.8)
    assert fill.reason == "trail_pct"


# ------------------------------------------------------------------ build_exits


def test_build_exits_maps_every_type_in_config_order() -> None:
    asked: list[IndicatorKey] = []

    def column(key: IndicatorKey) -> pl.Series:
        asked.append(key)
        return pl.Series([1.0, None])

    config = ExitConfig.model_validate(
        {
            "name": "all",
            "exits": [
                {"type": "close_below_ma", "ma": "ema", "n": 21},
                {"type": "stop_pct", "pct": 8},
                {"type": "stop_atr", "k": 2, "n": 14},
                {"type": "target", "pct": 15},
                {"type": "trail_pct", "pct": 10},
                {"type": "time", "bars": 5},
            ],
        }
    )
    exits = build_exits(config, column)
    kinds = [type(e) for e in exits]
    assert kinds == [
        CloseBelowMaExit,
        StopPctExit,
        StopAtrExit,
        TargetExit,
        TrailPctExit,
        TimeExitRule,
    ]
    assert asked == [IndicatorKey("ema", 21), IndicatorKey("atr", 14)]
    atr = exits[2]
    assert isinstance(atr, StopAtrExit)
    assert atr.atr[0] == 1.0
    assert math.isnan(atr.atr[1])
