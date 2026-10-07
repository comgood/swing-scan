"""MAE and MFE oracle B-9 (doc 01 section 6.4, doc 02 section 7.2, spec 0002 value sourcing).

Four trades from `fixtures/b09_mae_mfe.csv`: a gap stop, an intraday stop, an intraday target
and a time exit. MAE is the min low and MFE the max high from the entry bar through the exit
bar, measured from the entry fill, with the exit bar limited to what was knowable before the
fill. In R, the move is divided by R = fill - initial stop.
"""

from __future__ import annotations

import pytest

from ._oracle import SLIP_IN, SLIP_OUT, close_above, fixture, only_trade, portfolio

EXITS = [
    {"type": "stop_pct", "pct": 8},
    {"type": "target", "pct": 15},
    {"type": "time", "bars": 3},
]
FILL = 10 * SLIP_IN
STOP = FILL * 0.92
TARGET = FILL * 1.15
R = FILL - STOP


def pct(price: float) -> float:
    return (price / FILL - 1) * 100


def in_r(price: float) -> float:
    return (price - FILL) / R


@pytest.mark.parametrize(
    ("ticker", "reason", "exit_price", "mae_price", "mfe_price"),
    [
        # Gap stop: the exit bar contributes only its open (9.0); its low 8.7 is ignored.
        ("MG", "stop_pct", 9.0 * SLIP_OUT, min(9.8, 9.0), max(10.4, 9.0)),
        # Intraday stop: exit bar MAE at the stop, MFE at the open; its high 10.6 is ignored.
        ("MS", "stop_pct", STOP * SLIP_OUT, min(9.9, STOP), max(10.3, 9.7)),
        # Intraday target: exit bar MFE at the target, MAE at the open; its low 9.5 is ignored.
        ("MT", "target", TARGET * SLIP_OUT, min(9.95, 10.8), max(10.5, TARGET)),
        # Time exit at close(6): the full bars 4 to 6 count.
        ("MM", "time", 10.3 * SLIP_OUT, min(9.7, 9.6, 9.4), max(10.2, 10.9, 10.6)),
    ],
)
def test_b9_mae_and_mfe_with_the_exit_bar_capped(
    ticker: str, reason: str, exit_price: float, mae_price: float, mfe_price: float
) -> None:
    result = portfolio(close_above(9.5), EXITS, fixture("b09_mae_mfe"))

    trade = only_trade(result.trades, ticker)
    assert trade.exit_reason == reason
    assert trade.exit_price == pytest.approx(exit_price, abs=1e-9)
    assert trade.mae_pct == pytest.approx(pct(mae_price), abs=1e-9)
    assert trade.mfe_pct == pytest.approx(pct(mfe_price), abs=1e-9)
    assert trade.mae_r == pytest.approx(in_r(mae_price), abs=1e-9)
    assert trade.mfe_r == pytest.approx(in_r(mfe_price), abs=1e-9)
    assert trade.r_multiple == pytest.approx(in_r(exit_price), abs=1e-9)
    assert trade.mae_pct <= 0 <= trade.mfe_pct
