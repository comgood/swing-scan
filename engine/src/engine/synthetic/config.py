"""Every number the synthetic market model uses (spec 0006). Change one, bump the version."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

GENERATOR_VERSION = "synthetic-1"
"""Written to `meta.data_version`. Bump it on any change to the model or its defaults."""

BENCHMARK = "DEMO-INDEX"
DEFAULT_SEED = 42


@dataclass(frozen=True)
class Regime:
    name: str
    drift: float
    """Mean daily log return of the market factor."""
    vol: float
    """Daily standard deviation of the market factor."""


BULL = Regime("bull", 0.0006, 0.009)
CHOP = Regime("chop", 0.0, 0.011)
BEAR = Regime("bear", -0.0015, 0.019)
RECOVERY = Regime("recovery", 0.0010, 0.014)
REGIMES = (BULL, CHOP, BEAR, RECOVERY)

SECTORS = (
    "Technology",
    "Healthcare",
    "Financials",
    "Energy",
    "Industrials",
    "Consumer",
    "Materials",
    "Utilities",
    "Telecom",
    "Real Estate",
)

NAME_SUFFIXES = (
    "Labs",
    "Holdings",
    "Systems",
    "Group",
    "Industries",
    "Works",
    "Partners",
    "Dynamics",
    "Networks",
    "Corp",
)


@dataclass(frozen=True)
class SyntheticConfig:
    """The model's knobs. The defaults are the published demo market (spec 0006)."""

    n_tickers: int = 500
    n_sessions: int = 1260
    start: date = date(2021, 1, 4)
    """A Monday. Every weekday after it is a session; there are no holidays."""

    listing_fraction: float = 0.05
    delisting_fraction: float = 0.05
    min_delisted: int = 20

    bear_start_range: tuple[float, float] = (0.24, 0.55)
    """Where the planted bear segment may start, as fractions of `n_sessions`."""
    bear_length_range: tuple[float, float] = (0.095, 0.143)
    bear_log_return_range: tuple[float, float] = (-0.45, -0.30)
    """Total market log return over the planted bear. -0.30 means at least a 25.9% fall."""
    regime_run_range: tuple[int, int] = (40, 160)
    """Length in sessions of each non bear regime run."""

    sector_vol: float = 0.007
    beta_range: tuple[float, float] = (0.6, 1.6)
    idio_vol_range: tuple[float, float] = (0.010, 0.030)
    t_degrees_of_freedom: float = 4.0

    momentum_coef: float = 0.10
    momentum_lookback: int = 63
    momentum_clip: float = 0.5

    start_price_median: float = 40.0
    start_price_range: tuple[float, float] = (2.0, 400.0)
    index_start_level: float = 1000.0
    price_floor: float = 0.05
    price_decimals: int = 4

    volume_median: float = 1_000_000.0
    index_volume_median: float = 500_000_000.0

    bankruptcy_share: float = 0.6
    bankruptcy_slide_sessions: int = 40
    bankruptcy_slide_drift: float = -0.006
    acquisition_lead_sessions: int = 20
    acquisition_premium_range: tuple[float, float] = (0.25, 0.40)

    def __post_init__(self) -> None:
        problems: list[str] = []
        if self.n_tickers < 1:
            problems.append("n_tickers must be at least 1")
        if self.n_sessions < 300:
            problems.append("n_sessions must be at least 300")
        if self.start.weekday() >= 5:
            problems.append("start must be a weekday")
        if self.n_listed + self.n_delisted > self.n_tickers:
            problems.append("listings plus delistings exceed n_tickers")
        low, high = self.bear_log_return_range
        if not low <= high < 0:
            problems.append("bear_log_return_range must be negative and ordered")
        if problems:
            raise ValueError("bad SyntheticConfig: " + "; ".join(problems))

    @property
    def n_listed(self) -> int:
        return round(self.listing_fraction * self.n_tickers)

    @property
    def n_delisted(self) -> int:
        return max(self.min_delisted, round(self.delisting_fraction * self.n_tickers))
