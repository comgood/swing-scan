"""Trade mode, the exit lab's loop, through `engine.api._trade_lab` (spec 0009, BE 1).

`backtest()` still answers 2 to 6 configs with 501 until the random baseline lands, so these
tests call the unserved use case directly.
"""

from __future__ import annotations

import json
import statistics
from typing import Any

import numpy as np
import pytest

from engine import api
from engine.contracts import BacktestRequest, Market, TradeLabResult, entries_hash
from engine.data.fixtures import FrameSpec, bar_date, make_market

SLIP = 0.001
CLOSE_ABOVE_5 = {
    "left": {"kind": "ind", "ind": "close"},
    "op": ">",
    "right": {"kind": "value", "value": 5},
}
TIME_30 = {"name": "time 30", "exits": [{"type": "time", "bars": 30}]}
TIME_2 = {"name": "time 2", "exits": [{"type": "time", "bars": 2}]}
STOP_8 = {"name": "stop 8", "exits": [{"type": "stop_pct", "pct": 8}]}

# Edges on bars 3 and 19 (bar 6 sits in the cooldown): entries on bars 4 and 20.
AAA = FrameSpec(1, [4.0, 4.0, 6.0, 4.0, 4.0, 6.0, 6.0] + [6.0] * 10 + [4.0, 6.0, 6.0])
# One edge on bar 3, entry on bar 4; the ticker stops at bar 10, so it is delisted there.
CCC = FrameSpec(1, [4.0, 4.0] + [6.0] * 8)


def _market() -> Market:
    return make_market({"AAA": AAA, "CCC": CCC})


def _lab(market: Market, *configs: dict[str, Any], **sim: Any) -> TradeLabResult:
    request = BacktestRequest.model_validate(
        {
            "rule": {"name": "t", "conditions": [CLOSE_ABOVE_5]},
            "configs": list(configs),
            "sim": sim,
        }
    )
    return api._trade_lab(request, market)


def test_backtest_still_answers_trade_mode_with_501() -> None:
    request = BacktestRequest.model_validate(
        {"rule": {"name": "t", "conditions": [CLOSE_ABOVE_5]}, "configs": [TIME_30, TIME_2]}
    )
    with pytest.raises(api.NotYetImplemented) as caught:
        api.backtest(request, _market())
    assert caught.value.feature == 12


def test_every_config_walks_the_same_entries_with_overlap_allowed() -> None:  # AC-1
    result = _lab(_market(), TIME_30, TIME_2, STOP_8, horizon_bars=60)

    expected = [("AAA", bar_date(4)), ("CCC", bar_date(4)), ("AAA", bar_date(20))]
    assert result.entries.count == 3
    assert (result.entries.is_count, result.entries.oos_count) == (2, 1)
    assert result.entries.hash == entries_hash(expected)
    assert result.entries.distinct_weeks == 2
    # The first AAA trade is still held on bar 20 under `time 30`, yet the second is kept.
    assert [(t.ticker, t.entry_date) for t in result.baseline_trades] == expected
    assert result.baseline_trades[0].exit_date == bar_date(20)
    for row in result.rows:
        assert row.strategy.is_.n_trades + row.strategy.oos.n_trades == 3
    opens = [4.0, 6.0, 6.0]  # open(4) of AAA is its close, 4; the others open at 6
    for trade, price in zip(result.baseline_trades, opens, strict=True):
        assert trade.entry_price == pytest.approx(price * (1 + SLIP), abs=1e-12)


def test_horizon_end_of_test_and_delisting_exits() -> None:  # AC-3
    result = _lab(_market(), TIME_30, TIME_2, horizon_bars=5)
    by_entry = {(t.ticker, t.entry_date): t for t in result.baseline_trades}

    horizon = by_entry[("AAA", bar_date(4))]
    assert (horizon.exit_date, horizon.exit_reason, horizon.bars_held) == (
        bar_date(8),
        "horizon",
        5,
    )
    assert horizon.exit_price == pytest.approx(6.0 * (1 - SLIP), abs=1e-9)
    last = by_entry[("AAA", bar_date(20))]
    assert (last.exit_reason, last.bars_held) == ("end_of_test", 1)

    delisted = _lab(_market(), TIME_30, TIME_2, horizon_bars=60).baseline_trades[1]
    assert (delisted.ticker, delisted.exit_reason, delisted.exit_date) == (
        "CCC",
        "delisted",
        bar_date(10),
    )


