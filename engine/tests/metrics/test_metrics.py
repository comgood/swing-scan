"""Each metric formula and its null case, and thinning (spec 0007, AC-9)."""

from __future__ import annotations

import math
from datetime import date
from statistics import stdev

import pytest

from engine.contracts import Trade
from engine.metrics import curve_stats, exposure_pct, thin, trade_stats


def _trade(return_pct: float, bars: int = 3, r: float | None = 1.0) -> Trade:
    return Trade(
        ticker="AAA",
        entry_date=date(2020, 1, 2),
        entry_price=10.0,
        exit_date=date(2020, 1, 6),
        exit_price=10.0 * (1 + return_pct / 100),
        return_pct=return_pct,
        bars_held=bars,
        exit_reason="time",
        r_multiple=r,
        mae_pct=0.0,
        mfe_pct=0.0,
        mae_r=None,
        mfe_r=None,
        segment="is",
    )


def test_trade_stats_follow_the_formulas() -> None:
    stats = trade_stats(
        [_trade(10, 2, 1.5), _trade(-5, 4, -1.0), _trade(0, 6, 0.0), _trade(20, 8, 2.5)]
    )
    assert stats.n_trades == 4
    assert stats.win_rate_pct == 50.0  # 0 counts as a loss
    assert stats.avg_win_pct == pytest.approx(15.0)
    assert stats.avg_loss_pct == pytest.approx(-2.5)
    assert stats.expectancy_pct == pytest.approx(25 / 4)
    assert stats.expectancy_r == pytest.approx(3.0 / 4)
    assert stats.profit_factor == pytest.approx(30 / 5)
    assert stats.avg_bars_held == pytest.approx(5.0)


def test_no_trades_makes_every_trade_metric_null() -> None:
    stats = trade_stats([])
    assert stats.n_trades == 0
    assert stats.win_rate_pct is None and stats.expectancy_pct is None
    assert stats.avg_win_pct is None and stats.avg_loss_pct is None
    assert stats.expectancy_r is None and stats.profit_factor is None
    assert stats.avg_bars_held is None


def test_only_wins_has_no_loss_average_and_no_profit_factor() -> None:
    stats = trade_stats([_trade(4), _trade(6)])
    assert stats.avg_loss_pct is None
    assert stats.profit_factor is None  # abs(sum of losses) = 0
    assert stats.win_rate_pct == 100.0


def test_only_losses_has_no_win_average_and_a_zero_profit_factor() -> None:
    stats = trade_stats([_trade(-4), _trade(-6)])
    assert stats.avg_win_pct is None
    assert stats.profit_factor == 0.0
    assert stats.win_rate_pct == 0.0


def test_expectancy_r_is_null_without_a_stop() -> None:
    assert trade_stats([_trade(4, r=None), _trade(-2, r=None)]).expectancy_r is None


def test_expectancy_r_leaves_out_only_the_trades_without_r() -> None:  # ruling 2026-10-09
    # A stop config where one trade has no R (a `stop_atr` entry during ATR warm up).
    stats = trade_stats([_trade(10, r=2.0), _trade(-4, r=None), _trade(-2, r=-1.0)])
    assert stats.expectancy_r == pytest.approx((2.0 - 1.0) / 2)
    assert stats.n_trades == 3
    assert stats.expectancy_pct == pytest.approx(4 / 3)  # every other metric counts it


def test_curve_stats_follow_the_formulas() -> None:
    closes = [110.0, 99.0, 121.0]
    stats = curve_stats(closes, start=100.0, peak=100.0)
    assert stats.cagr_pct == pytest.approx(((121 / 100) ** (252 / 3) - 1) * 100)
    assert stats.max_dd_pct == pytest.approx((99 / 110 - 1) * 100)
    returns = [0.1, 99 / 110 - 1, 121 / 99 - 1]  # the first one against the start
    expected = sum(returns) / 3 / stdev(returns) * math.sqrt(252)
    assert stats.sharpe == pytest.approx(expected)


def test_the_drawdown_peak_carries_in_from_before_the_segment() -> None:
    # OOS starts at 90 after an IS peak of 120: the OOS drawdown is measured from 120.
    stats = curve_stats([95.0, 100.0], start=90.0, peak=120.0)
    assert stats.max_dd_pct == pytest.approx((95 / 120 - 1) * 100)
    assert stats.cagr_pct == pytest.approx(((100 / 90) ** (252 / 2) - 1) * 100)


def test_a_flat_curve_has_no_drawdown_and_no_sharpe() -> None:
    stats = curve_stats([100.0, 100.0, 100.0], start=100.0, peak=100.0)
    assert stats.cagr_pct == 0.0
    assert stats.max_dd_pct == 0.0
    assert stats.sharpe is None  # std = 0


def test_fewer_than_two_sessions_makes_every_curve_metric_null() -> None:
    for closes in ([], [105.0]):
        stats = curve_stats(closes, start=100.0, peak=100.0)
        assert (stats.cagr_pct, stats.max_dd_pct, stats.sharpe) == (None, None, None)


def test_exposure_is_the_mean_invested_share_and_null_without_sessions() -> None:
    assert exposure_pct([0.0, 0.5, 1.0]) == pytest.approx(50.0)
    assert exposure_pct([]) is None


@pytest.mark.parametrize("n", [1, 2, 499, 500, 501, 999, 1000, 1001, 1260, 5000])
def test_thinning_keeps_the_first_and_last_point_and_at_most_500(n: int) -> None:
    picked = thin(n)
    assert picked[0] == 0 and picked[-1] == n - 1
    assert len(picked) <= 500
    assert picked == sorted(set(picked))
    if n <= 500:
        assert picked == list(range(n))


def test_thinning_takes_every_kth_session() -> None:
    assert thin(1260)[:4] == [0, 3, 6, 9]  # k = ceil(1260 / 500) = 3
    assert thin(0) == []
