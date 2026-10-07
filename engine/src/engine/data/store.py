"""Read and write one dataset directory: `bars.parquet`, `securities.parquet`, `meta.json`
(doc 02 §5.1, spec 0002)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import polars as pl

from engine.contracts import BARS_SCHEMA, SECURITIES_SCHEMA, DataMeta, Market

from .sanity import check_market

BARS_FILE = "bars.parquet"
SECURITIES_FILE = "securities.parquet"
META_FILE = "meta.json"
DATA_DIR_ENV = "SYNTHETIC_DATA_DIR"
DEFAULT_DATA_DIR = Path("data/synthetic")


def market_dir() -> Path:
    """Where the synthetic dataset lives: `$SYNTHETIC_DATA_DIR`, else `data/synthetic`."""
    configured = os.environ.get(DATA_DIR_ENV)
    return Path(configured) if configured else DEFAULT_DATA_DIR


def write_market(market: Market, out_dir: str | Path) -> Path:
    """Check the market, then write its three files into `out_dir` (created if missing).

    Output is byte for byte reproducible for the same market and library versions.
    """
    check_market(market)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    market.bars.write_parquet(out / BARS_FILE, compression="zstd", statistics=False)
    market.securities.write_parquet(out / SECURITIES_FILE, compression="zstd", statistics=False)
    meta = market.meta.model_dump(mode="json")
    (out / META_FILE).write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", "utf-8")
    return out


def read_market(data_dir: str | Path | None = None) -> Market:
    """Load and check the dataset in `data_dir` (default: `market_dir()`)."""
    root = Path(data_dir) if data_dir is not None else market_dir()
    missing = [n for n in (BARS_FILE, SECURITIES_FILE, META_FILE) if not (root / n).is_file()]
    if missing:
        raise FileNotFoundError(
            f"no dataset in {root}: missing {missing}. Run `make data` to generate it."
        )
    bars = pl.read_parquet(root / BARS_FILE).cast(BARS_SCHEMA)  # type: ignore[arg-type]
    securities = pl.read_parquet(root / SECURITIES_FILE).cast(SECURITIES_SCHEMA)  # type: ignore[arg-type]
    meta = DataMeta.model_validate_json((root / META_FILE).read_text("utf-8"))
    market = Market(bars=bars, securities=securities, meta=meta)
    check_market(market)
    return market
