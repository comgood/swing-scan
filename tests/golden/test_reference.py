"""Self checks for the golden reference, using the worked examples in doc 01 section 6.

These test QA's reference, not the engine, so they are not gated: they always block CI.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from golden.reference import TickerBars, entry_signals, hits, operand_series, rule_series


def _bars(close: list[float], high: list[float] | None = None) -> TickerBars:
    start = date(2020, 1, 1)
    dates = [start + timedelta(days=i) for i in range(len(close))]
    return TickerBars(
        ticker="AAA",
        dates=dates,
        open=close,
        high=high if high is not None else close,
        low=close,
        close=close,
        volume=[1e6] * len(close),
    )


def _ind(ind: str, n: int | None = None, offset: int = 0, mult: float = 1.0) -> dict[str, Any]:
    return {"kind": "ind", "ind": ind, "n": n, "offset": offset, "mult": mult}


def _val(x: float) -> dict[str, Any]:
    return {"kind": "value", "value": x}


def _rule(*conditions: tuple[dict[str, Any], str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "name": "t",
        "conditions": [{"left": a, "op": op, "right": b} for a, op, b in conditions],
    }


def test_crosses_above_true_only_on_first_bar_above() -> None:
    # R-3: A goes 9 -> 11 against B = 10.
    bars = _bars([9, 9, 11, 11, 11])
    rule = _rule((_ind("close"), "crosses_above", _val(10)))
    assert rule_series(bars, rule) == [None, False, True, False, False]


def test_highest_with_offset_excludes_today() -> None:
    # R-4: highest(5)[1] at t is max(high[t-5 .. t-1]).
    high = [1.0, 9.0, 2.0, 3.0, 4.0, 5.0, 6.0, 100.0]
    bars = _bars([1.0] * len(high), high=high)
    series = operand_series(bars, _ind("highest", n=5, offset=1))
    assert series[:5] == [None] * 5
    assert series[5] == 9.0  # bars 0..4
    assert series[6] == max(high[1:6])
    assert series[7] == max(high[2:7])  # today's 100 excluded


def test_warm_up_is_invalid_not_false() -> None:
    # R-5: 30 bars and close > sma(50) is invalid on every bar, never a hit.
    bars = _bars([10.0 + i for i in range(30)])
    rule = _rule((_ind("close"), ">", _ind("sma", n=50)))
    assert rule_series(bars, rule) == [None] * 30
    assert not any(hits(bars, rule))


def test_no_edge_on_first_valid_bar_then_edge_after_false() -> None:
    # B-14: close > highest(252)[1] first valid on bar 253 and true there: no signal.
    # Valid and false on bar 260, true on bar 261: signal on 261.
    close = [10.0 + 0.01 * i for i in range(259)]  # bars 1..259 strictly rising
    close.append(5.0)  # bar 260: false
    close += [20.0 + 0.01 * i for i in range(10)]  # bars 261..270: true
    bars = _bars(close)
    rule = _rule((_ind("close"), ">", _ind("highest", n=252, offset=1)))
    series = rule_series(bars, rule)
    assert series[251] is None and series[252] is True  # bar 252 invalid, bar 253 valid
    assert entry_signals(bars, rule) == [260]  # index 260 is bar 261


def test_no_edge_on_listing_day() -> None:
    # B-14: a rule true from a ticker's first bar never has an edge there.
    bars = _bars([10.0] * 5)
    assert entry_signals(bars, _rule((_ind("close"), ">", _val(5)))) == []


def test_no_entry_on_last_bar() -> None:
    # B-15: a rising edge on the last bar creates no entry, unless the scan view ignores it.
    bars = _bars([4.0, 4.0, 4.0, 6.0])
    rule = _rule((_ind("close"), ">", _val(5)))
    assert entry_signals(bars, rule) == []
    assert entry_signals(bars, rule, ignore_last_bar=True) == [3]


def test_cooldown_counts_from_accepted_signal() -> None:
    # B-16: rising edges at bars 100, 105 and 112: signals at 100 and 112 only.
    close = [4.0] * 130
    for bar in (100, 105, 112):
        close[bar - 1] = 6.0
    bars = _bars(close)
    signals = entry_signals(bars, _rule((_ind("close"), ">", _val(5))))
    assert [i + 1 for i in signals] == [100, 112]


@pytest.mark.parametrize(("blocked_bar", "accepted"), [(110, False), (111, True)])
def test_cooldown_boundary_is_ten_bars(blocked_bar: int, accepted: bool) -> None:
    close = [4.0] * 130
    close[99] = 6.0
    close[blocked_bar - 1] = 6.0
    bars = _bars(close)
    signals = [i + 1 for i in entry_signals(bars, _rule((_ind("close"), ">", _val(5))))]
    assert (blocked_bar in signals) is accepted


def test_ema_is_sma_seeded() -> None:
    bars = _bars([1.0, 2.0, 3.0, 4.0])
    series = operand_series(bars, _ind("ema", n=3))
    assert series[:2] == [None, None]
    assert series[2] == pytest.approx(2.0)
    assert series[3] == pytest.approx(0.5 * 4.0 + 0.5 * 2.0)


def test_mult_and_offset_apply_to_the_shifted_value() -> None:
    bars = _bars([1.0, 2.0, 3.0])
    assert operand_series(bars, _ind("close", offset=1, mult=1.5)) == [None, 1.5, 3.0]
