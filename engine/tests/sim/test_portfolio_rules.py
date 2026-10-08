"""Portfolio rules and the response: slots, sizing, cash cap, window, metrics, warnings
(spec 0007, BE milestone 2)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from pydantic import ValidationError

from engine import api
from engine.data.fixtures import FrameSpec, bar_date, make_market

from .test_portfolio import CLOSE_ABOVE_5, SLIP, _edge_on, _run

TIME_50 = [{"type": "time", "bars": 50}]


def test_b11_fifteen_signals_fill_the_top_ten_by_rs_at_equity_over_ten() -> None:
    # Fifteen tickers whose slope (and so ret(126), rs(126)) rises with their index, while
    # their names run the other way, so rank and ticker order disagree. One rising edge each
    # on bar 200 (volume spike), entry at open(201).
    signal, n_bars = 200, 230
    tickers: dict[str, FrameSpec] = {}
    for i in range(15):
        closes = [10.0 + 0.01 * (i + 1) * t for t in range(1, signal + 1)]
        closes += [closes[-1]] * (n_bars - signal)
        volume = [1e6] * n_bars
        volume[signal - 1] = 2e6
        tickers[f"{chr(ord('O') - i)}X"] = FrameSpec(1, closes, volume=volume)
    rule = {
        "left": {"kind": "ind", "ind": "volume"},
        "op": ">",
        "right": {"kind": "value", "value": 1_500_000},
    }
    result = _run(make_market(tickers), TIME_50, max_positions=10, rule=rule)

    expected = sorted(f"{chr(ord('O') - i)}X" for i in range(5, 15))
    assert sorted(t.ticker for t in result.trades) == expected
    assert {t.entry_date for t in result.trades} == {bar_date(signal + 1)}
    # Ten slots of 100 / 10, each bought at close × 1.001 and marked at the same close.
    point = next(p for p in result.equity if p.date == bar_date(signal + 1))
    assert point.value == pytest.approx(10 * 10 / (1 + SLIP), abs=1e-9)


def test_the_cash_cap_sizes_an_entry_below_equity_over_slots() -> None:
    # Two slots. AAA takes 50 at 6.006 and triples; equity ~200 so 1/2 would be ~100, but
    # only 50 cash is left, so BBB gets 50.
    aaa = FrameSpec(1, [4.0, 4.0, 6.0, 6.0] + [18.0] * 6)
    bbb = FrameSpec(1, [4.0] * 5 + [6.0] * 5)
    result = _run(make_market({"AAA": aaa, "BBB": bbb}), TIME_50, max_positions=2)
    assert [t.ticker for t in result.trades] == ["AAA", "BBB"]
    shares = 50 / (6 * (1 + SLIP))
    by_date = {p.date: p.value for p in result.equity}
    assert by_date[bar_date(7)] == pytest.approx(shares * 18 + shares * 6)


def test_signals_before_start_are_ignored_and_the_curve_starts_at_start() -> None:
    result = _run(make_market({"AAA": _edge_on(3, 12)}), TIME_50, start=bar_date(5).isoformat())
    assert result.trades == []
    assert result.equity[0].date == bar_date(5) and result.equity[0].value == 100.0
    assert result.benchmark[0].value == 100.0
    assert len(result.equity) == 8
    assert result.oos_start == bar_date(5 + math.floor(0.7 * 8))
    assert [(w.code, w.config_index) for w in result.warnings] == [("no_entries", 0)]


def test_an_open_position_at_end_exits_end_of_test_not_delisted() -> None:
    market = make_market({"AAA": _edge_on(3, 12)})
    result = _run(market, TIME_50, end=bar_date(8).isoformat())
    (trade,) = result.trades
    assert (trade.exit_date, trade.exit_reason) == (bar_date(8), "end_of_test")
    assert result.equity[-1].date == bar_date(8)
    assert result.warnings == []


@pytest.mark.parametrize(
    ("field", "value"), [("start", "2019-12-31"), ("end", "2020-02-03"), ("start", "2020-01-20")]
)
def test_a_window_edge_outside_the_data_is_range_outside_data(field: str, value: str) -> None:
    market = make_market({"AAA": _edge_on(3, 12)})  # bars 1 to 12: 2020-01-02 to 2020-01-17
    with pytest.raises(ValidationError) as caught:
        _run(market, TIME_50, CLOSE_ABOVE_5, **{field: value})
    (error,) = caught.value.errors()
    assert error["type"] == "range_outside_data"
    assert error["loc"] == ("sim", field)
    assert error["ctx"] == {"min": "2020-01-02", "max": "2020-01-17"}


def _walk(seed: int, n_tickers: int, n_bars: int) -> dict[str, list[float]]:
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0005, 0.02, size=(n_tickers, n_bars))
    return {f"T{i:02d}": (30 * np.exp(np.cumsum(row))).tolist() for i, row in enumerate(steps)}


def test_b10_a_poisoned_future_changes_nothing_with_stop_pct_and_time() -> None:
    # Feature 9 stand in for the B-10 portfolio oracle until feature 11's exits land.
    cut, walks = 250, _walk(5, 20, 300)
    clean = make_market({t: FrameSpec(1, c) for t, c in walks.items()})
    poisoned = {t: c[:cut] + [1.0 + (k * 37) % 97 for k in range(len(c) - cut)] for t, c in
                walks.items()}  # fmt: skip
    dirty = make_market({t: FrameSpec(1, c) for t, c in poisoned.items()})
    exits = [{"type": "stop_pct", "pct": 8}, {"type": "time", "bars": 10}]
    rule = {
        "left": {"kind": "ind", "ind": "close"},
        "op": ">",
        "right": {"kind": "ind", "ind": "sma", "n": 20},
    }
    end = bar_date(cut).isoformat()
    first = _run(clean, exits, end=end, rule=rule)
    assert first.trades_total > 0
    assert _run(dirty, exits, end=end, rule=rule).model_dump() == first.model_dump()


def test_metrics_split_is_and_oos_and_benchmark_metrics_are_filled() -> None:
    result = _run(make_market({"AAA": _edge_on(3, 20)}), [{"type": "time", "bars": 3}])
    is_, oos = result.metrics.is_, result.metrics.oos
    assert (is_.n_trades, oos.n_trades) == (1, 0)
    (trade,) = result.trades
    assert is_.expectancy_pct == pytest.approx(trade.return_pct)
    assert is_.expectancy_r is None  # no stop in the config
    assert is_.cagr_pct is not None and is_.exposure_pct is not None and is_.exposure_pct > 0
    assert oos.win_rate_pct is None and oos.exposure_pct == 0.0
    # The fixture benchmark is flat, so its curve metrics are exactly 0.
    assert result.benchmark_metrics.is_.cagr_pct == 0.0
    assert result.benchmark_metrics.oos.max_dd_pct == 0.0


def test_warnings_come_in_order_with_the_spec_messages() -> None:
    assert api._warnings(5) == []
    (no_entries,) = api._warnings(0)
    assert (no_entries.code, no_entries.config_index) == ("no_entries", 0)
    (truncated,) = api._warnings(2600)
    assert (truncated.code, truncated.config_index) == ("trades_truncated", None)
    assert truncated.message == "Showing the latest 2,000 of 2,600 trades; metrics use all of them."
