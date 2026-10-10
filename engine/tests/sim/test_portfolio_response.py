"""The response `backtest()` assembles: assumptions, metric nulls, thinning, ranking and
`trial` (spec 0007, AC-6, AC-9, AC-10).

The formulas themselves are unit tested in `engine/tests/metrics/`; these walk the whole use
case, so a metric that is undefined in a real run really comes out `null`.
"""

from __future__ import annotations

from typing import Any

import pytest

from engine.contracts import Rule, pair_key, structure_key
from engine.data.fixtures import FrameSpec, bar_date, make_market

from .test_portfolio import CLOSE_ABOVE_5, SLIP, _edge_on, _run

NEVER_TRUE = {
    "left": {"kind": "ind", "ind": "close"},
    "op": ">",
    "right": {"kind": "value", "value": 1000},
}
VOLUME_SPIKE = {
    "left": {"kind": "ind", "ind": "volume"},
    "op": ">",
    "right": {"kind": "value", "value": 1_500_000},
}
TIME_50 = [{"type": "time", "bars": 50}]


def test_assumptions_echo_every_portfolio_setting() -> None:  # AC-10, U-3
    market = make_market({"AAA": _edge_on(3, 20)})
    exits: list[dict[str, Any]] = [{"type": "stop_pct", "pct": 8}, {"type": "time", "bars": 5}]
    result = _run(market, exits, max_positions=3, slippage_bps=25)
    assert result.assumptions.model_dump(mode="json") == {
        "fill_model": "signal_close_entry_next_open",
        "slippage_bps": 25.0,
        "commission_bps": 0.0,
        "sizing": "equal_weight",
        "max_positions": 3,
        "entry_rising_edge": True,
        "cooldown_bars": 10,
        "cooldown_basis": "signal",
        "no_last_bar_entry": True,
        "same_ticker_overlap": False,
        "horizon_bars": None,  # portfolio mode has no horizon and no randomness
        "seed": None,
        "configs": [{"name": "c", "exits": exits}],
        "baseline_config_index": 0,
        "delisting_rule": "exit_last_close",
        "oos_start": bar_date(15).isoformat(),
        "oos_fraction": 0.3,
        "data_mode": "synthetic",
        "data_version": "fixture:built",
        "data_seed": None,  # a fixture market has no seed
    }
    assert result.oos_start == result.assumptions.oos_start


def test_a_run_with_no_trades_leaves_every_undefined_number_null() -> None:  # AC-9
    result = _run(make_market({"AAA": _edge_on(3, 20)}), TIME_50, rule=NEVER_TRUE)
    assert result.trades == [] and result.trades_total == 0
    assert result.trades_truncated is False
    for metrics in (result.metrics.is_, result.metrics.oos):
        assert metrics.n_trades == 0
        assert metrics.win_rate_pct is None and metrics.expectancy_pct is None
        assert metrics.avg_win_pct is None and metrics.avg_loss_pct is None
        assert metrics.expectancy_r is None and metrics.profit_factor is None
        assert metrics.avg_bars_held is None
        # The curve never moves off 100, so there is no drawdown and no Sharpe at all.
        assert (metrics.cagr_pct, metrics.max_dd_pct, metrics.sharpe) == (0.0, 0.0, None)
        assert metrics.exposure_pct == 0.0
    assert {p.value for p in result.equity} == {100.0}
    assert [w.code for w in result.warnings] == ["no_entries"]


def test_a_one_session_segment_has_null_curve_metrics() -> None:  # AC-9
    # Two sessions: floor(0.7 × 2) = 1, so IS and OOS hold one close each and s < 2 both sides.
    market = make_market({"AAA": _edge_on(3, 12)})
    result = _run(market, TIME_50, start=bar_date(11).isoformat(), end=bar_date(12).isoformat())
    assert len(result.equity) == 2
    for metrics in (result.metrics.is_, result.metrics.oos):
        assert (metrics.cagr_pct, metrics.max_dd_pct, metrics.sharpe) == (None, None, None)
        assert metrics.exposure_pct is not None  # one session is still a session
    for bench in (result.benchmark_metrics.is_, result.benchmark_metrics.oos):
        assert (bench.cagr_pct, bench.max_dd_pct) == (None, None)


