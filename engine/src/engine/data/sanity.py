"""Bar sanity checks on top of the frozen `validate_market` (D-2, spec 0006)."""

from __future__ import annotations

import polars as pl

from engine.contracts import Market, MarketError, validate_market

PRICES = ("open", "high", "low", "close")


def _sample(df: pl.DataFrame) -> str:
    first = df.sort("ticker", "date").row(0, named=True)
    return f"first {first['ticker']} {first['date']}"


def bar_problems(market: Market) -> list[str]:
    """Every D-2 problem in the market's bars, as readable lines (empty when sane)."""
    bars, securities = market.bars, market.securities
    problems: list[str] = []

    checks: list[tuple[str, pl.Expr]] = [
        (
            "price is null, not finite or not positive",
            pl.any_horizontal(
                *(pl.col(c).is_null() | ~pl.col(c).is_finite() | (pl.col(c) <= 0) for c in PRICES)
            ),
        ),
        ("low above min(open, close)", pl.col("low") > pl.min_horizontal("open", "close")),
        ("high below max(open, close)", pl.col("high") < pl.max_horizontal("open", "close")),
        ("volume not positive", pl.col("volume").is_null() | ~(pl.col("volume") > 0)),
    ]
    for label, expr in checks:
        bad = bars.filter(expr)
        if bad.height:
            problems.append(f"bars: {bad.height} rows with {label}, {_sample(bad)}")

    dated = bars.join(
        securities.select("ticker", "listed_from", "delisted_on"), on="ticker", how="inner"
    )
    early = dated.filter(pl.col("date") < pl.col("listed_from"))
    if early.height:
        problems.append(f"bars: {early.height} rows before listed_from, {_sample(early)}")
    late = dated.filter(
        pl.col("delisted_on").is_not_null() & (pl.col("date") > pl.col("delisted_on"))
    )
    if late.height:
        problems.append(f"bars: {late.height} rows after delisted_on, {_sample(late)}")
    return problems


def check_market(market: Market) -> None:
    """Raise `MarketError` unless the market passes `validate_market` and every D-2 check."""
    validate_market(market)
    problems = bar_problems(market)
    if problems:
        raise MarketError(problems)
