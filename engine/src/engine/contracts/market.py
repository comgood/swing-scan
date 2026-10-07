"""The stored data shapes: bars, securities, dataset meta, and the in memory `Market` (AC-10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import polars as pl
from pydantic import model_validator

from ._errors import ContractModel, IsoDate

BARS_SCHEMA: dict[str, pl.DataType] = {
    "ticker": pl.String(),
    "date": pl.Date(),
    "open": pl.Float64(),
    "high": pl.Float64(),
    "low": pl.Float64(),
    "close": pl.Float64(),
    "volume": pl.Float64(),
}
"""`bars.parquet`: one row per (ticker, date), sorted by it. Prices are split adjusted."""

SECURITIES_SCHEMA: dict[str, pl.DataType] = {
    "ticker": pl.String(),
    "name": pl.String(),
    "sector": pl.String(),
    "listed_from": pl.Date(),
    "delisted_on": pl.Date(),
    "delist_reason": pl.String(),
}
"""`securities.parquet`: one row per ticker. `delist_reason` is null exactly when
`delisted_on` is null."""


class DataMeta(ContractModel):
    """`meta.json`: describes one dataset. `benchmark` is excluded from every universe."""

    data_mode: Literal["synthetic", "live"]
    seed: int | None
    data_version: str
    start: IsoDate
    end: IsoDate
    n_tickers: int
    """Tickers excluding the benchmark."""
    survivors_only: bool
    benchmark: str

    @model_validator(mode="after")
    def _synthetic_has_seed(self) -> DataMeta:
        # Hand written fixtures are synthetic but unseeded (spec 0002, Fixture format).
        if (
            self.data_mode == "synthetic"
            and self.seed is None
            and not self.data_version.startswith("fixture:")
        ):
            raise ValueError("a synthetic dataset needs its seed")
        return self


@dataclass(frozen=True)
class Market:
    """One loaded dataset, passed into every use case."""

    bars: pl.DataFrame
    securities: pl.DataFrame
    meta: DataMeta


class MarketError(ValueError):
    """`validate_market` found problems; the message lists every one."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("invalid market:\n" + "\n".join(f"  - {p}" for p in problems))


def _schema_problems(name: str, df: pl.DataFrame, schema: dict[str, pl.DataType]) -> list[str]:
    problems: list[str] = []
    missing = [c for c in schema if c not in df.columns]
    extra = [c for c in df.columns if c not in schema]
    if missing:
        problems.append(f"{name}: missing columns {missing}")
    if extra:
        problems.append(f"{name}: unexpected columns {extra}")
    for column, dtype in schema.items():
        if column in df.columns and df.schema[column] != dtype:
            problems.append(f"{name}.{column}: dtype {df.schema[column]}, expected {dtype}")
    return problems


def validate_market(market: Market) -> None:
    """Raise `MarketError` listing every problem with the market's shape and keys."""
    bars, securities = market.bars, market.securities
    problems = _schema_problems("bars", bars, BARS_SCHEMA)
    problems += _schema_problems("securities", securities, SECURITIES_SCHEMA)
    if problems:
        raise MarketError(problems)  # the key checks below need the right columns

    dupes = bars.group_by("ticker", "date").len().filter(pl.col("len") > 1)
    if dupes.height:
        first = dupes.sort("ticker", "date").row(0, named=True)
        problems.append(
            f"bars: {dupes.height} duplicate (ticker, date) keys, "
            f"first {first['ticker']} {first['date']}"
        )
    if not bars.select("ticker", "date").equals(
        bars.select("ticker", "date").sort("ticker", "date")
    ):
        problems.append("bars: not sorted by (ticker, date)")

    if securities["ticker"].is_duplicated().any():
        problems.append("securities: duplicate tickers")
    mismatched = securities.filter(
        pl.col("delisted_on").is_null() != pl.col("delist_reason").is_null()
    )
    if mismatched.height:
        problems.append(
            "securities: delist_reason and delisted_on must be set together, not for "
            f"{sorted(mismatched['ticker'].to_list())}"
        )

    unknown = set(bars["ticker"].unique().to_list()) - set(securities["ticker"].to_list())
    if unknown:
        problems.append(f"bars: tickers missing from securities {sorted(unknown)}")
    if market.meta.benchmark not in set(bars["ticker"].unique().to_list()):
        problems.append(f"bars: benchmark {market.meta.benchmark!r} has no bars")

    if problems:
        raise MarketError(problems)
