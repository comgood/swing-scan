"""The locked LRU cache with pinned keys (spec 0005, AC-7)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from engine.data.fixtures import FrameSpec, make_market
from engine.indicators import IndicatorCache, IndicatorKey


def _cache(capacity: int) -> IndicatorCache:
    return IndicatorCache(
        make_market({"AAA": FrameSpec(1, [float(i) for i in range(30)])}), capacity
    )


def test_the_least_recently_used_column_is_evicted() -> None:
    cache = _cache(2)
    a, b, c = IndicatorKey("sma", 2), IndicatorKey("sma", 3), IndicatorKey("sma", 4)
    cache.get(a)
    cache.get(b)
    cache.get(a)  # b is now the oldest
    cache.get(c)
    assert a in cache and c in cache and b not in cache
    assert len(cache) == 2


def test_pinned_columns_are_never_evicted() -> None:
    cache = _cache(2)
    pinned = IndicatorKey("ema", 5)
    cache.pin([pinned])
    for n in range(2, 12):
        cache.get(IndicatorKey("sma", n))
    assert pinned in cache
    assert cache.pinned == frozenset({pinned})


def test_pinning_rs_also_pins_its_ret() -> None:
    cache = _cache(1)
    cache.pin([IndicatorKey("rs", 5)])
    for n in range(2, 6):
        cache.get(IndicatorKey("sma", n))
    assert IndicatorKey("rs", 5) in cache
    assert IndicatorKey("ret", 5) in cache


def test_eviction_never_changes_values() -> None:
    cache = _cache(1)
    first = cache.get(IndicatorKey("sma", 3)).to_list()
    cache.get(IndicatorKey("sma", 4))
    assert IndicatorKey("sma", 3) not in cache
    assert cache.get(IndicatorKey("sma", 3)).to_list() == first


def test_concurrent_readers_get_one_column_per_key() -> None:
    cache = _cache(64)
    keys = [IndicatorKey("sma", 2 + i % 4) for i in range(40)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        columns = list(pool.map(cache.get, keys))
    for key, column in zip(keys, columns, strict=True):
        assert column is cache.get(key)
    assert len(cache) == 4
