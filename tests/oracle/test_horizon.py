"""Horizon oracle X-9 (doc 01 section 6.8, doc 02 sections 7.2 and 7.4).

In trade mode a trade still open after `horizon_bars` (60) exits at the close of bar 60,
counting the entry bar as bar 1, with reason `horizon`. A config with more than 10% of its
trades exited by horizon gets the `horizon_exits_over_10pct` warning.
"""

from __future__ import annotations

import pytest

from engine.contracts import Market

from ._oracle import SLIP_OUT, FrameSpec, bar_date, close_above, config, lab, make_market

# Bars 1 and 2 close at 9, bar 3 at 10 (the signal), then +1% a bar. Lows sit 0.5% under the
# close, so a 10% trailing stop (under the prior high) is never touched.
CLOSES = [9.0, 9.0] + [10 * 1.01 ** (k - 3) for k in range(3, 91)]


def _market() -> Market:
    return make_market(
        {
            "HZN": FrameSpec(
                start_bar=1,
                close=CLOSES,
                open=[c * 0.998 for c in CLOSES],
                high=CLOSES,
                low=[c * 0.995 for c in CLOSES],
            )
        }
    )


def test_x9_trailing_trade_exits_by_horizon_at_close_of_bar_60() -> None:
    configs = [
        config("trail", {"type": "trail_pct", "pct": 10}),
        config("time 5", {"type": "time", "bars": 5}),
    ]
    result = lab(close_above(9.5), configs, _market())

    assert result.assumptions.horizon_bars == 60
    trade = result.baseline_trades[0]  # configs[0], the trailing stop
    assert trade.entry_date == bar_date(4)
    assert trade.exit_date == bar_date(63)  # entry bar 4 is bar 1, so bar 60 is bar 63
    assert trade.exit_price == pytest.approx(CLOSES[63 - 1] * SLIP_OUT, abs=1e-9)
    assert trade.exit_reason == "horizon"
    assert trade.bars_held == 60


def test_x9_horizon_share_over_10pct_warns_only_that_config() -> None:
    configs = [
        config("trail", {"type": "trail_pct", "pct": 10}),
        config("time 5", {"type": "time", "bars": 5}),
    ]
    result = lab(close_above(9.5), configs, _market())

    trail, time5 = result.rows
    horizon_pct = [
        split.horizon_exit_pct
        for split in (trail.strategy.is_, trail.strategy.oos)
        if split.n_trades
    ]
    assert horizon_pct == [100.0]
    assert all(
        split.horizon_exit_pct in (None, 0.0) for split in (time5.strategy.is_, time5.strategy.oos)
    )
    warned = {w.config_index for w in result.warnings if w.code == "horizon_exits_over_10pct"}
    assert warned == {0}
