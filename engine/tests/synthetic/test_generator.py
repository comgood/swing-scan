"""The synthetic market generator (spec 0006): determinism, sanity, and planted features."""

from __future__ import annotations

from datetime import date

import numpy as np
import polars as pl
import pytest

from engine.contracts import Market
from engine.data import bar_problems
from engine.synthetic import BENCHMARK, GENERATOR_VERSION, SyntheticConfig, generate, sessions

SMALL = SyntheticConfig(n_tickers=40, n_sessions=400, min_delisted=3)


@pytest.fixture(scope="module")
def demo() -> Market:
    return generate(42)


def max_drawdown(market: Market) -> float:
    bench = market.bars.filter(pl.col("ticker") == market.meta.benchmark).sort("date")
    value: float = bench.select((pl.col("close") / pl.col("close").cum_max() - 1).min()).item()
    return value


def delisted(market: Market) -> pl.DataFrame:
    return market.securities.filter(pl.col("delisted_on").is_not_null())


def test_same_seed_gives_equal_frames_and_meta(demo: Market) -> None:  # D-1
    again = generate(42)
    assert demo.bars.equals(again.bars)
    assert demo.securities.equals(again.securities)
    assert demo.meta == again.meta


def test_different_seeds_give_different_markets() -> None:
    a, b = generate(1, SMALL), generate(2, SMALL)
    assert not a.bars.equals(b.bars)


def test_every_bar_is_sane(demo: Market) -> None:  # D-2
    assert bar_problems(demo) == []
    bars = demo.bars
    assert bars.filter(pl.col("low") > pl.min_horizontal("open", "close")).height == 0
    assert bars.filter(pl.col("high") < pl.max_horizontal("open", "close")).height == 0
    assert bars.filter(pl.col("volume") <= 0).height == 0


def test_nothing_trades_after_delisting_and_last_bar_is_delisted_on(demo: Market) -> None:
    lasts = demo.bars.group_by("ticker").agg(pl.col("date").max().alias("last"))
    joined = delisted(demo).join(lasts, on="ticker")
    assert joined.height == delisted(demo).height
    assert (joined["last"] == joined["delisted_on"]).all()


def test_bear_segment_and_delistings(demo: Market) -> None:  # D-3
    assert max_drawdown(demo) <= -0.20
    assert delisted(demo).height >= 20
    assert set(delisted(demo)["delist_reason"].to_list()) == {"bankruptcy", "acquired"}


@pytest.mark.parametrize("seed", range(8))
def test_planted_bear_holds_for_any_seed(seed: int) -> None:
    # The bear's total log return is at most -0.30, so the fall is at least 25.9%.
    assert max_drawdown(generate(seed, SMALL)) <= float(np.exp(-0.30) - 1)


def test_universe_shape_and_meta(demo: Market) -> None:
    meta = demo.meta
    assert meta.data_mode == "synthetic"
    assert meta.seed == 42
    assert meta.data_version == GENERATOR_VERSION
    assert meta.benchmark == BENCHMARK
    assert meta.survivors_only is False
    assert meta.n_tickers == 500
    assert demo.securities.height == 501
    assert demo.bars["ticker"].n_unique() == 501
    assert meta.start == date(2021, 1, 4)
    assert meta.end == sessions(date(2021, 1, 4), 1260)[-1]


def test_calendar_is_1260_weekdays_and_the_benchmark_covers_it(demo: Market) -> None:
    dates = demo.bars["date"].unique().sort()
    assert dates.len() == 1260
    assert all(d.weekday() < 5 for d in dates.to_list())
    bench = demo.bars.filter(pl.col("ticker") == BENCHMARK)
    assert bench.height == 1260
    assert bench["close"][0] == pytest.approx(1000.0)


def test_mid_sample_listings_start_on_listed_from(demo: Market) -> None:
    firsts = demo.bars.group_by("ticker").agg(pl.col("date").min().alias("first"))
    joined = demo.securities.join(firsts, on="ticker")
    assert (joined["first"] == joined["listed_from"]).all()
    late = joined.filter(pl.col("listed_from") > demo.meta.start)
    assert late.height == 25


def test_listings_and_delistings_are_disjoint(demo: Market) -> None:
    late = demo.securities.filter(pl.col("listed_from") > demo.meta.start)
    assert late.filter(pl.col("delisted_on").is_not_null()).height == 0


def test_tickers_are_invented_four_letter_symbols(demo: Market) -> None:
    stocks = demo.securities.filter(pl.col("ticker") != BENCHMARK)
    assert stocks["ticker"].str.contains(r"^[A-Z]{4}$").all()
    assert stocks["sector"].n_unique() == 10
    assert (stocks["sector"] != "Index").all()


