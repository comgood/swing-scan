"""The portfolio day loop and the trade walker through `engine.api.backtest` (spec 0007)."""

from __future__ import annotations

from typing import Any

import pytest

from engine import api
from engine.contracts import BacktestRequest, Market, PortfolioResult
from engine.data.fixtures import FrameSpec, bar_date, make_market
from engine.exits import EntryContext, StopPctExit, TimeExitRule
from engine.indicators import cache_for
from engine.sim import BarArrays, walk_trade

SLIP = 0.001


def _run(market: Market, exits: list[dict[str, Any]], **sim: Any) -> PortfolioResult:
    request = BacktestRequest.model_validate(
        {
            "rule": {
                "name": "t",
                "conditions": [
                    {
                        "left": {"kind": "ind", "ind": "close"},
                        "op": ">",
                        "right": {"kind": "value", "value": 5},
                    }
                ],
            },
            "configs": [{"name": "c", "exits": exits}],
            "sim": sim,
        }
    )
    result = api.backtest(request, market)
    assert isinstance(result, PortfolioResult)
    return result


def _edge_on(bar: int, n: int = 12) -> FrameSpec:
    """Below 5 until `bar`, then above: one rising edge on `bar`."""
    return FrameSpec(1, [4.0] * (bar - 1) + [6.0] * (n - bar + 1))


def test_an_open_position_on_the_last_session_exits_end_of_test() -> None:
    result = _run(make_market({"AAA": _edge_on(3, 6)}), [{"type": "time", "bars": 50}])
    (trade,) = result.trades
    assert (trade.entry_date, trade.exit_date) == (bar_date(4), bar_date(6))
    assert trade.exit_reason == "end_of_test"
    assert trade.exit_price == pytest.approx(6.0 * (1 - SLIP))
    assert trade.bars_held == 3


def test_slots_limit_entries_and_rank_then_ticker_breaks_ties() -> None:
    # Five equal signals (same rs) on bar 3, two slots: A and B enter, the rest are dropped.
    market = make_market({t: _edge_on(3) for t in ("EEE", "DDD", "CCC", "BBB", "AAA")})
    result = _run(market, [{"type": "time", "bars": 2}], max_positions=2)
    assert [t.ticker for t in result.trades] == ["AAA", "BBB"]


def test_each_entry_gets_equity_over_max_positions() -> None:
    market = make_market({"AAA": _edge_on(3), "BBB": FrameSpec(1, [4.0] * 12)})
    result = _run(market, [{"type": "time", "bars": 2}], max_positions=4)
    # Close of entry bar 4: 75 cash plus 25 / (6 × 1.001) shares at 6.
    expected = 75 + 25 / (6 * (1 + SLIP)) * 6
    by_date = {p.date: p.value for p in result.equity}
    assert by_date[bar_date(4)] == pytest.approx(expected)
    assert by_date[bar_date(1)] == 100.0


def test_a_slot_freed_today_is_not_reused_today() -> None:
    # One slot. AAA enters on bar 4 and gaps through its stop at open(6). BBB signals on
    # bar 5, but the slot was taken at close(5), so BBB is dropped, not entered at open(6).
    aaa = FrameSpec(1, [4.0, 4.0, 6.0, 6.0, 6.0] + [3.0] * 5)
    bbb = FrameSpec(1, [4.0] * 4 + [6.0] * 6)
    result = _run(make_market({"AAA": aaa, "BBB": bbb}), [{"type": "stop_pct", "pct": 8}],
                  max_positions=1)  # fmt: skip
    assert [(t.ticker, t.exit_date, t.exit_reason) for t in result.trades] == [
        ("AAA", bar_date(6), "stop_pct")
    ]


def test_a_held_tickers_signal_is_skipped() -> None:
    closes = [4.0, 4.0, 6.0, 4.0, 4.0, 6.0, 6.0] + [6.0] * 10 + [4.0, 6.0, 6.0]
    market = make_market({"AAA": FrameSpec(1, closes)})
    result = _run(market, [{"type": "time", "bars": 30}])
    # Edges on bars 3 and 6 (6 is in the cooldown anyway) and 19; the first trade is still
    # held on bar 19, so only one trade, closed at the end.
    assert [(t.entry_date, t.exit_reason) for t in result.trades] == [(bar_date(4), "end_of_test")]


def test_the_response_is_a_valid_minimal_portfolio_result() -> None:
    result = _run(make_market({"AAA": _edge_on(3, 20)}), [{"type": "stop_pct", "pct": 8}])
    assert result.mode == "portfolio"
    assert result.oos_start == bar_date(15)  # floor(0.7 × 20) = index 14
    assert result.metrics.is_.n_trades == 1
    assert result.trades_total == 1
    assert len(result.equity) == len(result.benchmark) == 20
    assert result.benchmark[0].value == 100.0
    assert result.assumptions.configs[0].name == "c"
    assert result.assumptions.data_version == "fixture:built"


def test_walk_trade_runs_the_same_step() -> None:
    market = make_market({"AAA": FrameSpec(1, [10.0, 10.0, 9.0, 9.0])})
    cache = cache_for(market)
    bars = BarArrays.build(market, cache)
    outcome = walk_trade(1, 10.0, [StopPctExit(5), TimeExitRule(10)], bars, EntryContext(0))
    assert (outcome.exit_row, outcome.fill.reason, outcome.fill.price) == (2, "stop_pct", 9.0)
    assert outcome.position.bars_held == 2
