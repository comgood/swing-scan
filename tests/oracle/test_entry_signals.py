"""Entry signal oracles B-14 to B-16 (doc 01 section 6.4, doc 02 section 6).

    edge(t)   = rule(t) and valid(t - 1) and not rule(t - 1)
    signal(t) = edge(t) and not last_bar(t) and no accepted signal in t - 10 .. t - 1

An entry fills at the next bar's open, so a signal on bar s shows up as a trade with
entry_date = bar_date(s + 1). Markets are built with `make_market` from close lists
(open, high and low default to the close).
"""

from __future__ import annotations

from engine.contracts import Market, entries_hash

from ._oracle import (
    FrameSpec,
    bar_date,
    close_above,
    config,
    ind,
    lab,
    make_market,
    portfolio,
    rule,
)

ONE_BAR = [{"type": "time", "bars": 1}]


def test_b14_first_valid_bar_is_not_an_edge_but_a_later_false_to_true_is() -> None:
    # close > highest(252)[1] first becomes valid on bar 253 (it needs bars 1 to 252).
    # Bar 253: 11 > 10, valid and true, but bar 252 was not valid, so no signal.
    # Bars 254 to 260: 10.5 > 11 is false. Bar 261: 12 > 11 is true after false: signal.
    closes = [10.0] * 252 + [11.0] + [10.5] * 7 + [12.0] * 5
    market = make_market({"EDG": FrameSpec(start_bar=1, close=closes)})
    breakout = rule((ind("close"), ">", ind("highest", 252, offset=1)))

    result = portfolio(breakout, ONE_BAR, market)

    assert [t.entry_date for t in result.trades] == [bar_date(262)]


def test_b14_a_listing_day_is_never_an_edge() -> None:
    # LATE lists on bar 5 already above 5, so close > 5 is true on its first bar with no
    # bar before it: no edge, ever. CTRL goes from 4 to 6 on bar 3: one signal, so the
    # test is not vacuous.
    market = make_market(
        {
            "LATE": FrameSpec(start_bar=5, close=[6.0] * 8),
            "CTRL": FrameSpec(start_bar=1, close=[4.0, 4.0] + [6.0] * 10),
        }
    )

    result = portfolio(close_above(5), ONE_BAR, market)

    assert [(t.ticker, t.entry_date) for t in result.trades] == [("CTRL", bar_date(4))]


def _last_bar_market() -> Market:
    # LBD: last bar 8 while the data runs to 20, so delisted; its edge is on bar 8.
    # EOD: alive to the end; its edge is on bar 20, the last bar of the data.
    # CTL: an edge on bar 10, which has a next bar, so it is the only entry.
    return make_market(
        {
            "LBD": FrameSpec(start_bar=1, close=[9.0] * 7 + [11.0]),
            "EOD": FrameSpec(start_bar=1, close=[9.0] * 19 + [11.0]),
            "CTL": FrameSpec(start_bar=1, close=[9.0] * 9 + [11.0] * 11),
        }
    )


def test_b15_no_entry_on_a_last_bar_in_portfolio_mode() -> None:
    result = portfolio(close_above(10), ONE_BAR, _last_bar_market())

    assert [(t.ticker, t.entry_date) for t in result.trades] == [("CTL", bar_date(11))]


def test_b15_no_entry_on_a_last_bar_in_trade_mode() -> None:
    configs = [config("a", *ONE_BAR), config("b", {"type": "stop_pct", "pct": 8})]
    result = lab(close_above(10), configs, _last_bar_market())

    assert result.entries.count == 1
    assert result.entries.hash == entries_hash([("CTL", bar_date(11))])


def _cooldown_market() -> Market:
    # Rising edges on bars 100, 105 and 112 (close > 10 after a close of 9).
    closes = [9.0] * 120
    for bar in (100, 105, 112):
        closes[bar - 1] = 11.0
    return make_market({"CDN": FrameSpec(start_bar=1, close=closes)})


def test_b16_cooldown_keeps_100_and_112_in_every_exit_config() -> None:
    # 105 falls inside 100 + 10, so it is dropped. 112 looks back over 102 to 111, where
    # no signal was accepted (105 was not), so it is kept. Exits never change entries.
    configs = [
        config("time 3", {"type": "time", "bars": 3}),
        config("stop and target", {"type": "stop_pct", "pct": 8}, {"type": "target", "pct": 15}),
        config("trail and time", {"type": "trail_pct", "pct": 10}, {"type": "time", "bars": 20}),
    ]
    result = lab(close_above(10), configs, _cooldown_market())

    expected = [("CDN", bar_date(101)), ("CDN", bar_date(113))]
    assert result.entries.count == 2
    assert result.entries.hash == entries_hash(expected)
    assert [(t.ticker, t.entry_date) for t in result.baseline_trades] == expected
    for row in result.rows:
        assert row.strategy.is_.n_trades + row.strategy.oos.n_trades == 2, row.name


def test_b16_cooldown_in_portfolio_mode() -> None:
    result = portfolio(close_above(10), [{"type": "time", "bars": 3}], _cooldown_market())

    assert [t.entry_date for t in result.trades] == [bar_date(101), bar_date(113)]
