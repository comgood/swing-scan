"""Indicator formulas over a whole market at once (spec 0005, *Indicator conventions*).

Every function returns a Float64 series aligned to the bars' row order, which is sorted by
`(ticker, date)` with each ticker's bars contiguous. A window only counts once it lies fully
inside one ticker, which the `_pos` column (the row's position within its ticker, 0 based)
decides. A value without enough history is null. Nothing reads a bar after t.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import NamedTuple

import polars as pl

from engine.contracts import IndName, IndOperand

POS = "_pos"
"""Row position within the ticker: 0 on the ticker's first bar."""

PRICE_FIELDS: frozenset[str] = frozenset({"open", "high", "low", "close", "volume"})


class IndicatorKey(NamedTuple):
    """One cached column. `offset` and `mult` are applied after lookup, never cached."""

    ind: IndName
    n: int | None = None


def key_of(operand: IndOperand) -> IndicatorKey:
    return IndicatorKey(operand.ind, operand.n)


def dependencies(keys: Iterable[IndicatorKey]) -> Iterator[IndicatorKey]:
    """Each key, followed by the columns it reads (`rs(n)` reads `ret(n)`)."""
    for key in keys:
        yield key
        if key.ind == "rs":
            yield IndicatorKey("ret", key.n)


Lookup = Callable[[IndicatorKey], pl.Series]
"""Reads another cached column (`rs(n)` reads `ret(n)`)."""


def _gated(bars: pl.DataFrame, expr: pl.Expr, first_pos: int) -> pl.Series:
    """`expr` where the row is at least `first_pos` bars into its ticker, else null."""
    gated = pl.when(pl.col(POS) >= first_pos).then(expr).otherwise(None)
    return bars.select(gated.cast(pl.Float64).alias("value")).to_series()


def _window(bars: pl.DataFrame, column: str, how: str, n: int) -> pl.Series:
    source = pl.col(column)
    rolled = {
        "mean": source.rolling_mean(n),
        "max": source.rolling_max(n),
        "min": source.rolling_min(n),
    }[how]
    return _gated(bars, rolled, n - 1)


def _previous_close() -> pl.Expr:
    """Yesterday's close of the same ticker, null on the ticker's first bar."""
    return pl.when(pl.col(POS) >= 1).then(pl.col("close").shift(1)).otherwise(None)


def _seeded_ewm(bars: pl.DataFrame, source: pl.Expr, n: int, alpha: float, seed: int) -> pl.Series:
    """A recursive average seeded with the simple mean of `n` values ending on row `seed`.

    `ema` uses `alpha = 2 / (n + 1)`; Wilder's `atr` and `rsi` use `alpha = 1 / n`, which is
    the same as `(prev × (n - 1) + x) / n`.
    """
    start = (
        pl.when(pl.col(POS) < seed)
        .then(None)
        .when(pl.col(POS) == seed)
        .then(source.rolling_mean(n))
        .otherwise(source)
    )
    smoothed = start.ewm_mean(alpha=alpha, adjust=False).over("ticker")
    return _gated(bars, smoothed, seed)


def _true_range() -> pl.Expr:
    prev = _previous_close()
    high, low = pl.col("high"), pl.col("low")
    full = pl.max_horizontal(high - low, (high - prev).abs(), (low - prev).abs())
    return pl.when(prev.is_null()).then(high - low).otherwise(full)


def _rsi(bars: pl.DataFrame, n: int) -> pl.Series:
    change = pl.col("close") - _previous_close()
    gain = _seeded_ewm(bars, pl.max_horizontal(change, pl.lit(0.0)), n, 1 / n, n)
    loss = _seeded_ewm(bars, pl.max_horizontal(-change, pl.lit(0.0)), n, 1 / n, n)
    rsi = pl.select(
        pl.when(loss == 0).then(100.0).otherwise(100.0 - 100.0 / (1.0 + gain / loss))
    ).to_series()
    return rsi.alias("value")


def _rs(bars: pl.DataFrame, ret: pl.Series, benchmark: str) -> pl.Series:
    """Percentile rank of `ret(n)` among the non benchmark tickers with a valid one on t.

    `floor(99 × (rank - 1) / (m - 1))`, ties take the highest rank, 99 when m = 1.
    """
    eligible = pl.when(pl.col("ticker") != benchmark).then(pl.col("ret"))
    rank = eligible.rank("max").over("date")
    m = eligible.count().over("date")
    rs = (
        pl.when(eligible.is_null())
        .then(None)
        .when(m == 1)
        .then(99.0)
        .otherwise(((rank - 1) * 99 / (m - 1)).floor())
    )
    frame = bars.select("ticker", "date").with_columns(ret.fill_nan(None).alias("ret"))
    return frame.select(rs.cast(pl.Float64).alias("value")).to_series()


def compute(key: IndicatorKey, bars: pl.DataFrame, lookup: Lookup, benchmark: str) -> pl.Series:
    """The raw column for `key` (no offset, no mult), with nulls during warm up."""
    ind, n = key
    if ind in PRICE_FIELDS:
        return bars[ind].cast(pl.Float64).alias("value")
    if n is None:
        raise ValueError(f"{ind} needs n")
    match ind:
        case "sma":
            return _window(bars, "close", "mean", n)
        case "avg_volume":
            return _window(bars, "volume", "mean", n)
        case "highest":
            return _window(bars, "high", "max", n)
        case "lowest":
            return _window(bars, "low", "min", n)
        case "ema":
            return _seeded_ewm(bars, pl.col("close"), n, 2 / (n + 1), n - 1)
        case "atr":
            return _seeded_ewm(bars, _true_range(), n, 1 / n, n - 1)
        case "rsi":
            return _rsi(bars, n)
        case "ret":
            return _gated(bars, pl.col("close") / pl.col("close").shift(n) - 1, n)
        case "rs":
            return _rs(bars, lookup(IndicatorKey("ret", n)), benchmark)
    raise ValueError(f"unknown indicator {ind!r}")