def test_some_tickers_trade_under_the_template_price_filter(demo: Market) -> None:
    under_five = demo.bars.filter((pl.col("ticker") != BENCHMARK) & (pl.col("close") < 5))
    assert under_five["ticker"].n_unique() > 0


def test_planted_momentum_shows_in_the_data(demo: Market) -> None:
    # Trailing 63 session winners keep drifting up: the documented planted edge.
    stocks = demo.bars.filter(pl.col("ticker") != BENCHMARK).sort("ticker", "date")
    frame = stocks.with_columns(
        (pl.col("close") / pl.col("close").shift(63).over("ticker")).log().alias("past"),
        (pl.col("close").shift(-21).over("ticker") / pl.col("close")).log().alias("future"),
    ).drop_nulls()
    corr: float = frame.select(pl.corr("past", "future")).item()
    assert corr > 0


def test_momentum_off_is_a_real_switch() -> None:
    on = generate(3, SMALL)
    off = generate(
        3, SyntheticConfig(n_tickers=40, n_sessions=400, min_delisted=3, momentum_coef=0)
    )
    assert not on.bars.equals(off.bars)
    assert on.bars.filter(pl.col("ticker") == BENCHMARK).equals(
        off.bars.filter(pl.col("ticker") == BENCHMARK)
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"n_tickers": 0}, "n_tickers"),
        ({"n_sessions": 100}, "n_sessions"),
        ({"start": date(2021, 1, 2)}, "weekday"),
        ({"n_tickers": 30, "min_delisted": 30}, "exceed"),
        ({"bear_log_return_range": (-0.1, 0.1)}, "bear_log_return_range"),
    ],
)
def test_config_rejects_impossible_values(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        SyntheticConfig(**kwargs)  # type: ignore[arg-type]


def test_sessions_skips_weekends() -> None:
    days = sessions(date(2021, 1, 1), 3)  # Friday
    assert days == [date(2021, 1, 1), date(2021, 1, 4), date(2021, 1, 5)]


def closes(market: Market, ticker: str) -> np.ndarray:
    return market.bars.filter(pl.col("ticker") == ticker).sort("date")["close"].to_numpy()


def test_acquired_tickers_jump_on_announcement_then_stay_pinned(demo: Market) -> None:
    # Spec 0006: +25% to +40% on the session 20 before the last bar, then near flat.
    acquired = delisted(demo).filter(pl.col("delist_reason") == "acquired")["ticker"]
    assert acquired.len() > 0
    for ticker in acquired.to_list():
        close = closes(demo, ticker)
        jump = close[-21] / close[-22]
        assert 1.25 - 1e-3 <= jump <= 1.40 + 1e-3, (ticker, jump)
        assert abs(close[-1] / close[-21] - 1) < 0.05, ticker


def test_bankrupt_tickers_slide_into_their_last_bar(demo: Market) -> None:
    # Spec 0006: an extra -0.6% a day over the last 40 sessions (about -21% in total).
    bankrupt = delisted(demo).filter(pl.col("delist_reason") == "bankruptcy")["ticker"]
    assert bankrupt.len() > 0
    slides = [closes(demo, t)[-1] / closes(demo, t)[-41] for t in bankrupt.to_list()]
    assert float(np.median(slides)) < 0.85


def test_demo_index_holds_the_planted_bear_window(demo: Market) -> None:
    # Spec 0006: one bear of 120 to 180 sessions starting at session 300 to 700, whose
    # total log return is in [-0.45, -0.30]. The index is the market factor itself.
    log_close = np.log(closes(demo, BENCHMARK))
    found = False
    for length in range(120, 181):
        starts = np.arange(300, 701)
        move = log_close[starts + length - 1] - log_close[starts - 1]
        if np.any((move >= -0.45 - 1e-4) & (move <= -0.30 + 1e-4)):
            found = True
            break
    assert found


def test_prices_keep_four_decimals_and_volumes_are_whole(demo: Market) -> None:
    # Rounding is what keeps output identical across machines (spec 0006, randomness).
    bars = demo.bars
    for column in ("open", "high", "low", "close"):
        off = (bars[column] * 10_000 - (bars[column] * 10_000).round()).abs().max()
        assert off is not None and float(off) < 1e-6, column  # type: ignore[arg-type]
    assert (bars["volume"] == bars["volume"].round()).all()
    assert bars["volume"].min() >= 1  # type: ignore[operator]


def test_delisting_count_has_a_floor_of_min_delisted() -> None:
    # max(min_delisted, round(5% x n)): 40 tickers would give 2, the floor lifts it to 3.
    market = generate(5, SMALL)
    assert delisted(market).height == 3
    assert SyntheticConfig().n_delisted == 25


def test_generate_does_not_touch_global_numpy_random_state() -> None:
    np.random.seed(123)
    expected = np.random.random()
    np.random.seed(123)
    generate(4, SMALL)
    assert np.random.random() == expected
