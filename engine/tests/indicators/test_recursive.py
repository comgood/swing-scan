"""`ema`, `atr`, `rsi`, `ret` and `rs` against hand computed values (spec 0005, AC-2)."""

from __future__ import annotations

import pytest

from engine.data.fixtures import FrameSpec, make_market
from engine.indicators import IndicatorKey, cache_for


def _values(tickers: dict[str, FrameSpec], key: IndicatorKey, ticker: str) -> list[float | None]:
    cache = cache_for(make_market(tickers))
    return cache.get(key).filter(cache.bars["ticker"] == ticker).to_list()


def test_ema_is_seeded_with_the_mean_of_the_first_n_closes() -> None:
    spec = {"AAA": FrameSpec(1, [1.0, 2.0, 3.0, 4.0, 5.0])}
    # bar 3: (1 + 2 + 3) / 3 = 2, then alpha = 0.5: 0.5 × 4 + 0.5 × 2 = 3, then 4.
    assert _values(spec, IndicatorKey("ema", 3), "AAA") == [None, None, 2.0, 3.0, 4.0]


def test_atr_is_wilder_smoothed_true_range() -> None:
    spec = {"AAA": FrameSpec(1, [9.0, 10.0, 13.0], high=[10.0, 11.0, 14.0], low=[8.0, 9.0, 12.0])}
    # TR: 2 (high - low on the first bar), 2, max(2, 4, 2) = 4. ATR(2): mean 2, then (2 + 4) / 2.
    assert _values(spec, IndicatorKey("atr", 2), "AAA") == [None, 2.0, 3.0]


def test_rsi_is_wilder_smoothed_gain_over_loss() -> None:
    spec = {"AAA": FrameSpec(1, [10.0, 11.0, 10.0, 12.0])}
    # Changes +1, -1, +2. Bar 3: gain 0.5, loss 0.5 → 50. Bar 4: gain 1.25, loss 0.25 → 83.33.
    values = _values(spec, IndicatorKey("rsi", 2), "AAA")
    assert values[:3] == [None, None, 50.0]
    assert values[3] == pytest.approx(100 - 100 / 6)


def test_rsi_is_100_when_there_is_no_loss() -> None:
    spec = {"AAA": FrameSpec(1, [10.0, 11.0, 12.0, 13.0])}
    assert _values(spec, IndicatorKey("rsi", 2), "AAA") == [None, None, 100.0, 100.0]


def test_ret_is_a_fraction_first_valid_on_bar_n_plus_1() -> None:
    spec = {"AAA": FrameSpec(1, [10.0, 11.0, 12.0, 15.0])}
    values = _values(spec, IndicatorKey("ret", 2), "AAA")
    assert values[:2] == [None, None]
    assert values[2] == pytest.approx(0.2)
    assert values[3] == pytest.approx(15 / 11 - 1)


def _rs_market() -> dict[str, FrameSpec]:
    return {
        "AAA": FrameSpec(1, [10.0, 10.0, 11.0]),  # ret(2) 0.1
        "BBB": FrameSpec(1, [10.0, 10.0, 12.0]),  # 0.2
        "CCC": FrameSpec(1, [10.0, 10.0, 12.0]),  # 0.2, tied with BBB
        "DDD": FrameSpec(1, [10.0, 10.0, 9.0]),  # -0.1
        "LATE": FrameSpec(2, [10.0, 50.0]),  # no ret(2) yet
    }


@pytest.mark.parametrize(
    ("ticker", "expected"),
    [("DDD", 0.0), ("AAA", 33.0), ("BBB", 99.0), ("CCC", 99.0), ("LATE", None)],
)
def test_rs_ranks_ret_among_valid_tickers_with_ties_taking_the_highest(
    ticker: str, expected: float | None
) -> None:
    # m = 4 (LATE and the benchmark are excluded): floor(99 × (rank - 1) / 3).
    assert _values(_rs_market(), IndicatorKey("rs", 2), ticker)[-1] == expected


def test_rs_is_null_for_the_benchmark_and_99_when_alone() -> None:
    tickers = {"ONLY": FrameSpec(1, [10.0, 10.0, 11.0])}
    assert _values(tickers, IndicatorKey("rs", 2), "ONLY") == [None, None, 99.0]
    assert _values(tickers, IndicatorKey("rs", 2), "FIXTURE-INDEX") == [None, None, None]
