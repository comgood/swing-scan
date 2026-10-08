"""R-3, R-4, R-5 and R-7 on custom rules, beyond the two templates (spec 0008, AC-11).

Each case builds a rule the builder could send (varied indicators, an indicator or a number on
the right, crosses, offsets, mults) and checks the compiled rule or `engine.api.scan` against
values worked out by hand or by a brute force reference.
"""

from __future__ import annotations

import polars as pl
import pytest

from engine.api import scan
from engine.contracts import IndOperand, Rule, ScanRequest
from engine.data.fixtures import FrameSpec, bar_date, make_market
from engine.indicators import IndicatorCache, cache_for
from engine.rules import compile_rule, operand_values

from .helpers import ind, rule, val


def _of(cache: IndicatorCache, series: pl.Series, ticker: str = "AAA") -> list[object]:
    return series.filter(cache.bars["ticker"] == ticker).to_list()


def _hits(rule_: Rule, tickers: dict[str, FrameSpec], bar: int) -> list[str]:
    request = ScanRequest(rule=rule_, as_of=bar_date(bar))
    return [row.ticker for row in scan(request, make_market(tickers)).rows]


# R-3: a cross is true only on the bar where A first passes B.


def test_crosses_above_an_indicator_on_the_right() -> None:
    # A = close goes 9 -> 11, B = open held at 10: only bar 3 crosses.
    close = [9.0, 9.0, 11.0, 11.0, 12.0]
    market = make_market({"AAA": FrameSpec(1, close, open=[10.0] * 5)})
    cache = cache_for(market)
    compiled = compile_rule(rule((ind("close"), "crosses_above", ind("open"))), cache)
    assert _of(cache, compiled.value) == [False, False, True, False, False]
    assert _of(cache, compiled.valid) == [False, True, True, True, True]


def test_crosses_above_through_scan_hits_only_on_the_crossing_session() -> None:
    tickers = {"AAA": FrameSpec(1, [9.0, 9.0, 11.0, 11.0, 12.0])}
    crossing = rule((ind("close"), "crosses_above", val(10)))
    assert [_hits(crossing, tickers, bar) for bar in range(1, 6)] == [[], [], ["AAA"], [], []]


def test_crosses_above_a_windowed_indicator_with_a_mult() -> None:
    # sma(2) = [-, 10, 11, 12.5, 12.5] and 1.1 x sma(2) = [-, 11, 12.1, 13.75, 13.75].
    market = make_market({"AAA": FrameSpec(1, [10.0, 10.0, 12.0, 13.0, 12.0])})
    cache = cache_for(market)
    right = ind("sma", 2, mult=1.1)
    assert _of(cache, operand_values(right, cache))[1:] == pytest.approx([11.0, 12.1, 13.75, 13.75])
    # With the mult the close never gets above, so there is no cross at all.
    compiled = compile_rule(rule((ind("close"), "crosses_above", right)), cache)
    assert _of(cache, compiled.value) == [False] * 5
    # Without it the close is above on bars 3 and 4; only bar 3 is the cross.
    plain = compile_rule(rule((ind("close"), "crosses_above", ind("sma", 2))), cache)
    assert _of(cache, plain.value) == [False, False, True, False, False]


def test_crosses_below_with_an_offset_on_the_left() -> None:
    # close[1] = [-, 11, 11, 9, 9, 8]: below 10 from bar 4, so only bar 4 crosses.
    market = make_market({"AAA": FrameSpec(1, [11.0, 11.0, 9.0, 9.0, 8.0, 8.0])})
    cache = cache_for(market)
    compiled = compile_rule(rule((ind("close", offset=1), "crosses_below", val(10))), cache)
    assert _of(cache, compiled.valid) == [False, False, True, True, True, True]
    assert _of(cache, compiled.value) == [False, False, False, True, False, False]


def test_a_cross_after_a_dip_back_fires_again() -> None:
    market = make_market({"AAA": FrameSpec(1, [9.0, 11.0, 12.0, 9.0, 11.0])})
    cache = cache_for(market)
    compiled = compile_rule(rule((ind("close"), "crosses_above", val(10))), cache)
    assert _of(cache, compiled.value) == [False, True, False, False, True]


