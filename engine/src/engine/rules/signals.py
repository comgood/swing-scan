"""The one entry signal function, shared by the scan and the backtest (doc 02 §6, S-3).

    edge(t)   = rule valid and true at t, and valid and false at t-1   (B-14)
    signal(t) = edge(t), not the ticker's last bar                     (B-15)
                and no ACCEPTED signal in t-cooldown … t-1             (B-16)

The cooldown is a chain: an edge dropped by the cooldown never starts its own cooldown. The
scan passes `ignore_last_bar=True`; the backtest keeps the last bar term.
"""

from __future__ import annotations

import numpy as np
import polars as pl

COOLDOWN = 10


def entry_signals(
    pos: pl.Series,
    is_last: pl.Series,
    valid: pl.Series,
    value: pl.Series,
    *,
    cooldown: int = COOLDOWN,
    ignore_last_bar: bool = False,
) -> pl.Series:
    """Accepted entry signals per bar, aligned to the inputs' row order.

    All four inputs are aligned to bars sorted by `(ticker, date)`: `pos` is the row's
    position within its ticker (0 on the first bar), `is_last` marks each ticker's last bar,
    and `valid` / `value` come from the compiled rule. Each ticker is walked from its first
    bar, so the cooldown chain depends on the whole history up to t and never on later bars.
    """
    pos_np = pos.to_numpy()
    valid_np = valid.to_numpy()
    value_np = value.to_numpy()
    prev_valid = np.concatenate(([False], valid_np[:-1]))
    prev_value = np.concatenate(([False], value_np[:-1]))
    edges = value_np & valid_np & (pos_np >= 1) & prev_valid & ~prev_value
    if not ignore_last_bar:
        edges &= ~is_last.to_numpy()

    accepted = np.zeros(len(pos_np), dtype=bool)
    last_accepted = -(10**12)
    for t in np.flatnonzero(edges).tolist():
        first_row = t - int(pos_np[t])
        if last_accepted >= first_row and t - last_accepted <= cooldown:
            continue
        accepted[t] = True
        last_accepted = t
    return pl.Series("signal", accepted, dtype=pl.Boolean)
