"""Cash timing, missing bars, the IS to OOS hand off and truncation through `backtest()`
(spec 0007; the fixes for the 2026-10-09 review of feature 9)."""

from __future__ import annotations

from typing import Any

import polars as pl
import pytest

from engine import api
from engine.contracts import Market, Trade
from engine.data.fixtures import FrameSpec, bar_date, make_market
from engine.sim import make_trade

from .test_portfolio import SLIP, _edge_on, _run

TIME_50 = [{"type": "time", "bars": 50}]


def _drop(market: Market, ticker: str, bar: int) -> Market:
    """`market` without `ticker`'s bar on `bar` (a halt, or a bar the vendor lost)."""
    keep = ~((pl.col("ticker") == ticker) & (pl.col("date") == bar_date(bar)))
    return Market(bars=market.bars.filter(keep), securities=market.securities, meta=market.meta)


# Cash timing: entries at open(d) are capped by the cash at close d - 1 (spec 0007 decision 4).


def test_an_exit_at_todays_close_does_not_fund_todays_entry() -> None:
    # The review's repro. Two slots: AAA takes 50 at 6.006 and triples; BBB enters at open(7),
    # the bar AAA's `time` 4 exit fills at the close. Only the 50 left at close(6) is spendable,
    # so BBB gets 50, as it does with `time` 50 (no exit that day), not the ~100 equity / 2.
    aaa = FrameSpec(1, [4.0, 4.0, 6.0, 6.0] + [18.0] * 6)
    bbb = FrameSpec(1, [4.0] * 5 + [6.0] * 5)
    market = make_market({"AAA": aaa, "BBB": bbb})
    result = _run(market, [{"type": "time", "bars": 4}], max_positions=2)
    held = _run(market, TIME_50, max_positions=2)

    shares = 50 / (6 * (1 + SLIP))
    aaa_trade, bbb_trade = result.trades
    assert (aaa_trade.ticker, aaa_trade.exit_date) == ("AAA", bar_date(7))
    assert (bbb_trade.ticker, bbb_trade.entry_date) == ("BBB", bar_date(7))
    by_date = {p.date: p.value for p in result.equity}
    assert by_date[bar_date(7)] == pytest.approx(shares * 18 * (1 - SLIP) + shares * 6, abs=1e-9)
    by_date_held = {p.date: p.value for p in held.equity}
    assert by_date_held[bar_date(7)] == pytest.approx(shares * 18 + shares * 6, abs=1e-9)


def test_an_entry_stopped_out_on_its_own_bar_does_not_fund_the_next_entry() -> None:
    # Three slots. AAA takes 100 / 3 at 6.006 and triples, so equity / 3 at close(6) is about
    # 55.5 and cash 66.67. BBB and CCC enter at open(7); BBB stops out intraday on that bar,
    # and CCC still gets only what BBB left of the close(6) cash.
    aaa = FrameSpec(1, [4.0, 4.0, 6.0, 6.0] + [18.0] * 6)
    bbb_close = [4.0] * 5 + [6.0] * 5
    bbb_low = [*bbb_close[:6], 5.0, *bbb_close[7:]]
    bbb = FrameSpec(1, bbb_close, low=bbb_low)
    ccc = FrameSpec(1, [4.0] * 5 + [6.0] * 5)
    market = make_market({"AAA": aaa, "BBB": bbb, "CCC": ccc})
    exits = [{"type": "stop_pct", "pct": 8}, {"type": "time", "bars": 50}]
    result = _run(market, exits, max_positions=3)

    fill = 6 * (1 + SLIP)
    aaa_shares = 100 / 3 / fill
    cash = 100 - 100 / 3
    slot = (cash + aaa_shares * 18) / 3
    stop = fill * (1 - 0.08)
    ccc_notional = cash - slot
    assert [(t.ticker, t.exit_reason) for t in result.trades if t.ticker != "AAA"] == [
        ("BBB", "stop_pct"),
        ("CCC", "end_of_test"),
    ]
    expected = aaa_shares * 18 + slot / fill * stop * (1 - SLIP) + ccc_notional / fill * 6
    by_date = {p.date: p.value for p in result.equity}
    assert by_date[bar_date(7)] == pytest.approx(expected, abs=1e-9)


# Missing bars: the loop aligns on session dates and never reads a bar after the session.


def test_a_missing_bar_is_not_stepped_and_the_position_keeps_its_last_close() -> None:
    # The review's repro: AAA enters on 2020-01-07 (bar 4) and its 2020-01-09 bar (6) is gone.
    closes = [4.0, 4.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0]
    market = _drop(make_market({"AAA": FrameSpec(1, closes)}), "AAA", 6)
    result = _run(market, TIME_50, max_positions=1)

    (trade,) = result.trades
    assert trade.entry_date == bar_date(4)
    assert (trade.exit_date, trade.exit_reason) == (bar_date(10), "end_of_test")
    assert trade.bars_held == 6  # the ticker's own bars: 7 sessions, one without a bar
    shares = 100 / (7 * (1 + SLIP))
    by_date = {p.date: p.value for p in result.equity}
    assert by_date[bar_date(6)] == pytest.approx(shares * 8, abs=1e-9)  # the 01-08 close
    assert by_date[bar_date(7)] == pytest.approx(shares * 10, abs=1e-9)
    assert by_date[bar_date(9)] == pytest.approx(shares * 12, abs=1e-9)
    assert result.equity[-1].value == pytest.approx(shares * 13 * (1 - SLIP), abs=1e-9)


