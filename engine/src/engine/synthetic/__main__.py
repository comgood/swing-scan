"""`python -m engine.synthetic --seed 42 --out DIR`: write the synthetic dataset (spec 0001)."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import polars as pl

from engine.data import write_market

from .config import DEFAULT_SEED
from .generator import generate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m engine.synthetic", description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="generator seed (42)")
    parser.add_argument("--out", required=True, help="directory to write the dataset into")
    args = parser.parse_args(argv)

    market = generate(args.seed)
    out = write_market(market, args.out)
    n_delisted = market.securities.filter(pl.col("delisted_on").is_not_null()).height
    print(
        f"wrote {market.bars.height} bars for {market.meta.n_tickers} tickers plus "
        f"{market.meta.benchmark} ({market.meta.start} to {market.meta.end}, "
        f"{n_delisted} delisted, seed {args.seed}) to {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
