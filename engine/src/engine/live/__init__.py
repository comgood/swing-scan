"""Live research data, local only (DI lane, scope feature 14, spec 0010).

`python -m engine.live --universe research/sp500.csv --out data/live` (what `make load-live`
runs) fetches Alpaca free daily bars and writes the same files as the synthetic market.
"""

from .alpaca import LiveLoadError, Transport, fetch_bars, keys_from_env, urllib_transport
from .market import BENCHMARK, LIVE_START, LoadSummary, build_market, read_universe

__all__ = [
    "BENCHMARK",
    "LIVE_START",
    "LiveLoadError",
    "LoadSummary",
    "Transport",
    "build_market",
    "fetch_bars",
    "keys_from_env",
    "read_universe",
    "urllib_transport",
]