def test_a_null_rs126_ranks_after_every_non_null_one() -> None:  # AC-6, decision 5
    # AAA rises faster and wins the ticker tie break, but it listed too late for rs(126), so
    # the young ticker goes behind ZZZ, which has a rank. One slot, both spike on bar 200.
    signal, n_bars, young_from = 200, 230, 120
    volume = [1e6] * n_bars
    volume[signal - 1] = 2e6
    ranked = FrameSpec(1, [10.0 + 0.05 * t for t in range(n_bars)], volume=volume)
    young = FrameSpec(
        young_from,
        [10.0 + 0.5 * t for t in range(n_bars - young_from + 1)],
        volume=volume[young_from - 1 :],
    )
    result = _run(
        make_market({"ZZZ": ranked, "AAA": young}), TIME_50, rule=VOLUME_SPIKE, max_positions=1
    )
    assert [(t.ticker, t.entry_date) for t in result.trades] == [("ZZZ", bar_date(signal + 1))]


def test_an_entry_after_a_loss_is_sized_from_the_lower_equity() -> None:  # AC-6
    # Two slots. AAA takes 50 at bar 4 and halves by bar 6, where `time` closes it: equity is
    # then 75, so BBB's entry on bar 9 is 75 / 2, not 50.
    aaa = FrameSpec(1, [4.0, 4.0, 6.0, 6.0, 4.0, 3.0] + [3.0] * 6)
    bbb = FrameSpec(1, [4.0] * 7 + [6.0] * 5)
    result = _run(make_market({"AAA": aaa, "BBB": bbb}), [{"type": "time", "bars": 3}],
                  max_positions=2)  # fmt: skip
    aaa_trade, bbb_trade = result.trades
    assert (aaa_trade.exit_date, aaa_trade.exit_reason) == (bar_date(6), "time")
    assert bbb_trade.entry_date == bar_date(9)
    equity_before = {p.date: p.value for p in result.equity}[bar_date(8)]
    shares = equity_before / 2 / (6 * (1 + SLIP))
    assert {p.date: p.value for p in result.equity}[bar_date(9)] == pytest.approx(
        equity_before - equity_before / 2 + shares * 6
    )


def test_the_curve_is_thinned_once_the_window_passes_500_sessions() -> None:  # AC-9, decision 9
    market = make_market({"AAA": _edge_on(3, 501)})
    exact = _run(market, TIME_50, end=bar_date(500).isoformat())
    assert len(exact.equity) == 500  # 500 sessions fit, so every one is a point
    assert [p.date for p in exact.equity] == [p.date for p in exact.benchmark]

    thinned = _run(market, TIME_50)
    assert len(thinned.equity) == len(thinned.benchmark) == 251  # k = ceil(501 / 500) = 2
    assert [p.date for p in thinned.equity] == [p.date for p in thinned.benchmark]
    assert thinned.equity[0].date == bar_date(1) and thinned.equity[0].value == 100.0
    assert thinned.equity[-1].date == bar_date(501)
    assert [p.date for p in thinned.equity[:3]] == [bar_date(1), bar_date(3), bar_date(5)]


def _rule_of(condition: dict[str, Any]) -> Rule:
    """The `Rule` `_run` sends for one condition."""
    return Rule.model_validate({"name": "t", "conditions": [condition]})


def test_trial_carries_the_rule_structure_and_the_rule_config_pair() -> None:  # AC-9
    market = make_market({"AAA": _edge_on(3, 20)})
    exits: list[dict[str, Any]] = [{"type": "stop_pct", "pct": 8}]
    result = _run(market, exits, rule=CLOSE_ABOVE_5)
    config = result.assumptions.configs[0]
    assert result.trial.structure_key == structure_key(_rule_of(CLOSE_ABOVE_5))
    assert result.trial.pair_keys == [pair_key(_rule_of(CLOSE_ABOVE_5), config)]

    # A different threshold keeps the structure but is a new rule and config pair.
    other = {**CLOSE_ABOVE_5, "right": {"kind": "value", "value": 7}}
    moved = _run(market, exits, rule=other)
    assert moved.trial.structure_key == result.trial.structure_key
    assert moved.trial.pair_keys != result.trial.pair_keys
