"""Curve metrics of one segment of a daily equity curve (spec 0007, Metric formulas).

252 sessions a year, risk free rate 0, unrounded. OOS runs on the OOS part of the same
continuous curve: its start value is the last IS close and its drawdown peak carries over
from IS.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean, stdev

SESSIONS_PER_YEAR = 252


@dataclass(frozen=True)
class CurveStats:
    cagr_pct: float | None
    max_dd_pct: float | None
    sharpe: float | None


def curve_stats(closes: Sequence[float], start: float, peak: float) -> CurveStats:
    """`closes` are the segment's daily closes; `start` is the close before its first session
    (the start equity for IS); `peak` is the running max before the segment (at least `start`).
    """
    s = len(closes)
    if s < 2:
        return CurveStats(cagr_pct=None, max_dd_pct=None, sharpe=None)
    cagr = ((closes[-1] / start) ** (SESSIONS_PER_YEAR / s) - 1) * 100
    worst = 0.0
    for value in closes:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    previous = [start, *closes[:-1]]
    returns = [value / before - 1 for value, before in zip(closes, previous, strict=True)]
    spread = stdev(returns)
    sharpe = fmean(returns) / spread * math.sqrt(SESSIONS_PER_YEAR) if spread > 0 else None
    return CurveStats(cagr_pct=cagr, max_dd_pct=worst * 100, sharpe=sharpe)


def exposure_pct(invested: Sequence[float]) -> float | None:
    """Mean share of equity held in positions at each close, in %; null with no sessions."""
    return fmean(invested) * 100 if invested else None


def thin(n: int, limit: int = 500) -> list[int]:
    """Indexes 0, k, 2k, … plus the last, k = ceil(n / limit). Adding the last can make
    `limit` + 1 points; then the step point just before the last is dropped, so the curve
    still starts at the first session (from 100) and ends at the last."""
    if n == 0:
        return []
    k = math.ceil(n / limit)
    picked = list(range(0, n, k))
    if picked[-1] != n - 1:
        picked.append(n - 1)
    if len(picked) > limit:
        del picked[-2]
    return picked
