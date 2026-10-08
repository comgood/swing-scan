"""The shared entry signal function: edges, the last bar term and the cooldown chain (AC-4)."""

from __future__ import annotations

import polars as pl

from engine.data.fixtures import FrameSpec, make_market
from engine.indicators import cache_for
from engine.rules import compile_rule, entry_signals

from .helpers import ind, rule, val


def _signal_bars(
    tickers: dict[str, FrameSpec], ticker: str, *, ignore_last_bar: bool = False
) -> list[int]:
    """1 based bar numbers (relative to the ticker's first bar) of accepted signals."""
    cache = cache_for(make_market(tickers))
    compiled = compile_rule(rule((ind("close"), ">", val(10))), cache)
    signals = entry_signals(
        cache.pos, cache.is_last, compiled.valid, compiled.value, ignore_last_bar=ignore_last_bar
    )
    frame = cache.bars.with_columns(signals.alias("signal")).filter(
        (pl.col("ticker") == ticker) & pl.col("signal")
    )
    return [p + 1 for p in frame["_pos"].to_list()]


def test_cooldown_is_a_chain_of_accepted_signals() -> None:
    # Edges on bars 100, 108 and 115. 108 is inside 100's cooldown and dropped, so 115 sees
    # no accepted signal in 105 … 114 and is kept.
    closes = [9.0] * 130
    for bar in (100, 108, 115):
        closes[bar - 1] = 11.0
    assert _signal_bars({"CDN": FrameSpec(1, closes)}, "CDN") == [100, 115]


def test_the_cooldown_spans_exactly_ten_bars() -> None:
    closes = [9.0] * 40
    for bar in (10, 20, 21, 31):
        closes[bar - 1] = 11.0
    # 20 is within 10 … 20 of bar 10 (t - 10), so dropped; 31 is 21 bars after 10, kept.
    assert _signal_bars({"CDN": FrameSpec(1, closes)}, "CDN") == [10, 31]


def test_a_first_bar_is_never_an_edge() -> None:
    assert _signal_bars({"NEW": FrameSpec(1, [11.0] * 5)}, "NEW") == []


def test_a_last_bar_edge_counts_only_when_ignored() -> None:
    closes = [9.0] * 5 + [11.0]
    tickers = {"END": FrameSpec(1, closes)}
    assert _signal_bars(tickers, "END") == []
    assert _signal_bars(tickers, "END", ignore_last_bar=True) == [6]


def test_the_cooldown_does_not_cross_tickers() -> None:
    # AAA's signal on its last bar is accepted when ignored; BBB's edge on its bar 2 is only
    # a few rows later in the frame, but belongs to another ticker.
    tickers = {
        "AAA": FrameSpec(1, [9.0, 11.0]),
        "BBB": FrameSpec(1, [9.0, 11.0, 11.0]),
    }
    assert _signal_bars(tickers, "AAA", ignore_last_bar=True) == [2]
    assert _signal_bars(tickers, "BBB", ignore_last_bar=True) == [2]


def test_an_edge_needs_a_valid_previous_bar() -> None:
    # close > sma(3) becomes valid on bar 3 already true: not an edge. Bar 5 is false, bar 6
    # true after false: an edge.
    closes = [1.0, 2.0, 3.0, 4.0, 1.0, 9.0, 9.0]
    cache = cache_for(make_market({"AAA": FrameSpec(1, closes)}))
    compiled = compile_rule(rule((ind("close"), ">", ind("sma", 3))), cache)
    signals = entry_signals(cache.pos, cache.is_last, compiled.valid, compiled.value)
    assert [i + 1 for i, s in enumerate(signals.to_list()) if s] == [6]
