"""Indicator formulas over a whole market at once (spec 0005, *Indicator conventions*).

Every function returns a Float64 series aligned to the bars' row order, which is sorted by
`(ticker, date)` with each ticker's bars contiguous. A window only counts once it lies fully
inside one ticker, which the `_pos` column (the row's position within its ticker, 0 based)
decides. A value without enough history is null. Nothing reads a bar after t.
"""

from __future__ import annotations

from collections.abc import Callable
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


def compute(key: IndicatorKey, bars: pl.DataFrame, lookup: Lookup) -> pl.Series:
    """The raw column for `key` (no offset, no mult), with nulls during warm up."""
    ind, n = key
    if ind in PRICE_FIELDS:
        return bars[ind].cast(pl.Float64).alias("value")
    if n is None:
        raise ValueError(f"{ind} needs n")
    if ind == "sma":
        return _window(bars, "close", "mean", n)
    if ind == "avg_volume":
        return _window(bars, "volume", "mean", n)
    if ind == "highest":
        return _window(bars, "high", "max", n)
    if ind == "lowest":
        return _window(bars, "low", "min", n)
    raise NotImplementedError(f"indicator {ind} arrives with the engine breadth milestone")
