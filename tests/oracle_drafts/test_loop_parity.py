"""Loop parity (doc 02 section 7.3): the portfolio day loop and the trade mode per trade loop
call the same exits through one `step()`, so a one trade fixture exits identically in both.
"""

from __future__ import annotations

from ._oracle import close_above, config, fixture, lab, portfolio

EXITS = [
    {"type": "stop_pct", "pct": 8},
    {"type": "target", "pct": 15},
    {"type": "time", "bars": 10},
]


def test_one_trade_exits_identically_in_both_loops() -> None:
    market = fixture("b01_stop_pct")

    single = portfolio(close_above(9.5), EXITS, market)
    exit_lab = lab(
        close_above(9.5),
        [config("same exits", *EXITS), config("other", {"type": "time", "bars": 2})],
        market,
    )

    assert len(single.trades) == 1
    assert len(exit_lab.baseline_trades) == 1  # configs[0], the same exits
    assert exit_lab.baseline_trades[0].model_dump() == single.trades[0].model_dump()
