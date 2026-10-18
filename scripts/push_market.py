"""`make push-market`: seed the market store from a local dataset directory (spec 0011).

Reads `<--from>/<mode>` locally, then writes the three objects under `<--to>/<mode>` in bars,
securities, meta order, meta last, so a reader that sees the new meta already has the new bars
behind it. Rerunnable: both reads and writes go through `engine.data`, whose output is byte for
byte reproducible, so a second run leaves the store in the same state.

A live dataset holds real vendor prices, so pushing one needs `--allow-live` on purpose.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from engine.data import read_market, write_market
from engine.data.store import dataset_key


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/push_market.py", description=__doc__)
    parser.add_argument("--mode", default="synthetic", choices=("synthetic", "live"))
    parser.add_argument("--from", dest="source", default="data", help="local dataset root (data)")
    parser.add_argument("--to", dest="dest", required=True, help="store root, e.g. s3://bucket")
    parser.add_argument("--allow-live", action="store_true", help="required to push a live dataset")
    args = parser.parse_args(argv)

    source = dataset_key(args.source, args.mode)
    market = read_market(source)
    if market.meta.data_mode == "live" and not args.allow_live:
        print(
            f"{source} is live data (real vendor prices). Pass --allow-live to push it.",
            file=sys.stderr,
        )
        return 1

    dest = dataset_key(args.dest, args.mode)
    write_market(market, dest)
    print(
        f"pushed {market.bars.height} bars for {market.meta.n_tickers} tickers "
        f"({market.meta.data_mode}, {market.meta.start} to {market.meta.end}) "
        f"from {source} to {dest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
