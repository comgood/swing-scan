"""Metrics: pure functions over trades and the daily equity curve (spec 0007), and the exit
lab's per trade metrics (spec 0009)."""

from .curve import CurveStats, curve_stats, exposure_pct, thin
from .trade_mode import (
    best_is,
    distinct_weeks,
    edge,
    even_spread,
    guides_is,
    over_horizon_limit,
    trade_metrics,
)
from .trades import TradeStats, trade_stats

__all__ = [
    "CurveStats",
    "TradeStats",
    "best_is",
    "curve_stats",
    "distinct_weeks",
    "edge",
    "even_spread",
    "exposure_pct",
    "guides_is",
    "over_horizon_limit",
    "thin",
    "trade_metrics",
    "trade_stats",
]