def test_a_signal_whose_ticker_has_no_bar_next_session_is_dropped_and_frees_the_slot() -> None:
    # AAA and BBB signal on bar 5 with one slot; AAA (first by ticker) has no bar 6, so it
    # cannot be bought at open(6). Its signal is dropped, never queued, and BBB takes the slot.
    market = _drop(make_market({"AAA": _edge_on(5), "BBB": _edge_on(5)}), "AAA", 6)
    result = _run(market, TIME_50, max_positions=1)
    assert [(t.ticker, t.entry_date) for t in result.trades] == [("BBB", bar_date(6))]


def test_a_bar_off_the_benchmark_calendar_is_stepped_before_the_next_session() -> None:
    # The benchmark lacks 2020-01-09 (bar 6) but AAA traded and gapped through its stop then;
    # the stop fills on that bar, during the next session's step, never later.
    market = make_market({"AAA": FrameSpec(1, [4.0, 4.0, 6.0, 6.0, 6.0, 3.0, 3.0, 3.0])})
    market = _drop(market, market.meta.benchmark, 6)
    result = _run(market, [{"type": "stop_pct", "pct": 8}], max_positions=1)
    (trade,) = result.trades
    assert (trade.exit_date, trade.exit_reason) == (bar_date(6), "stop_pct")
    assert trade.exit_price == pytest.approx(3.0 * (1 - SLIP))
    assert bar_date(6) not in {p.date for p in result.equity}


def test_bars_after_the_benchmarks_last_session_are_never_read() -> None:
    # The benchmark ends a bar before AAA: the open position exits at the last session.
    market = make_market({"AAA": _edge_on(3, 8)})
    market = _drop(market, market.meta.benchmark, 8)
    (trade,) = _run(market, TIME_50).trades
    assert (trade.exit_date, trade.exit_reason) == (bar_date(7), "end_of_test")


def test_bars_that_stop_early_without_delisted_on_exit_end_of_test_on_the_last_bar() -> None:
    # Spec 0007: `is_final` is the window's last session or the ticker's last bar in the cut
    # market, and `delisted` needs a real `delisted_on`. So data that just stops, mid window,
    # exits `end_of_test` on its last bar (the fixture loader sets `delisted_on`; live data
    # without it would read this way).
    dated = make_market({"AAA": _edge_on(3, 7), "BBB": FrameSpec(1, [4.0] * 12)})
    undated = dated.securities.with_columns(pl.lit(None, dtype=pl.Date).alias("delisted_on"))
    market = Market(bars=dated.bars, securities=undated, meta=dated.meta)
    (trade,) = _run(market, TIME_50).trades
    assert (trade.exit_date, trade.exit_reason) == (bar_date(7), "end_of_test")
    (listed,) = _run(dated, TIME_50).trades
    assert (listed.exit_date, listed.exit_reason) == (bar_date(7), "delisted")


# The IS to OOS hand off and truncation, end to end.


def test_oos_starts_from_the_last_is_close_and_carries_the_is_peak() -> None:
    # 20 sessions, OOS from index 14 (bar 15). All in AAA from bar 3: IS peaks at 15, ends at
    # 12; OOS climbs to 13 and ends at 11 (sold at the last close, less slippage).
    closes = [4.0, 6.0, 6.0, 8.0, 10.0, 12.0, 15.0, 15.0, 15.0, 15.0, 15.0, 14.0, 13.0, 12.0]
    closes += [12.0, 13.0, 11.0, 11.0, 11.0, 11.0]
    result = _run(make_market({"AAA": FrameSpec(1, closes)}), TIME_50, max_positions=1)
    assert result.oos_start == bar_date(15)

    shares = 100 / (6 * (1 + SLIP))
    last = shares * 11 * (1 - SLIP)
    oos = result.metrics.oos
    assert oos.max_dd_pct == pytest.approx((last / (shares * 15) - 1) * 100, abs=1e-9)
    assert oos.cagr_pct == pytest.approx(((last / (shares * 12)) ** (252 / 6) - 1) * 100)


def test_truncation_keeps_the_latest_2000_trades_and_metrics_use_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 40 tickers, one rising edge every 12 bars each, phases spread over the cycle; `time` 1
    # exits at the entry bar's close, so every slot is free again the next morning.
    n_bars, tickers = 700, {}
    for k in range(40):
        closes = [6.0 if (t + k) % 12 < 6 else 4.0 for t in range(n_bars)]
        tickers[f"T{k:02d}"] = FrameSpec(1, closes)
    made: list[Trade] = []

    def record(*args: Any) -> Trade:
        made.append(trade := make_trade(*args))
        return trade

    monkeypatch.setattr(api, "make_trade", record)
    result = _run(make_market(tickers), [{"type": "time", "bars": 1}], max_positions=20)

    total = len(made)
    every = sorted(made, key=lambda t: (t.entry_date, t.ticker))
    assert total > 2000
    assert (result.trades_total, result.trades_truncated) == (total, True)
    assert result.trades == every[-2000:]
    assert result.metrics.is_.n_trades + result.metrics.oos.n_trades == total
    oos = [t for t in every if t.segment == "oos"]
    assert result.metrics.oos.expectancy_pct == pytest.approx(
        sum(t.return_pct for t in oos) / len(oos)
    )
    assert [w.code for w in result.warnings] == ["trades_truncated"]
    assert result.warnings[0].message == (
        f"Showing the latest 2,000 of {total:,} trades; metrics use all of them."
    )
