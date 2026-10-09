"""The seeded random entry baseline (spec 0009, assumed decision 3, AC-8)."""

from __future__ import annotations

import numpy as np

from engine.baseline import Pool, eligible_pool, sample
from engine.contracts import Market
from engine.data.fixtures import BENCHMARK, FrameSpec, bar_date, make_market
from engine.indicators import cache_for

# AAA lives bars 1 to 10, BBB bars 4 to 12 (the end of the data), so AAA is delisted at 10.
MARKET = make_market({"AAA": FrameSpec(1, [5.0] * 10), "BBB": FrameSpec(4, [7.0] * 9)})


def _pairs(market: Market, rows: np.ndarray) -> list[tuple[str, int]]:
    """(ticker, 1 based signal bar) per row."""
    bars = cache_for(market).bars
    out = []
    for row in rows.tolist():
        ticker, day = bars["ticker"][row], bars["date"][row]
        out.append((ticker, next(b for b in range(1, 13) if bar_date(b) == day)))
    return out


def test_pool_is_every_non_benchmark_bar_but_the_last_sorted_by_entry_date_then_ticker() -> None:
    pool = eligible_pool(cache_for(MARKET), bar_date(3), oos_start=bar_date(9))
    # IS: entry dates bar 4 to 8 (signals 3 to 7); BBB's first signal is bar 4.
    assert _pairs(MARKET, pool.is_) == [
        ("AAA", 3),
        ("AAA", 4),
        ("BBB", 4),
        ("AAA", 5),
        ("BBB", 5),
        ("AAA", 6),
        ("BBB", 6),
        ("AAA", 7),
        ("BBB", 7),
    ]
    # OOS: entries from bar 9 on. AAA's last bar (10) and BBB's (12) never appear.
    assert _pairs(MARKET, pool.oos) == [
        ("AAA", 8),
        ("BBB", 8),
        ("AAA", 9),
        ("BBB", 9),
        ("BBB", 10),
        ("BBB", 11),
    ]


def test_pool_never_holds_the_benchmark_or_a_last_bar() -> None:
    cache = cache_for(MARKET)
    pool = eligible_pool(cache, bar_date(1), oos_start=bar_date(6))
    rows = np.concatenate([pool.is_, pool.oos])
    assert BENCHMARK not in {cache.bars["ticker"][r] for r in rows.tolist()}
    assert not cache.is_last.to_numpy()[rows].any()
    assert len(set(rows.tolist())) == len(rows) == 9 + 8  # AAA 1 to 9, BBB 4 to 11


def test_same_seed_same_sample_and_a_different_seed_differs() -> None:
    pool = Pool(is_=np.arange(1000, dtype=np.int64), oos=np.arange(1000, 1400, dtype=np.int64))
    a = sample(pool, 120, 40, seed=42)
    assert np.array_equal(a, sample(pool, 120, 40, seed=42))
    assert not np.array_equal(a, sample(pool, 120, 40, seed=7))
    assert len(a) == 160
    assert set(a[:120].tolist()) <= set(pool.is_.tolist())
    assert set(a[120:].tolist()) <= set(pool.oos.tolist())
    assert len(set(a.tolist())) == 160  # no replacement while the pool is big enough


def test_draws_is_first_then_oos_from_one_generator() -> None:
    pool = Pool(is_=np.arange(50, dtype=np.int64), oos=np.arange(50, 80, dtype=np.int64))
    rng = np.random.default_rng(42)
    expected_is = pool.is_[rng.choice(50, size=5, replace=False)]
    expected_oos = pool.oos[rng.choice(30, size=3, replace=False)]
    assert sample(pool, 5, 3, seed=42).tolist() == [*expected_is, *expected_oos]


def test_a_pool_smaller_than_its_count_draws_with_replacement() -> None:
    pool = Pool(is_=np.array([7, 8], dtype=np.int64), oos=np.array([9], dtype=np.int64))
    drawn = sample(pool, 5, 3, seed=42)
    assert len(drawn) == 8
    assert set(drawn[:5].tolist()) <= {7, 8}
    assert drawn[5:].tolist() == [9, 9, 9]


def test_an_empty_pool_draws_nothing_and_leaves_the_other_segment_alone() -> None:
    empty = np.empty(0, dtype=np.int64)
    oos = np.arange(10, dtype=np.int64)
    assert sample(Pool(is_=empty, oos=empty), 4, 2, seed=42).tolist() == []
    # An empty IS pool takes nothing from the generator, so OOS draws as if first.
    alone = sample(Pool(is_=empty, oos=oos), 4, 3, seed=42)
    assert alone.tolist() == oos[np.random.default_rng(42).choice(10, 3, replace=False)].tolist()


def test_zero_counts_draw_nothing() -> None:
    pool = Pool(is_=np.arange(10, dtype=np.int64), oos=np.arange(10, 20, dtype=np.int64))
    assert sample(pool, 0, 0, seed=42).tolist() == []
