"""Random entries: the exit lab's baseline (spec 0009, assumed decision 3).

The pool is every non benchmark (ticker, signal session t) with t from the window start on,
where the ticker also has a bar at t + 1, so t is never its last bar. Entries fill at
open(t + 1) like a real signal, and the segment is the entry date's. No rule, cooldown or
exit type is involved here, so random entries go through exactly the same exits as the
strategy's.

Rows are signal rows in `market.bars` order, the same row space as the strategy's signals.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import numpy.typing as npt
import polars as pl

from engine.indicators import IndicatorCache

Rows = npt.NDArray[np.int64]

_ROW = "_row"
_ENTRY = "_entry_date"
_LAST = "_is_last"


@dataclass(frozen=True)
class Pool:
    """Eligible signal rows, each segment sorted by (entry date, ticker)."""

    is_: Rows
    oos: Rows


def eligible_pool(cache: IndicatorCache, start: date, oos_start: date) -> Pool:
    """The IS and OOS pools on the (already cut) market behind `cache`. A row's segment is
    its entry date's: OOS from `oos_start` on."""
    frame = (
        cache.bars.select("ticker", "date")
        .with_columns(
            pl.int_range(pl.len(), dtype=pl.Int64).alias(_ROW),
            # The next row is the same ticker whenever the row is not the ticker's last.
            pl.col("date").shift(-1).alias(_ENTRY),
            cache.is_last.alias(_LAST),
        )
        .filter((pl.col("ticker") != cache.benchmark) & ~pl.col(_LAST) & (pl.col("date") >= start))
        .sort([_ENTRY, "ticker"])
    )
    oos = frame[_ENTRY] >= oos_start
    return Pool(
        is_=frame.filter(~oos)[_ROW].to_numpy(),
        oos=frame.filter(oos)[_ROW].to_numpy(),
    )


def _draw(rng: np.random.Generator, pool: Rows, count: int) -> Rows:
    """`count` rows of `pool`, without replacement unless the non empty pool is too small.
    An empty pool, or a count of 0, draws nothing and leaves `rng` untouched."""
    if count == 0 or len(pool) == 0:
        return np.empty(0, dtype=np.int64)
    picks = rng.choice(len(pool), size=count, replace=len(pool) < count)
    return pool[picks]


def sample(pool: Pool, is_count: int, oos_count: int, seed: int) -> Rows:
    """Signal rows for `is_count` IS and `oos_count` OOS random entries. One
    `default_rng(seed)` draws IS first, then OOS, so the same inputs give the same rows."""
    rng = np.random.default_rng(seed)
    return np.concatenate([_draw(rng, pool.is_, is_count), _draw(rng, pool.oos, oos_count)])
