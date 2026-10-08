"""The indicator cache: one per loaded market, shared by every request (spec 0005, AC-7).

A least recently used cache of 64 columns, keyed by `(ind, n)`. Pinned columns (the
templates', warmed when the API starts) are never evicted. The cache only changes speed,
never results. FastAPI runs sync routes on worker threads, so every read and write holds
the lock.
"""

from __future__ import annotations

import threading
import weakref
from collections import OrderedDict
from collections.abc import Iterable
from datetime import date

import polars as pl

from engine.contracts import Market

from .compute import POS, IndicatorKey, compute, dependencies

CAPACITY = 64
"""Columns kept per market; pinned columns count toward it but are never evicted."""


class IndicatorCache:
    """Indicator columns for one market, aligned to `market.bars` row order."""

    def __init__(self, market: Market, capacity: int = CAPACITY) -> None:
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
        self.capacity = capacity
        self._lock = threading.RLock()
        self._columns: OrderedDict[IndicatorKey, pl.Series] = OrderedDict()
        self._pinned: set[IndicatorKey] = set()

    def __contains__(self, key: IndicatorKey) -> bool:
        with self._lock:
            return key in self._columns

    def __len__(self) -> int:
        with self._lock:
            return len(self._columns)

    @property
    def pinned(self) -> frozenset[IndicatorKey]:
        with self._lock:
            return frozenset(self._pinned)

    def get(self, key: IndicatorKey) -> pl.Series:
        """The cached column for `key`, computed on first use (least recently used order)."""
        with self._lock:
            column = self._columns.get(key)
            if column is not None:
                self._columns.move_to_end(key)
                return column
            column = compute(key, self.bars, self.get, self.benchmark)
            self._columns[key] = column
            self._evict()
            return column

    def pin(self, keys: Iterable[IndicatorKey]) -> None:
        """Compute `keys` now and never evict them (the template columns, warmed at start)."""
        wanted = list(dict.fromkeys(dependencies(keys)))
        with self._lock:
            self._pinned.update(wanted)  # before computing, so nothing pinned is evicted
            for key in wanted:
                self.get(key)

    def _evict(self) -> None:
        excess = len(self._columns) - self.capacity
        if excess <= 0:
            return
        for key in [k for k in self._columns if k not in self._pinned][:excess]:
            del self._columns[key]


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
