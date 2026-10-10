"""CLI behind `make load-live`: fetch, check and write the live dataset (D-4, spec 0010)."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from pathlib import Path

from engine.contracts import MarketError
from engine.data import write_market

from .alpaca import (
    DEFAULT_FEED,
    FEED_ENV,
    FEEDS,
    LiveLoadError,
    Transport,
    fetch_bars,
    keys_from_env,
    resolve_feed,
    urllib_transport,
)
from .market import BENCHMARK, LIVE_START, build_market, read_universe


def main(
    argv: Sequence[str] | None = None,
    get: Transport = urllib_transport,
    env: Mapping[str, str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="python -m engine.live", description=__doc__)
    parser.add_argument("--universe", type=Path, default=Path("research/sp500.csv"))
    parser.add_argument("--out", type=Path, default=Path("data/live"))
    parser.add_argument("--start", type=date.fromisoformat, default=LIVE_START)
    parser.add_argument("--end", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    parser.add_argument(
        "--feed",
        default=None,
        help=(
            f"Alpaca data feed, one of {', '.join(FEEDS)} "
            f"(default {DEFAULT_FEED}, or ${FEED_ENV}); sip needs a paid plan"
        ),
    )
    args = parser.parse_args(argv)
    environ = os.environ if env is None else env
    try:
        feed = resolve_feed(args.feed, environ)
        headers = keys_from_env(environ)
        universe = read_universe(args.universe)
        symbols = [*universe["ticker"].to_list(), BENCHMARK]
        print(f"fetching {len(symbols)} symbols from {args.start} to {args.end} (feed {feed}) ...")
        raw = fetch_bars(symbols, args.start, args.end, headers, get, feed)
        market, summary = build_market(universe, raw, args.start, args.end, feed)
        write_market(market, args.out)
    except (LiveLoadError, MarketError, FileNotFoundError) as exc:
        print(f"load-live failed: {exc}", file=sys.stderr)
        return 1
    for line in summary.lines():
        print(line)
    print(f"wrote {args.out} (gitignored). Run it with: make dev-live")
    return 0


if __name__ == "__main__":
    sys.exit(main())