def test_a_cross_never_reads_across_tickers() -> None:
    # AAA ends above 10 and BBB starts above 10: BBB's first bar is not a cross.
    market = make_market({"AAA": FrameSpec(1, [9.0, 11.0]), "BBB": FrameSpec(1, [11.0, 12.0])})
    cache = cache_for(market)
    compiled = compile_rule(rule((ind("close"), "crosses_above", val(10))), cache)
    assert _of(cache, compiled.value, "BBB") == [False, False]


# R-4: highest(n, offset=k) is the max high of bars t-n-k+1 .. t-k (today excluded for k >= 1).


HIGH = [3.0, 8.0, 5.0, 4.0, 9.0, 2.0, 7.0, 12.0, 6.0, 1.0, 15.0, 4.0]
LOW = [h - 1.0 for h in HIGH]


def _reference(values: list[float], n: int, offset: int, how: str) -> list[float | None]:
    pick = max if how == "max" else min
    out: list[float | None] = []
    for t in range(len(values)):
        first = t - offset - n + 1
        out.append(pick(values[first : t - offset + 1]) if first >= 0 else None)
    return out


@pytest.mark.parametrize(("n", "offset"), [(5, 1), (3, 0), (2, 4), (5, 7)])
def test_highest_and_lowest_match_a_brute_force_window(n: int, offset: int) -> None:
    market = make_market({"AAA": FrameSpec(1, HIGH, high=HIGH, low=LOW)})
    cache = cache_for(market)
    highest = _of(cache, operand_values(ind("highest", n, offset=offset), cache))
    lowest = _of(cache, operand_values(ind("lowest", n, offset=offset), cache))
    assert highest == _reference(HIGH, n, offset, "max")
    assert lowest == _reference(LOW, n, offset, "min")


def test_highest_offset_one_excludes_a_record_high_today() -> None:
    # Bar 11 sets a new high (15): today is excluded, so highest(5)[1] is 12, not 15.
    market = make_market({"AAA": FrameSpec(1, HIGH, high=HIGH)})
    cache = cache_for(market)
    assert _of(cache, operand_values(ind("highest", 5, offset=1), cache))[10] == 12.0
    breakout = compile_rule(rule((ind("high"), ">", ind("highest", 5, offset=1))), cache)
    # high > the prior 5 highs: bars 8 (12 > 9) and 11 (15 > 12). Bar 5 (9 > 8) is not a
    # hit: it has only 4 prior bars, so highest(5)[1] is not computable there yet (R-5).
    assert [i + 1 for i, hit in enumerate(_of(cache, breakout.value)) if hit] == [8, 11]


# R-5: a condition whose operand cannot be computed yet is invalid (never a hit).


def test_close_above_sma50_on_30_bars_is_invalid_on_every_bar() -> None:
    tickers = {"YNG": FrameSpec(1, [10.0 + i for i in range(30)])}  # rising: true if computed
    market = make_market(tickers)
    cache = cache_for(market)
    compiled = compile_rule(rule((ind("close"), ">", ind("sma", 50))), cache)
    assert _of(cache, compiled.valid, "YNG") == [False] * 30
    assert _of(cache, compiled.value, "YNG") == [False] * 30
    hits = [_hits(rule((ind("close"), ">", ind("sma", 50))), tickers, bar) for bar in range(1, 31)]
    assert hits == [[]] * 30


@pytest.mark.parametrize(
    ("operand", "first_valid_bar"),
    [
        (ind("sma", 5), 5),
        (ind("ema", 5), 5),
        (ind("atr", 5), 5),
        (ind("highest", 5), 5),
        (ind("avg_volume", 5), 5),
        (ind("rsi", 5), 6),
        (ind("ret", 5), 6),
        (ind("sma", 5, offset=3), 8),
        (ind("close", offset=4), 5),
        (ind("rs", 5, mult=2.0), 6),
    ],
    ids=str,
)
def test_each_indicator_is_invalid_until_its_window_fills(
    operand: IndOperand, first_valid_bar: int
) -> None:
    close = [10.0 + (i % 3) for i in range(12)]
    market = make_market({"AAA": FrameSpec(1, close)})
    cache = cache_for(market)
    # `>= -1e9` is true for any computed value, so `value` shows exactly where it is valid.
    compiled = compile_rule(rule((operand, ">=", val(-1e9))), cache)
    expected = [bar >= first_valid_bar for bar in range(1, 13)]
    assert _of(cache, compiled.valid) == expected
    assert _of(cache, compiled.value) == expected


