"""The rule compiler: comparisons, offset, mult and validity (spec 0005, AC-2, AC-3)."""

from __future__ import annotations

import polars as pl
import pytest

from engine.contracts import Op
from engine.data.fixtures import FrameSpec, make_market
from engine.indicators import IndicatorCache, cache_for
from engine.rules import compile_rule, operand_values

from .helpers import ind, rule, val


def _of(cache: IndicatorCache, series: pl.Series, ticker: str = "AAA") -> list[object]:
    """The series on `ticker`'s rows only (the frame also holds the benchmark)."""
    return series.filter(cache.bars["ticker"] == ticker).to_list()


def test_highest_with_offset_one_excludes_today() -> None:
    high = [5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    market = make_market({"AAA": FrameSpec(1, high, high=high)})
    cache = cache_for(market)
    shifted = _of(cache, operand_values(ind("highest", 5, offset=1), cache))
    assert shifted == [None, None, None, None, None, 9.0]
    compiled = compile_rule(rule((ind("close"), ">", ind("highest", 5, offset=1))), cache)
    assert _of(cache, compiled.value) == [False] * 5 + [True]


def test_offset_never_reads_the_previous_ticker() -> None:
    market = make_market({"AAA": FrameSpec(1, [50.0, 60.0]), "BBB": FrameSpec(1, [1.0, 2.0])})
    cache = cache_for(market)
    assert _of(cache, operand_values(ind("close", offset=1), cache)) == [None, 50.0]
    assert _of(cache, operand_values(ind("close", offset=1), cache), "BBB") == [None, 1.0]


def test_mult_scales_after_lookup() -> None:
    market = make_market({"AAA": FrameSpec(1, [2.0, 4.0])})
    cache = cache_for(market)
    assert _of(cache, operand_values(ind("close", mult=1.5), cache)) == [3.0, 6.0]


@pytest.mark.parametrize(
    ("op", "expected"),
    [(">", [False, False, True]), ("<", [True, False, False]),
     (">=", [False, True, True]), ("<=", [True, True, False])],
)  # fmt: skip
def test_comparisons(op: Op, expected: list[bool]) -> None:
    market = make_market({"AAA": FrameSpec(1, [4.0, 5.0, 6.0])})
    cache = cache_for(market)
    compiled = compile_rule(rule((ind("close"), op, val(5))), cache)
    assert _of(cache, compiled.value) == expected
    assert _of(cache, compiled.valid) == [True] * 3


def test_a_rule_is_invalid_and_false_while_any_operand_warms_up() -> None:
    market = make_market({"AAA": FrameSpec(1, [10.0, 11.0, 12.0])})
    cache = cache_for(market)
    compiled = compile_rule(
        rule((ind("close"), ">", val(5)), (ind("close"), ">", ind("sma", 3, mult=0.5))), cache
    )
    assert _of(cache, compiled.valid) == [False, False, True]
    assert _of(cache, compiled.value) == [False, False, True]


def test_comparisons_use_raw_values() -> None:
    market = make_market({"AAA": FrameSpec(1, [5.0000000001])})
    cache = cache_for(market)
    compiled = compile_rule(rule((ind("close"), ">", val(5))), cache)
    assert _of(cache, compiled.value) == [True]
