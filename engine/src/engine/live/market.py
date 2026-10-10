"""Alpaca bars plus the owner's universe CSV into a checked live `Market` (D-4, spec 0010)."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import polars as pl

from engine.contracts import BARS_SCHEMA, SECURITIES_SCHEMA, DataMeta, Market

from .alpaca import LiveLoadError, RawBars

LIVE_START = date(2016, 1, 4)
BENCHMARK = "SPY"
BENCHMARK_ROW = {"ticker": BENCHMARK, "name": "SPDR S&P 500 ETF Trust", "sector": "Index"}
COLUMNS = ("ticker", "name", "sector")


def read_universe(path: str | Path) -> pl.DataFrame:
    """The universe CSV (`ticker,name,sector`), upper cased, deduplicated, without SPY."""
    with Path(path).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows or not set(COLUMNS) <= set(rows[0]):
        raise LiveLoadError(f"{path} needs a ticker,name,sector header and at least one row")
    universe = pl.DataFrame({c: [r[c].strip() for r in rows] for c in COLUMNS})
    return (
        universe.with_columns(pl.col("ticker").str.to_uppercase())
        .filter(pl.col("ticker") != BENCHMARK)
        .unique("ticker", keep="first", maintain_order=True)
    )


@dataclass
class LoadSummary:
    """What `make load-live` prints (D-4): ticker count, bars, missing symbols."""

    tickers: int
    bars: int
    start: date
    end: date
    missing: list[str] = field(default_factory=list)
    dropped_bars: int = 0

    def lines(self) -> list[str]:
        return [
            f"loaded {self.tickers} tickers plus {BENCHMARK}: {self.bars} bars, "
            f"{self.start} to {self.end}",
            f"missing symbols ({len(self.missing)}): {', '.join(self.missing) or 'none'}",
            f"dropped {self.dropped_bars} bars that failed the D-2 checks",
        ]


def _sane() -> pl.Expr:
    """The D-2 bar rules from `engine.data.sanity`, as a keep filter."""
    positive = [pl.col(c).is_finite() & (pl.col(c) > 0) for c in ("open", "high", "low", "close")]
    return pl.all_horizontal(
        *positive,
        pl.col("volume") > 0,
        pl.col("low") <= pl.min_horizontal("open", "close"),
        pl.col("high") >= pl.max_horizontal("open", "close"),
    ).fill_null(False)


def build_market(
    universe: pl.DataFrame, raw: RawBars, start: date, end: date
) -> tuple[Market, LoadSummary]:
    """Bars in `[start, end]` for the universe plus SPY; bars failing D-2 are dropped."""
    rows = [
        {
            "ticker": symbol.upper(),
            "date": date.fromisoformat(str(b["t"])[:10]),
            "open": float(b["o"]),
            "high": float(b["h"]),
            "low": float(b["l"]),
            "close": float(b["c"]),
            "volume": float(b["v"]),
        }
        for symbol, bars in raw.items()
        for b in bars
    ]
    names = pl.concat([universe.select(COLUMNS), pl.DataFrame([BENCHMARK_ROW])])
    every = (
        pl.DataFrame(rows, schema=BARS_SCHEMA)
        .filter(pl.col("date").is_between(start, end))
        .filter(pl.col("ticker").is_in(names["ticker"].implode()))
        .unique(["ticker", "date"], keep="first")
    )
    bars = every.filter(_sane()).sort("ticker", "date")
    if BENCHMARK not in set(bars["ticker"].to_list()):
        raise LiveLoadError(f"no {BENCHMARK} bars came back; the benchmark is required (D-4)")

    first = bars.group_by("ticker").agg(pl.col("date").min().alias("listed_from"))
    securities = (
        names.join(first, on="ticker", how="inner")
        .with_columns(
            pl.lit(None, pl.Date).alias("delisted_on"),
            pl.lit(None, pl.String).alias("delist_reason"),
        )
        .select(list(SECURITIES_SCHEMA))
        .sort("ticker")
    )
    loaded = set(securities["ticker"].to_list()) - {BENCHMARK}
    first_day, last_day = bars["date"].min(), bars["date"].max()
    if not isinstance(first_day, date) or not isinstance(last_day, date):  # pragma: no cover
        raise LiveLoadError("bars have no dates")
    meta = DataMeta(
        data_mode="live",
        seed=None,
        data_version=f"alpaca-sip-all:{last_day.isoformat()}",
        start=first_day,
        end=last_day,
        n_tickers=len(loaded),
        survivors_only=True,
        benchmark=BENCHMARK,
    )
    summary = LoadSummary(
        tickers=len(loaded),
        bars=bars.height,
        start=first_day,
        end=last_day,
        missing=sorted(set(universe["ticker"].to_list()) - loaded),
        dropped_bars=every.height - bars.height,
    )
    return Market(bars=bars, securities=securities, meta=meta), summary
