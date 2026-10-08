"""The engine's indicators equal QA's loop based golden reference on a seeded random walk."""

from __future__ import annotations

import math
import random
from datetime import date

import pytest

from engine.data.fixtures import FrameSpec, bar_date, make_market
from engine.indicators import IndicatorKey, cache_for
from golden.reference import TickerBars, indicator


def _walk(seed: int, n_tickers: int = 6, n_bars: int = 160) -> dict[str, FrameSpec]:
    rng = random.Random(seed)  # noqa: S311 (test data)
    tickers: dict[str, FrameSpec] = {}
    for i in range(n_tickers):
        start = 1 if i % 3 else rng.randint(2, 40)  # some list late
        length = n_bars - start + 1 - (rng.randint(0, 30) if i % 2 else 0)  # some delist
        level, close, high, low, volume = 30.0, [], [], [], []
        for _ in range(length):
            level *= math.exp(rng.gauss(0.0, 0.02))
            close.append(level)
            high.append(level * (1 + abs(rng.gauss(0.0, 0.01))))
            low.append(level * (1 - abs(rng.gauss(0.0, 0.01))))
            volume.append(rng.lognormvariate(13.8, 0.35))
        tickers[f"T{i}"] = FrameSpec(start, close, high=high, low=low, volume=volume)
    return tickers


def _golden(ticker: str, spec: FrameSpec) -> TickerBars:
    n = len(spec.close)
    assert spec.high is not None and spec.low is not None and spec.volume is not None
    dates: list[date] = [bar_date(spec.start_bar + i) for i in range(n)]
    return TickerBars(ticker, dates, spec.close, spec.high, spec.low, spec.close, spec.volume)


KEYS = [
    IndicatorKey(ind, n)
    for ind in ("sma", "ema", "highest", "lowest", "avg_volume", "ret")
    for n in (2, 5, 21)
] + [IndicatorKey("close"), IndicatorKey("high"), IndicatorKey("volume")]


@pytest.mark.parametrize("key", KEYS, ids=lambda k: f"{k.ind}({k.n})")
def test_indicator_matches_the_golden_reference(key: IndicatorKey) -> None:
    tickers = _walk(seed=7)
    cache = cache_for(make_market(tickers))
    column = cache.get(key)
    for ticker, spec in tickers.items():
        ours = column.filter(cache.bars["ticker"] == ticker).to_list()
        theirs = indicator(_golden(ticker, spec), key.ind, key.n)
        assert [v is None for v in ours] == [v is None for v in theirs], ticker
        assert [v for v in ours if v is not None] == pytest.approx(
            [v for v in theirs if v is not None], rel=1e-12
        ), ticker
