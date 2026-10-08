"""Trade mode metrics for the exit lab (spec 0002 *Metric definitions*, spec 0009). Pure,
unrounded. No CAGR, max drawdown or Sharpe exists here (X-8).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from statistics import fmean

import numpy as np

from engine.contracts import BestIs, EdgeMetrics, Guides, Trade, TradeMetrics

from .trades import trade_stats

HORIZON_WARN_PCT = 10.0
"""A config warns when more than this share of its strategy trades exit by `horizon` (X-9)."""

HIGHER_IS_BETTER = (
    "win_rate_pct",
    "avg_win_pct",
    "avg_loss_pct",  # ≤ 0, so higher is closer to 0
    "expectancy_pct",
    "expectancy_r",
    "expectancy_per_bar_pct",
    "profit_factor",
    "avg_mae_pct",  # ≤ 0, so higher is closer to 0
    "avg_mfe_pct",
)
LOWER_IS_BETTER = ("horizon_exit_pct",)


def distinct_weeks(days: Sequence[date]) -> int:
    """Distinct ISO (year, week) pairs over the dates."""
    return len({day.isocalendar()[:2] for day in days})


def horizon_exit_pct(trades: Sequence[Trade]) -> float | None:
    if not trades:
        return None
    return sum(t.exit_reason == "horizon" for t in trades) / len(trades) * 100


def trade_metrics(trades: Sequence[Trade]) -> TradeMetrics:
    """Every `TradeMetrics` field over one segment's trades; null with no trades, except
    `n_trades` and `distinct_weeks`, which are 0."""
    stats = trade_stats(trades)
    bars = sum(t.bars_held for t in trades)
    return TradeMetrics(
        n_trades=stats.n_trades,
        distinct_weeks=distinct_weeks([t.entry_date for t in trades]),
        win_rate_pct=stats.win_rate_pct,
        avg_win_pct=stats.avg_win_pct,
        avg_loss_pct=stats.avg_loss_pct,
        expectancy_pct=stats.expectancy_pct,
        expectancy_r=stats.expectancy_r,
        expectancy_per_bar_pct=sum(t.return_pct for t in trades) / bars if bars else None,
        profit_factor=stats.profit_factor,
        avg_bars_held=stats.avg_bars_held,
        avg_mae_pct=fmean(t.mae_pct for t in trades) if trades else None,
        avg_mfe_pct=fmean(t.mfe_pct for t in trades) if trades else None,
        horizon_exit_pct=horizon_exit_pct(trades),
    )


def _minus(a: float | None, b: float | None) -> float | None:
    return a - b if a is not None and b is not None else None


def edge(strategy: TradeMetrics, random: TradeMetrics) -> EdgeMetrics:
    """Strategy minus random for the four edge metrics; null when either side is null."""
    return EdgeMetrics(
        expectancy_pct=_minus(strategy.expectancy_pct, random.expectancy_pct),
        expectancy_r=_minus(strategy.expectancy_r, random.expectancy_r),
        expectancy_per_bar_pct=_minus(
            strategy.expectancy_per_bar_pct, random.expectancy_per_bar_pct
        ),
        win_rate_pct=_minus(strategy.win_rate_pct, random.win_rate_pct),
    )


def _best(values: Sequence[float | None], higher: bool) -> int | None:
    """Index of the best non null value; ties go to the lowest index."""
    best: int | None = None
    for i, value in enumerate(values):
        if value is None:
            continue
        current = values[best] if best is not None else None
        if current is None or (value > current if higher else value < current):
            best = i
    return best


def best_is(strategy_is: Sequence[TradeMetrics]) -> BestIs:
    """Per ranked metric, the config whose strategy IS value is best (X-3). Only IS metrics
    come in, so OOS, random and edge values can never be ranked."""
    ranked = {
        name: _best([getattr(m, name) for m in strategy_is], name in HIGHER_IS_BETTER)
        for name in (*HIGHER_IS_BETTER, *LOWER_IS_BETTER)
    }
    return BestIs(**ranked)


def guides_is(baseline_is: Sequence[Trade]) -> Guides:
    """Winner MAE p75 and p90 and the median MFE, from the baseline config's IS trades (X-5).
    The caller passes IS trades only; anything else is rejected."""
    if any(t.segment != "is" for t in baseline_is):
        raise ValueError("guides_is takes IS trades only")
    winners = [t.mae_pct for t in baseline_is if t.return_pct > 0]
    mfe = [t.mfe_pct for t in baseline_is]
    return Guides(
        winner_mae_p75_pct=float(np.percentile(winners, 75)) if winners else None,
        winner_mae_p90_pct=float(np.percentile(winners, 90)) if winners else None,
        mfe_median_pct=float(np.median(mfe)) if mfe else None,
    )


def over_horizon_limit(trades: Sequence[Trade]) -> bool:
    """More than 10% of the trades (IS and OOS together) exit by `horizon` (spec 0009 #5)."""
    share = horizon_exit_pct(trades)
    return share is not None and share > HORIZON_WARN_PCT


def even_spread[T](items: Sequence[T], limit: int) -> list[T]:
    """At most `limit` items spread evenly through the order: indices
    `round(i × (total - 1) / (limit - 1))`, halves rounded up (spec 0002)."""
    total = len(items)
    if total <= limit:
        return list(items)
    span, gaps = total - 1, limit - 1
    # Round half up in exact integers: floor((2 × i × span + gaps) / (2 × gaps)).
    return [items[(2 * i * span + gaps) // (2 * gaps)] for i in range(limit)]
