"""Plain NumPy views of a market's bars for the simulator loops (spec 0007).

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
Bools = npt.NDArray[np.bool_]


@dataclass(frozen=True)
class BarArrays:
    ticker: list[str]
    date: list[date]
    open: Floats
    high: Floats
    low: Floats
    close: Floats
    is_last: Bools
    """The ticker's last row in this market (a delisting or the end of the data)."""
    is_delisting: Bools
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
            open=bars["open"].to_numpy(),
            high=bars["high"].to_numpy(),
            low=bars["low"].to_numpy(),
            close=bars["close"].to_numpy(),
            is_last=cache.is_last.to_numpy(),
            is_delisting=bars.select(delisting).to_series().to_numpy(),
        )

    def view(self, row: int, b: int, *, is_final: bool, horizon: int | None = None) -> BarView:
        return BarView(
            open=float(self.open[row]),
            high=float(self.high[row]),
            low=float(self.low[row]),
            close=float(self.close[row]),
            b=b,
            is_delisting=bool(self.is_delisting[row]),
            is_final=is_final or bool(self.is_last[row]),
            horizon=horizon,
        )
