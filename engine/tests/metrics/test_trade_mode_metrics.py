"""The exit lab's per trade metrics, `best_is`, `guides_is`, the horizon warning rule and the
even spread of the baseline trade list (spec 0002 metric definitions, spec 0009)."""

from __future__ import annotations

from datetime import date

import pytest

from engine.contracts import Trade, TradeMetrics
from engine.contracts.backtest import ExitReason, Segment
from engine.metrics import (
    best_is,
    edge,
    even_spread,
    guides_is,
    over_horizon_limit,
    trade_metrics,
)


def _trade(
    return_pct: float,
    bars: int = 3,
    *,
    r: float | None = None,
    mae: float = 0.0,
    mfe: float = 0.0,
    reason: ExitReason = "time",
    entry: date = date(2020, 1, 6),
    segment: Segment = "is",
) -> Trade:
    return Trade(
        ticker="AAA",
        entry_date=entry,
        entry_price=10.0,
        exit_date=entry,
        exit_price=10.0 * (1 + return_pct / 100),
        return_pct=return_pct,
        bars_held=bars,
        exit_reason=reason,
        r_multiple=r,
        mae_pct=mae,
        mfe_pct=mfe,
        mae_r=None,
        mfe_r=None,
        segment=segment,
    )


SIX = [
    _trade(10, 2, r=2.0, mae=-1, mfe=12, entry=date(2020, 1, 6)),  # ISO week 2
    _trade(-5, 4, r=-1.0, mae=-6, mfe=1, entry=date(2020, 1, 8)),  # week 2
    _trade(0, 6, r=0.0, mae=-2, mfe=3, reason="horizon", entry=date(2020, 1, 13)),  # week 3
    _trade(20, 8, r=4.0, mae=-3, mfe=25, entry=date(2020, 1, 20)),  # week 4
    _trade(-2, 1, r=-0.4, mae=-2, mfe=0, entry=date(2020, 12, 28)),  # 2020 week 53
    _trade(7, 3, r=1.4, mae=0, mfe=8, entry=date(2021, 1, 4)),  # 2021 week 1
]


def test_six_trade_fixture_matches_hand_values() -> None:  # AC-4
    m = trade_metrics(SIX)
    assert (m.n_trades, m.distinct_weeks) == (6, 5)
    assert m.win_rate_pct == pytest.approx(50.0)
    assert m.avg_win_pct == pytest.approx((10 + 20 + 7) / 3)
    assert m.avg_loss_pct == pytest.approx((-5 + 0 - 2) / 3)  # 0% counts as a loss
    assert m.expectancy_pct == pytest.approx(30 / 6)
    assert m.expectancy_r == pytest.approx((2 - 1 + 0 + 4 - 0.4 + 1.4) / 6)
    assert m.expectancy_per_bar_pct == pytest.approx(30 / 24)
    assert m.profit_factor == pytest.approx(37 / 7)
    assert m.avg_bars_held == pytest.approx(24 / 6)
    assert m.avg_mae_pct == pytest.approx(-14 / 6)
    assert m.avg_mfe_pct == pytest.approx(49 / 6)
    assert m.horizon_exit_pct == pytest.approx(100 / 6)
    assert not {"cagr_pct", "max_dd_pct", "sharpe"} & set(TradeMetrics.model_fields)


def test_an_empty_segment_is_null_except_the_counts() -> None:
    m = trade_metrics([])
    assert (m.n_trades, m.distinct_weeks) == (0, 0)
    others = m.model_dump(exclude={"n_trades", "distinct_weeks"})
    assert set(others.values()) == {None}


def test_no_stop_means_null_expectancy_r_and_null_r_edge() -> None:  # AC-5
    stopless = trade_metrics([_trade(5), _trade(-1)])
    assert stopless.expectancy_r is None
    stopped = trade_metrics([_trade(5, r=1.0)])
    assert edge(stopless, stopped).expectancy_r is None
    assert edge(stopped, stopped).expectancy_r == 0.0


def test_edge_is_strategy_minus_random_and_null_when_either_is_null() -> None:
    strategy, random = trade_metrics(SIX), trade_metrics([_trade(1, 1, r=0.5)])
    got = edge(strategy, random)
    assert got.expectancy_pct == pytest.approx(5 - 1)
    assert got.win_rate_pct == pytest.approx(50 - 100)
    assert got.expectancy_per_bar_pct == pytest.approx(1.25 - 1)
    assert edge(strategy, trade_metrics([])).model_dump() == dict.fromkeys(got.model_dump())


def _metrics(**values: float | None) -> TradeMetrics:
    base = trade_metrics([]).model_dump()
    return TradeMetrics.model_validate({**base, "n_trades": 1, **values})


