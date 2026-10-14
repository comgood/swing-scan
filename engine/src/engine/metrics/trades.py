"""Trade metrics of one segment (spec 0007, Metric formulas). Pure, unrounded.

A trade with `return_pct > 0` is a win; `return_pct <= 0` is a loss.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean

from engine.contracts import Trade


@dataclass(frozen=True)
class TradeStats:
    n_trades: int
    win_rate_pct: float | None
    avg_win_pct: float | None
    avg_loss_pct: float | None
    expectancy_pct: float | None
    expectancy_r: float | None
    """Mean `r_multiple` over the trades that have one. A trade without R (a `stop_atr` entry
    during ATR warm up sets no stop) is left out of R only; every other metric counts it.
    Null when no trade has R: a config without a stop, or no trades (owner ruling 2026-10-09)."""
    profit_factor: float | None
    avg_bars_held: float | None


def _mean(values: Sequence[float]) -> float | None:
    return fmean(values) if values else None


def trade_stats(trades: Sequence[Trade]) -> TradeStats:
    """Win rate, averages, expectancy in % and R, profit factor and bars held."""
    returns = [t.return_pct for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    r_multiples = [t.r_multiple for t in trades if t.r_multiple is not None]
    loss_sum = abs(sum(losses))
    return TradeStats(
        n_trades=len(trades),
        win_rate_pct=len(wins) / len(trades) * 100 if trades else None,
        avg_win_pct=_mean(wins),
        avg_loss_pct=_mean(losses),
        expectancy_pct=_mean(returns),
        expectancy_r=_mean(r_multiples),
        profit_factor=sum(wins) / loss_sum if trades and loss_sum > 0 else None,
        avg_bars_held=_mean([float(t.bars_held) for t in trades]),
    )
