"""`engine.api.scan` on fixture markets (spec 0005, AC-1, AC-4, AC-5, AC-13)."""

from __future__ import annotations

from datetime import date

from engine.api import scan
from engine.contracts import TEMPLATES, Rule, ScanRequest, ScanResponse
from engine.data.fixtures import FrameSpec, bar_date, make_market

from .helpers import ind, rule, val

BREAKOUT = TEMPLATES[0].rule


def _scan(rule_: Rule, tickers: dict[str, FrameSpec], as_of: date | None = None) -> ScanResponse:
    return scan(ScanRequest(rule=rule_, as_of=as_of), make_market(tickers))


def _breakout_frame(breakout_bar: int, n_bars: int = 300) -> FrameSpec:
    """Flat at 10 with 1M volume, then a close of 12 on 2M volume on `breakout_bar`."""
    close = [10.0] * n_bars
    volume = [1_000_000.0] * n_bars
    close[breakout_bar - 1] = 12.0
    volume[breakout_bar - 1] = 2_000_000.0
    return FrameSpec(1, close, volume=volume)


def test_breakout_template_returns_the_breakout_with_its_operands() -> None:
    tickers = {"BRK": _breakout_frame(300), "FLAT": FrameSpec(1, [10.0] * 300)}
    result = _scan(BREAKOUT, tickers)
    assert result.as_of == bar_date(300)
    assert result.columns == ["close", "highest(252)[1]", "volume", "1.5×avg_volume(50)"]
    assert [r.ticker for r in result.rows] == ["BRK"]
    row = result.rows[0]
    assert row.close == 12.0
    average = (49 * 1_000_000.0 + 2_000_000.0) / 50
    assert row.operands == [12.0, 10.0, 2_000_000.0, 1.5 * average]
    assert row.new_today is True


def test_warm_up_is_never_a_hit() -> None:
    # 252 bars: highest(252)[1] needs 253, so nothing can be valid yet.
    assert _scan(BREAKOUT, {"BRK": _breakout_frame(252, n_bars=252)}).rows == []
    tickers = {"YNG": FrameSpec(1, [10.0] * 30)}
    assert _scan(rule((ind("close"), ">", ind("sma", 50))), tickers).rows == []


def test_only_tickers_alive_on_as_of_appear() -> None:
    tickers = {
        "GONE": FrameSpec(1, [10.0] * 5),  # delisted after bar 5
        "EDGE": FrameSpec(1, [10.0] * 8),  # last bar is bar 8
        "LATE": FrameSpec(9, [10.0] * 2),  # lists on bar 9
        "LIVE": FrameSpec(1, [10.0] * 10),
    }
    result = _scan(rule((ind("close"), ">", val(5))), tickers, as_of=bar_date(8))
    assert [r.ticker for r in result.rows] == ["EDGE", "LIVE"]


def test_the_benchmark_is_never_a_row() -> None:
    result = _scan(rule((ind("close"), ">", val(5))), {"AAA": FrameSpec(1, [10.0] * 3)})
    assert [r.ticker for r in result.rows] == ["AAA"]  # FIXTURE-INDEX closes at 100


def test_no_hidden_price_filter() -> None:
    result = _scan(rule((ind("close"), "<", val(4))), {"PNY": FrameSpec(1, [3.0] * 3)})
    assert [r.ticker for r in result.rows] == ["PNY"]


def test_rows_are_new_first_then_ticker_a_to_z() -> None:
    old = FrameSpec(1, [6.0, 6.0, 6.0])  # true since bar 1: never an edge
    new = FrameSpec(1, [4.0, 4.0, 6.0])  # edge on the last bar
    tickers = {"AOLD": old, "ZNEW": new, "BOLD": old, "MNEW": new}
    result = _scan(rule((ind("close"), ">", val(5))), tickers)
    assert [(r.ticker, r.new_today) for r in result.rows] == [
        ("MNEW", True),
        ("ZNEW", True),
        ("AOLD", False),
        ("BOLD", False),
    ]


def test_new_today_on_an_earlier_as_of_ignores_later_bars() -> None:
    tickers = {"AAA": FrameSpec(1, [4.0, 6.0, 4.0, 6.0])}
    result = _scan(rule((ind("close"), ">", val(5))), tickers, as_of=bar_date(2))
    assert [(r.ticker, r.new_today) for r in result.rows] == [("AAA", True)]
    # Bar 4 is an edge, but bar 2's accepted signal is within the cooldown.
    result = _scan(rule((ind("close"), ">", val(5))), tickers)
    assert [(r.ticker, r.new_today) for r in result.rows] == [("AAA", False)]


def test_columns_dedupe_operands_in_order_of_first_appearance() -> None:
    rule_ = rule(
        (ind("close"), ">", ind("sma", 2)),
        (ind("sma", 2), ">", val(1)),
        (ind("close"), ">", ind("sma", 2, mult=0.5)),
    )
    result = _scan(rule_, {"AAA": FrameSpec(1, [2.0, 4.0])})
    assert result.columns == ["close", "sma(2)", "0.5×sma(2)"]
    assert result.rows[0].operands == [4.0, 3.0, 1.5]
