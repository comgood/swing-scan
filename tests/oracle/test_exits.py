"""Exit fill oracles B-1 to B-8 (doc 01 section 6.4, doc 02 sections 7.1 and 7.2).

Each test runs one config in portfolio mode on a hand checked CSV in `fixtures/`; the file's
comments carry the arithmetic. Every fill includes 10 bps slippage: entries x 1.001, exits
x 0.999. Bar 1 is Thu 2020-01-02 on a weekday only calendar.
"""

from __future__ import annotations

import pytest

from ._oracle import SLIP_IN, SLIP_OUT, bar_date, close_above, fixture, only_trade, portfolio

STOP_8 = {"type": "stop_pct", "pct": 8}


def test_b1_percent_stop_fills_at_the_stop() -> None:
    result = portfolio(close_above(9.5), [STOP_8], fixture("b01_stop_pct"))

    trade = only_trade(result.trades, "STP")
    fill = 10 * SLIP_IN
    stop = fill * (1 - 0.08)
    exit_fill = min(9.8, stop) * SLIP_OUT
    assert trade.entry_date == bar_date(4)
    assert trade.entry_price == pytest.approx(fill, abs=1e-9)
    assert trade.exit_date == bar_date(5)
    assert trade.exit_price == pytest.approx(exit_fill, abs=1e-9)
    assert trade.exit_price == pytest.approx(9.1999908, abs=1e-9)
    assert trade.exit_reason == "stop_pct"
    assert trade.bars_held == 2
    assert trade.return_pct == pytest.approx((exit_fill / fill - 1) * 100, abs=1e-9)


def test_b2_gap_through_the_stop_fills_at_the_open() -> None:
    result = portfolio(close_above(9.5), [STOP_8], fixture("b02_gap_stop"))

    trade = only_trade(result.trades, "GAP")
    fill = 10 * SLIP_IN
    assert fill * 0.92 > 9.0  # bar 5 opens below the stop
    assert trade.exit_date == bar_date(5)
    assert trade.exit_price == pytest.approx(9.0 * SLIP_OUT, abs=1e-9)
    assert trade.exit_reason == "stop_pct"
    assert trade.return_pct == pytest.approx((9.0 * SLIP_OUT / fill - 1) * 100, abs=1e-9)


def test_b3_atr_stop_is_fill_minus_k_times_atr_at_the_signal_bar() -> None:
    exits = [{"type": "stop_atr", "k": 2, "n": 14}]
    result = portfolio(close_above(10.5), exits, fixture("b03_stop_atr"))

    trade = only_trade(result.trades, "ATR")
    fill = 11 * SLIP_IN
    stop = fill - 2 * 2.0
    assert trade.entry_date == bar_date(21)
    assert trade.entry_price == pytest.approx(fill, abs=1e-9)
    assert trade.exit_date == bar_date(23)
    assert trade.exit_price == pytest.approx(stop * SLIP_OUT, abs=1e-9)
    assert trade.exit_reason == "stop_atr"
    assert trade.bars_held == 3


def test_b4_target_intraday_gap_and_stop_beats_target() -> None:
    exits = [STOP_8, {"type": "target", "pct": 15}]
    result = portfolio(close_above(9.5), exits, fixture("b04_target"))

    fill = 10 * SLIP_IN
    target = fill * 1.15
    stop = fill * 0.92

    intraday = only_trade(result.trades, "TGI")
    assert intraday.exit_date == bar_date(5)
    assert intraday.exit_price == pytest.approx(max(10.8, target) * SLIP_OUT, abs=1e-9)
    assert intraday.exit_reason == "target"

    gap = only_trade(result.trades, "TGG")
    assert gap.exit_price == pytest.approx(max(12.0, target) * SLIP_OUT, abs=1e-9)
    assert gap.exit_price == pytest.approx(12.0 * SLIP_OUT, abs=1e-9)
    assert gap.exit_reason == "target"

    both = only_trade(result.trades, "TGS")
    assert both.exit_date == bar_date(5)
    assert both.exit_price == pytest.approx(stop * SLIP_OUT, abs=1e-9)
    assert both.exit_reason == "stop_pct"


def test_b5_trailing_stop_only_rises_and_exits_at_10_8() -> None:
    result = portfolio(
        close_above(9.5), [{"type": "trail_pct", "pct": 10}], fixture("b05_trail_pct")
    )

    trade = only_trade(result.trades, "TRL")
    level = max(10, 12, 11) * (1 - 0.10)
    assert level == pytest.approx(10.8)
    assert trade.exit_date == bar_date(7)
    assert trade.exit_price == pytest.approx(level * SLIP_OUT, abs=1e-9)
    assert trade.exit_reason == "trail_pct"
    assert trade.bars_held == 4


def test_b6_close_below_sma_exits_at_the_next_open() -> None:
    exits = [{"type": "close_below_ma", "ma": "sma", "n": 21}]
    result = portfolio(close_above(10.5), exits, fixture("b06_close_below_ma"))

    trade = only_trade(result.trades, "SMA")
    sma_at_28 = (17 * 10 + 3 * 11 + 9) / 21
    assert sma_at_28 > 9  # close(28) is below its SMA(21), so the exit waits for open(29)
    assert trade.entry_date == bar_date(26)
    assert trade.exit_date == bar_date(29)
    assert trade.exit_price == pytest.approx(9.5 * SLIP_OUT, abs=1e-9)
    assert trade.exit_reason == "ma"
    assert trade.bars_held == 4


def test_b7_time_exit_at_the_close_of_bar_n() -> None:
    result = portfolio(close_above(9.5), [{"type": "time", "bars": 3}], fixture("b07_time"))

    trade = only_trade(result.trades, "TIM")
    assert trade.entry_date == bar_date(4)
    assert trade.exit_date == bar_date(6)  # entry bar 4 is bar 1, so bar N = 3 is bar 6
    assert trade.exit_price == pytest.approx(10.7 * SLIP_OUT, abs=1e-9)
    assert trade.exit_reason == "time"
    assert trade.bars_held == 3


def test_b8_delisting_exits_at_the_last_close() -> None:
    result = portfolio(close_above(9.5), [{"type": "time", "bars": 20}], fixture("b08_delisting"))

    assert [t.ticker for t in result.trades] == ["DLS"]  # KEEP never has a rising edge
    trade = result.trades[0]
    assert trade.exit_date == bar_date(8)
    assert trade.exit_price == pytest.approx(10.6 * SLIP_OUT, abs=1e-9)
    assert trade.exit_reason == "delisted"
    assert trade.bars_held == 5
