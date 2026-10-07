"""The one `Market` the routes serve, loaded and warmed once at import (spec 0005, AC-7, AC-8)."""

from __future__ import annotations

import logging

from engine import api as use_cases
from engine.contracts import Market
from engine.data import market_dir, read_market

logger = logging.getLogger("api.state")


def load_market() -> Market | None:
    """The dataset in `SYNTHETIC_DATA_DIR`, or None when none has been generated yet.

    Only a missing dataset is tolerated (the routes then answer 501). A dataset that exists
    but fails its checks raises, so a broken image never serves wrong numbers. A loaded
    market has every template column computed and pinned, so template scans start warm.
    """
    try:
        market = read_market()
    except FileNotFoundError:
        logger.warning("no market in %s; /scan answers 501 until one is generated", market_dir())
        return None
    use_cases.warm(market)
    return market


market: Market | None = load_market()
"""Null while no dataset is present (run `make data` locally)."""
