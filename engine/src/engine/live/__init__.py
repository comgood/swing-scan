"""Live research data, local only (DI lane, scope feature 14, spec 0010).

`python -m engine.live --universe research/sp500.csv --out data/live` (what `make load-live`
runs) fetches Alpaca daily bars and writes the same files as the synthetic market. The feed
defaults to `iex`, the only historical feed the free Basic plan serves.
"""

from .alpaca import (
    DEFAULT_FEED,
    FEED_ENV,
    FEEDS,
    VOLUME_CAVEAT,
    LiveLoadError,
    Transport,
    fetch_bars,
    keys_from_env,
    resolve_feed,
    urllib_transport,
    vendor_error,
)
from .market import BENCHMARK, LIVE_START, LoadSummary, build_market, read_universe

__all__ = [
    "BENCHMARK",
    "DEFAULT_FEED",
    "FEEDS",
    "FEED_ENV",
    "LIVE_START",
    "VOLUME_CAVEAT",
    "LiveLoadError",
    "LoadSummary",
    "Transport",
    "build_market",
    "fetch_bars",
    "keys_from_env",
    "read_universe",
    "resolve_feed",
    "urllib_transport",
    "vendor_error",
]
