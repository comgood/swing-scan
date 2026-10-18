"""The one `Market` the routes serve: loaded and warmed at import (spec 0005, AC-7, AC-8),
and reloaded when the store's dataset changes (spec 0011, AC-7 to AC-14)."""

from __future__ import annotations

import logging
import os
import sys
import time

from engine import api as use_cases
from engine.contracts import Market
from engine.data import change_key, market_uri, read_market, read_meta

from .settings import LOOPBACK, live_mode_problems

logger = logging.getLogger("api.state")

STORE_CHECK_FLOOR_SECONDS = 10.0
"""No request checks the store for a change more often than this (spec 0011)."""


def _read_and_warm() -> Market:
    """Read the dataset at `market_uri()`, refuse live data off this machine, and warm it.

    `FileNotFoundError` means no dataset is there yet, which callers may tolerate. Every
    other failure raises, so a broken dataset never serves.

    D-5 is enforced on the dataset, not on `DATA_MODE`: a live dataset refuses to load
    anywhere but your own machine, however the process was started. `DATA_MODE=live` alone
    cannot serve real prices, and forgetting it cannot serve them either.
    """
    market = read_market()
    if market.meta.data_mode == "live" and (problems := live_mode_problems(sys.argv, os.environ)):
        raise RuntimeError(
            f"the dataset in {market_uri()} is live data, which runs only on your machine "
            f"with the API bound to {LOOPBACK} (D-5); refusing to start: {'; '.join(problems)}."
        )
    use_cases.warm(market)
    return market


def load_market() -> Market | None:
    """The dataset at `market_uri()`, or None when no dataset is there yet.

    Only a missing dataset is tolerated (the routes then answer 501, and the change check
    keeps looking). A dataset that exists but fails its checks raises, so a broken store
    never serves wrong numbers. A loaded market has every template column computed and
    pinned, so template scans start warm.
    """
    try:
        return _read_and_warm()
    except FileNotFoundError:
        logger.warning("no market in %s; /scan answers 501 until one is generated", market_uri())
        return None


market: Market | None = load_market()
"""Null while no dataset is present (run `make data` locally). Always reached as
`state.market`: a reload rebinds this attribute, so an imported name would pin the old
dataset forever."""

_change_key: str | None = change_key(market.meta) if market is not None else None
_checked_at: float = time.monotonic()


def refresh_if_changed() -> None:
    """The store change check, run once per request by the middleware in `main.py`.

    At most one check every `STORE_CHECK_FLOOR_SECONDS` on monotonic time, so a clock
    change cannot stall it. A check re-reads `meta.parquet` and compares its contents to
    the loaded dataset's; only a difference reloads, and the request that noticed the
    change waits for the reload, then serves the new dataset. The read is blocking, which
    is what serializes it: the event loop is held, so two requests arriving together cannot
    both reload. It also runs while nothing is loaded, so a dataset that appears later is
    picked up without a restart. A reload that fails leaves the loaded market serving and
    is retried at the next check.
    """
    global market, _change_key, _checked_at
    now = time.monotonic()
    if now - _checked_at < STORE_CHECK_FLOOR_SECONDS:
        return
    _checked_at = now
    try:
        key = read_meta()[1]
    except FileNotFoundError:
        return  # nothing in the store yet; the next check looks again
    except Exception:
        logger.exception("market change check failed; retrying at the next check")
        return
    if key == _change_key:
        return
    try:
        reloaded = _read_and_warm()
    except Exception:
        logger.exception("market reload failed; the loaded dataset keeps serving, will retry")
        return
    market, _change_key = reloaded, change_key(reloaded.meta)
    logger.info("market reloaded from %s, data through %s", market_uri(), reloaded.meta.end)
