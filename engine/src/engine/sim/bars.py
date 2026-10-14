"""A market's bars as plain Python lists for the simulator loops (spec 0007).

The loops read one row at a time, millions of times per exit lab run, and indexing a Python
list is several times cheaper than indexing a NumPy array and converting the scalar.

Rows follow `market.bars` order: sorted by `(ticker, date)`, each ticker's bars contiguous,
so a held position's next bar is always the next row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import numpy.typing as npt
import polars as pl

from engine.contracts import Market
from engine.indicators import IndicatorCache

from ..exits import BarView

Floats = npt.NDArray[np.float64]


@dataclass(frozen=True)
class BarArrays:
    ticker: list[str]
    date: list[date]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    is_last: list[bool]
    """The ticker's last row in this market (a delisting or the end of the data)."""
    is_delisting: list[bool]
    """The row's date is the ticker's `delisted_on`."""

    @classmethod
    def build(cls, market: Market, cache: IndicatorCache) -> BarArrays:
        bars = cache.bars.join(
            market.securities.select("ticker", "delisted_on"), on="ticker", how="left"
        ).sort("ticker", "date")
        delisting = (pl.col("date") == pl.col("delisted_on")).fill_null(False)
        return cls(
            ticker=bars["ticker"].to_list(),
            date=bars["date"].to_list(),
            open=bars["open"].to_list(),
            high=bars["high"].to_list(),
            low=bars["low"].to_list(),
            close=bars["close"].to_list(),
            is_last=cache.is_last.to_list(),
            is_delisting=bars.select(delisting).to_series().to_list(),
        )

    def view(self, row: int, b: int, *, is_final: bool, horizon: int | None = None) -> BarView:
        return BarView(
            open=self.open[row],
            high=self.high[row],
            low=self.low[row],
            close=self.close[row],
            b=b,
            is_delisting=self.is_delisting[row],
            is_final=is_final or self.is_last[row],
            horizon=horizon,
            row=row,
        )