def test_best_is_follows_directions_ties_and_nulls() -> None:  # AC-6
    rows = [
        _metrics(expectancy_pct=1.0, avg_loss_pct=-4.0, avg_mae_pct=-3.0, horizon_exit_pct=20.0),
        _metrics(expectancy_pct=2.0, avg_loss_pct=-1.0, avg_mae_pct=-5.0, horizon_exit_pct=5.0),
        _metrics(expectancy_pct=2.0, avg_loss_pct=None, avg_mae_pct=-1.0, horizon_exit_pct=5.0),
    ]
    best = best_is(rows)
    assert best.expectancy_pct == 1  # tie between 1 and 2 goes to the lower index
    assert best.avg_loss_pct == 1  # closer to 0 is better, null skipped
    assert best.avg_mae_pct == 2  # closer to 0 is better
    assert best.horizon_exit_pct == 1  # lower is better, tie to the lower index
    assert best.profit_factor is None  # no config has a value


def test_only_is_values_are_ranked() -> None:  # AC-6
    # The API passes `rows[i].strategy.is_` only, so an OOS value never reaches `best_is`.
    is_rows = [_metrics(expectancy_pct=3.0), _metrics(expectancy_pct=1.0)]
    assert best_is(is_rows).expectancy_pct == 0


def test_guides_use_is_trades_only_and_reject_oos() -> None:  # AC-7
    is_trades = [
        _trade(5, mae=-1, mfe=6),
        _trade(4, mae=-2, mfe=5),
        _trade(3, mae=-3, mfe=4),
        _trade(-2, mae=-9, mfe=1),
        _trade(2, mae=-4, mfe=3),
    ]
    oos_winners = [_trade(9, mae=-20, mfe=30, segment="oos") for _ in range(4)]
    got = guides_is(is_trades)
    # Winner depths (-mae) [1, 2, 3, 4]: linear p75 at position 2.25 = 3.25, p90 at 2.7 = 3.7,
    # reported back signed (owner ruling 2026-10-09).
    assert got.winner_mae_p75_pct == pytest.approx(-3.25)
    assert got.winner_mae_p90_pct == pytest.approx(-3.7)
    assert got.mfe_median_pct == pytest.approx(4.0)
    with pytest.raises(ValueError, match="IS trades only"):
        guides_is(is_trades + oos_winners)
    assert guides_is([_trade(-1)]).winner_mae_p75_pct is None
    assert guides_is([]).mfe_median_pct is None


def _horizon_mix(n: int, horizon: int, segment: Segment) -> list[Trade]:
    return [
        _trade(1, reason="horizon" if i < horizon else "time", segment=segment) for i in range(n)
    ]


def test_horizon_warning_uses_is_and_oos_together() -> None:  # AC-9
    # 5% of 100 IS plus 30% of 20 OOS: 11 of 120 is 9.2%, no warning.
    assert not over_horizon_limit(_horizon_mix(100, 5, "is") + _horizon_mix(20, 6, "oos"))
    # 5% of 60 IS plus 30% of 40 OOS: 15 of 100 is 15%, a warning.
    assert over_horizon_limit(_horizon_mix(60, 3, "is") + _horizon_mix(40, 12, "oos"))
    assert not over_horizon_limit(_horizon_mix(100, 8, "is"))  # 8%
    assert not over_horizon_limit(_horizon_mix(10, 1, "is"))  # exactly 10% is not over
    assert not over_horizon_limit([])


def test_even_spread_keeps_both_ends_and_rounds_halves_up() -> None:
    assert even_spread(list(range(5)), 10) == [0, 1, 2, 3, 4]
    assert even_spread(list(range(5)), 3) == [0, 2, 4]
    assert even_spread(list(range(4)), 3) == [0, 2, 3]  # 1.5 rounds up to 2
    picked = even_spread(list(range(5000)), 2000)
    assert (len(picked), picked[0], picked[-1]) == (2000, 0, 4999)
    assert picked == [round(i * 4999 / 1999 + 1e-9) for i in range(2000)]


def test_the_p90_mae_guide_is_deeper_than_p75() -> None:  # owner ruling 2026-10-09
    # A stop guide: 90% of winners never dipped deeper than p90, so p90 <= p75 <= 0.
    winners = [_trade(1 + i, mae=-0.5 * i, mfe=2 + i) for i in range(20)]
    got = guides_is(winners)
    assert got.winner_mae_p75_pct is not None and got.winner_mae_p90_pct is not None
    assert got.winner_mae_p90_pct <= got.winner_mae_p75_pct <= 0
    assert got.winner_mae_p90_pct < got.winner_mae_p75_pct
