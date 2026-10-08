"""Window indicators and price fields against hand values (spec 0005, AC-2)."""

from __future__ import annotations

import pytest

from engine.data.fixtures import FrameSpec, make_market
from engine.indicators import IndicatorKey, cache_for


def _values(
    market_spec: dict[str, FrameSpec], key: IndicatorKey, ticker: str
) -> list[float | None]:
    market = make_market(market_spec)
    cache = cache_for(market)
    column = cache.get(key)
    mask = (cache.bars["ticker"] == ticker).to_list()
    return [v for v, keep in zip(column.to_list(), mask, strict=True) if keep]


def test_price_fields_are_the_bars_own_values() -> None:
    spec = {"AAA": FrameSpec(1, [1.0, 2.0], volume=[10.0, 20.0])}
    assert _values(spec, IndicatorKey("close"), "AAA") == [1.0, 2.0]
    assert _values(spec, IndicatorKey("volume"), "AAA") == [10.0, 20.0]


def test_sma_first_exists_on_bar_n() -> None:
    spec = {"AAA": FrameSpec(1, [1.0, 2.0, 3.0, 4.0])}
    assert _values(spec, IndicatorKey("sma", 3), "AAA") == [None, None, 2.0, 3.0]


def test_avg_volume_uses_volume() -> None:
    spec = {"AAA": FrameSpec(1, [1.0] * 3, volume=[100.0, 200.0, 600.0])}
    assert _values(spec, IndicatorKey("avg_volume", 2), "AAA") == [None, 150.0, 400.0]


def test_highest_and_lowest_use_high_and_low() -> None:
    close = [5.0, 5.0, 5.0]
    spec = {"AAA": FrameSpec(1, close, high=[6.0, 9.0, 7.0], low=[4.0, 1.0, 3.0])}
    assert _values(spec, IndicatorKey("highest", 2), "AAA") == [None, 9.0, 9.0]
    assert _values(spec, IndicatorKey("lowest", 2), "AAA") == [None, 1.0, 1.0]


def test_windows_never_mix_tickers() -> None:
    # AAA sorts before BBB, so a window crossing the boundary would mix them.
    spec = {"AAA": FrameSpec(1, [100.0] * 3), "BBB": FrameSpec(1, [1.0, 2.0, 3.0])}
    assert _values(spec, IndicatorKey("sma", 2), "BBB") == [None, 1.5, 2.5]


def test_a_late_listing_warms_up_from_its_own_first_bar() -> None:
    spec = {"AAA": FrameSpec(1, [1.0] * 6), "LATE": FrameSpec(4, [3.0, 6.0, 9.0])}
    assert _values(spec, IndicatorKey("sma", 3), "LATE") == [None, None, 6.0]


def test_the_cache_returns_the_same_column() -> None:
    market = make_market({"AAA": FrameSpec(1, [1.0, 2.0, 3.0])})
    cache = cache_for(market)
    key = IndicatorKey("sma", 2)
    assert key not in cache
    first = cache.get(key)
    assert key in cache
    assert cache.get(key) is first
    assert cache_for(market) is cache


def test_a_windowed_indicator_needs_n() -> None:
    market = make_market({"AAA": FrameSpec(1, [1.0])})
    with pytest.raises(ValueError, match="needs n"):
        cache_for(market).get(IndicatorKey("sma"))