def test_one_young_operand_makes_the_whole_rule_invalid() -> None:
    # close > 5 holds from bar 1, but rsi(3) < 101 is not computable until bar 4.
    market = make_market({"AAA": FrameSpec(1, [10.0, 11.0, 10.0, 12.0, 13.0])})
    cache = cache_for(market)
    compiled = compile_rule(
        rule((ind("close"), ">", val(5)), (ind("rsi", 3), "<", val(101))), cache
    )
    assert _of(cache, compiled.valid) == [False, False, False, True, True]
    assert _of(cache, compiled.value) == [False, False, False, True, True]


# Numbers and indicators on the right, mults on either side.


def test_mult_on_the_left_and_an_indicator_on_the_right() -> None:
    # volume > 2 x avg_volume(3), written as 0.5 x volume > avg_volume(3).
    volume = [100.0, 100.0, 100.0, 400.0, 100.0]
    market = make_market({"AAA": FrameSpec(1, [10.0] * 5, volume=volume)})
    cache = cache_for(market)
    # avg_volume(3) on bar 4 = 200; 0.5 x 400 = 200 is not > 200. On bar 4 with >=: true.
    strict = compile_rule(rule((ind("volume", mult=0.5), ">", ind("avg_volume", 3))), cache)
    loose = compile_rule(rule((ind("volume", mult=0.5), ">=", ind("avg_volume", 3))), cache)
    assert _of(cache, strict.value) == [False] * 5
    assert _of(cache, loose.value) == [False, False, False, True, False]


def test_a_custom_rule_through_scan_lists_its_operands() -> None:
    # ema(3) above close[2] and rsi(2) < 100 (not a straight line up), with a number right side.
    tickers = {
        "UP": FrameSpec(1, [10.0, 11.0, 12.0, 11.5, 13.0, 14.0]),
        "DOWN": FrameSpec(1, [14.0, 13.0, 12.0, 11.0, 10.0, 9.0]),
    }
    custom = rule(
        (ind("ema", 3), ">", ind("close", offset=2)),
        (ind("rsi", 2), "<", val(100)),
        (ind("close"), "<=", val(20)),
    )
    result = scan(ScanRequest(rule=custom), make_market(tickers))
    assert result.columns == ["ema(3)", "close[2]", "rsi(2)", "close"]
    assert [row.ticker for row in result.rows] == ["UP"]
    ema = 11.0  # seed: mean(10, 11, 12) on bar 3
    for close in (11.5, 13.0, 14.0):
        ema += 0.5 * (close - ema)
    assert result.rows[0].operands[:2] == pytest.approx([ema, 11.5])


# R-7: rs(n) is a 0 to 99 percentile of ret(n), the best ticker gets 99.


def _rs_tickers(n_tickers: int, bars: int) -> dict[str, FrameSpec]:
    """Ticker Tk grows by a fixed rate k (in basis points) per bar, so T{n} has the best ret."""
    return {
        f"T{k:02d}": FrameSpec(1, [10.0 * (1 + k / 10_000) ** i for i in range(bars)])
        for k in range(1, n_tickers + 1)
    }


def test_rs126_lies_in_0_to_99_and_the_best_return_gets_99() -> None:
    market = make_market(_rs_tickers(7, 130))
    cache = cache_for(market)
    values = operand_values(ind("rs"), cache)  # n defaults to 126
    frame = cache.bars.select("ticker", "date").with_columns(values.alias("rs"))
    computed = frame.filter(pl.col("rs").is_not_null())
    assert computed["rs"].min() == 0.0
    assert computed["rs"].max() == 99.0
    assert computed["date"].unique().sort().to_list() == [bar_date(b) for b in range(127, 131)]
    for day in computed.partition_by("date"):
        assert day.sort("rs")["ticker"].to_list() == [f"T{k:02d}" for k in range(1, 8)]
        assert set(day["rs"].to_list()) == {0.0, 16.0, 33.0, 49.0, 66.0, 82.0, 99.0}


def test_a_rs_rule_keeps_only_the_best_ticker() -> None:
    tickers = _rs_tickers(5, 130)
    assert _hits(rule((ind("rs", 126), ">=", val(99))), tickers, 130) == ["T05"]
    assert _hits(rule((ind("rs", 126), ">=", val(99))), tickers, 126) == []  # warm-up
