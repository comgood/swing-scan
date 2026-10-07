"""AC-10: `validate_market` raises a clear error for each broken market."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import polars as pl
import pytest

from engine.contracts import Market, MarketError, validate_market
from engine.data.fixtures import FrameSpec, make_market


@pytest.fixture
def market() -> Market:
    return make_market({"AAA": FrameSpec(1, [10, 11, 12]), "BBB": FrameSpec(1, [5, 6])})


def test_a_good_market_passes(market: Market) -> None:
    validate_market(market)


Breaker = Callable[[Market], Market]

CASES: list[tuple[str, Breaker, str]] = [
    ("missing column", lambda m: replace(m, bars=m.bars.drop("volume")), "missing columns"),
    (
        "extra column",
        lambda m: replace(m, bars=m.bars.with_columns(pl.lit(1.0).alias("vwap"))),
        "unexpected columns",
    ),
    (
        "wrong dtype",
        lambda m: replace(m, bars=m.bars.with_columns(pl.col("volume").cast(pl.Int64))),
        "dtype",
    ),
    (
        "duplicate key",
        lambda m: replace(m, bars=pl.concat([m.bars, m.bars.head(1)]).sort("ticker", "date")),
        "duplicate (ticker, date)",
    ),
    ("unsorted", lambda m: replace(m, bars=m.bars.reverse()), "not sorted"),
    (
        "reason without date",
        lambda m: replace(
            m,
            securities=m.securities.with_columns(
                pl.when(pl.col("ticker") == "AAA")
                .then(pl.lit("acquired"))
                .otherwise(pl.col("delist_reason"))
                .alias("delist_reason")
            ),
        ),
        "set together",
    ),
    (
        "date without reason",
        lambda m: replace(
            m, securities=m.securities.with_columns(pl.lit(None, pl.String).alias("delist_reason"))
        ),
        "set together",
    ),
    (
        "ticker missing from securities",
        lambda m: replace(m, securities=m.securities.filter(pl.col("ticker") != "BBB")),
        "missing from securities",
    ),
    (
        "benchmark missing from bars",
        lambda m: replace(m, meta=m.meta.model_copy(update={"benchmark": "NOPE"})),
        "benchmark",
    ),
]


@pytest.mark.parametrize(("label", "breaker", "message"), CASES, ids=[c[0] for c in CASES])
def test_each_problem_is_named(market: Market, label: str, breaker: Breaker, message: str) -> None:
    with pytest.raises(MarketError, match=message.replace("(", r"\(").replace(")", r"\)")):
        validate_market(breaker(market))


def test_duplicate_securities_are_named(market: Market) -> None:  # covers: AC-10
    doubled = replace(market, securities=pl.concat([market.securities, market.securities.head(1)]))
    with pytest.raises(MarketError, match="duplicate tickers"):
        validate_market(doubled)


def test_every_key_problem_is_listed_at_once(market: Market) -> None:  # covers: AC-10
    broken = replace(
        market,
        bars=market.bars.reverse(),
        meta=market.meta.model_copy(update={"benchmark": "NOPE"}),
    )
    with pytest.raises(MarketError) as caught:
        validate_market(broken)
    assert len(caught.value.problems) == 2