def test_trade_mode_has_per_trade_metrics_only() -> None:  # AC-4
    result = _lab(_market(), TIME_30, TIME_2)
    body = result.model_dump_json(by_alias=True)
    assert not {"cagr_pct", "max_dd_pct", "sharpe", "exposure_pct"} & set(_keys(body))
    time2 = result.rows[1].strategy.is_
    assert time2.n_trades == 2
    assert time2.expectancy_per_bar_pct is not None
    assert time2.horizon_exit_pct == 0.0


def test_r_metrics_are_null_without_a_stop() -> None:  # AC-5
    result = _lab(_market(), TIME_30, STOP_8)
    stopless, stopped = result.rows
    assert stopless.strategy.is_.expectancy_r is None
    assert stopless.edge.is_.expectancy_r is None
    assert stopped.strategy.is_.expectancy_r is not None
    trades = result.baseline_trades
    assert all(t.r_multiple is None and t.mae_r is None and t.mfe_r is None for t in trades)


def test_best_is_and_guides_is_come_from_is_strategy_values() -> None:  # AC-6, AC-7
    result = _lab(_market(), TIME_30, TIME_2, horizon_bars=5)
    # Both IS trades of config 0 hit the horizon, none of config 1's do.
    assert result.rows[0].strategy.is_.horizon_exit_pct == 100.0
    assert result.best_is.horizon_exit_pct == 1
    is_values = [row.strategy.is_.expectancy_pct or 0.0 for row in result.rows]
    assert result.best_is.expectancy_pct == is_values.index(max(is_values))

    is_trades = [t for t in result.baseline_trades if t.segment == "is"]
    winners = [t.mae_pct for t in is_trades if t.return_pct > 0]
    assert winners and len(is_trades) < len(result.baseline_trades)
    assert result.guides_is.winner_mae_p75_pct == pytest.approx(float(np.percentile(winners, 75)))
    assert result.guides_is.mfe_median_pct == pytest.approx(
        statistics.median(t.mfe_pct for t in is_trades)
    )


def test_horizon_warning_names_only_the_config_over_10pct() -> None:  # AC-9
    result = _lab(_market(), TIME_30, TIME_2, horizon_bars=5)
    horizon = [w for w in result.warnings if w.code == "horizon_exits_over_10pct"]
    assert [(w.config_index, w.message) for w in horizon] == [
        (0, "time 30: more than 10% of trades hit the 5 bar horizon, so its results are cut short.")
    ]


def test_assumptions_echo_trade_mode_settings() -> None:  # AC-12
    result = _lab(_market(), TIME_30, TIME_2, horizon_bars=40, seed=7, slippage_bps=5)
    a = result.assumptions
    assert (a.sizing, a.same_ticker_overlap, a.max_positions) == ("unit_notional", True, None)
    assert (a.horizon_bars, a.seed, a.slippage_bps, a.baseline_config_index) == (40, 7, 5, 0)
    assert [c.name for c in a.configs] == ["time 30", "time 2"]
    assert result.oos_start == a.oos_start == bar_date(15)  # floor(0.7 × 20) = index 14
    assert len(result.trial.pair_keys) == 2


def test_no_entries_keeps_every_row_with_empty_metrics() -> None:
    flat = make_market({"AAA": FrameSpec(1, [4.0] * 20)})
    result = _lab(flat, TIME_30, TIME_2, STOP_8)
    assert [w.code for w in result.warnings] == ["no_entries"]
    assert result.warnings[0].config_index is None
    assert len(result.rows) == 3
    for row in result.rows:
        assert (row.strategy.is_.n_trades, row.strategy.is_.distinct_weeks) == (0, 0)
        assert row.strategy.is_.expectancy_pct is None
    assert result.best_is.model_dump() == dict.fromkeys(result.best_is.model_dump())
    assert result.guides_is.model_dump() == dict.fromkeys(result.guides_is.model_dump())
    assert (result.entries.count, result.entries.random_is_count) == (0, 0)
    assert result.baseline_trades == []


def _keys(body: str) -> list[str]:
    found: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            found.extend(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(json.loads(body))
    return found
