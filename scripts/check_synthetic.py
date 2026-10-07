"""`make data-check`: build the seed 42 synthetic dataset twice and prove D-1 to D-3 on it.

Writes both copies to temporary folders (never `data/`), then checks that every file has the
same SHA-256, the bars pass `check_market` (D-2), the benchmark falls at least 20% from its
running peak, and at least 20 tickers are delisted (D-3).
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

import polars as pl

from engine.data import read_market, write_market
from engine.synthetic import DEFAULT_SEED, generate

FILES = ("bars.parquet", "securities.parquet", "meta.json")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp) / "a", Path(tmp) / "b"
        write_market(generate(DEFAULT_SEED), a)
        write_market(generate(DEFAULT_SEED), b)
        for name in FILES:
            first, second = digest(a / name), digest(b / name)
            print(f"{name}: {first}")
            if first != second:
                problems.append(f"D-1: {name} differs between two builds ({second})")

        market = read_market(a)  # runs check_market (D-2)
        bench = market.bars.filter(pl.col("ticker") == market.meta.benchmark).sort("date")
        drawdown: float = bench.select(
            (pl.col("close") / pl.col("close").cum_max() - 1).min()
        ).item()
        delisted = market.securities.filter(pl.col("delisted_on").is_not_null()).height
        print(f"benchmark max drawdown {drawdown:.1%}, {delisted} delisted tickers")
        if drawdown > -0.20:
            problems.append(f"D-3: benchmark drawdown {drawdown:.1%} is not a bear segment")
        if delisted < 20:
            problems.append(f"D-3: only {delisted} delisted tickers")

    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
