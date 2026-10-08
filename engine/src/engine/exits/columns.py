"""Indicator columns the data reading exits hold, as NumPy arrays aligned to `market.bars`."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import numpy.typing as npt
import polars as pl

from engine.indicators import IndicatorKey

Floats = npt.NDArray[np.float64]
Column = Callable[[IndicatorKey], pl.Series]
"""Looks up one indicator column by key, e.g. `IndicatorCache.get`."""


def floats(column: Column, key: IndicatorKey) -> Floats:
    """The column as floats, nulls (warm up) as NaN."""
    return column(key).cast(pl.Float64).fill_null(float("nan")).to_numpy()
