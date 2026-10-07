"""The indicator cache: one per loaded market, shared by every request (spec 0005, AC-7).

The cache only changes speed, never results. FastAPI runs sync routes on worker threads, so
every read and write holds the lock.
"""

from __future__ import annotations

import threading
import weakref
from datetime import date

import polars as pl

from engine.contracts import Market

from .compute import POS, IndicatorKey, compute


class IndicatorCache:
    """Indicator columns for one market, aligned to `market.bars` row order."""

    def __init__(self, market: Market) -> None:
        bars = market.bars
        self.bars: pl.DataFrame = bars.with_columns(
            pl.int_range(pl.len(), dtype=pl.Int64).over("ticker").alias(POS)
        )
        self.benchmark: str = market.meta.benchmark
        self.pos: pl.Series = self.bars[POS]
        self.is_last: pl.Series = (
            self.bars.select((pl.col("ticker") != pl.col("ticker").shift(-1)).fill_null(True))
            .to_series()
            .alias("is_last")
        )
        self.sessions: list[date] = bars["date"].unique().sort().to_list()
        self._lock = threading.RLock()
        self._columns: dict[IndicatorKey, pl.Series] = {}

    def __contains__(self, key: IndicatorKey) -> bool:
        with self._lock:
            return key in self._columns

    def get(self, key: IndicatorKey) -> pl.Series:
        """The cached column for `key`, computed on first use."""
        with self._lock:
            column = self._columns.get(key)
            if column is None:
                column = compute(key, self.bars, self.get)
                self._columns[key] = column
            return column


_registry: dict[int, tuple[weakref.ref[Market], IndicatorCache]] = {}
_registry_lock = threading.Lock()


def cache_for(market: Market) -> IndicatorCache:
    """The one cache of `market`, created on first use and dropped with the market."""
    key = id(market)
    with _registry_lock:
        entry = _registry.get(key)
        if entry is not None and entry[0]() is market:
            return entry[1]
        cache = IndicatorCache(market)

        def _forget(_: weakref.ref[Market], key: int = key) -> None:
            _registry.pop(key, None)

        _registry[key] = (weakref.ref(market, _forget), cache)
        return cache
