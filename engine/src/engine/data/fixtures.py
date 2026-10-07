"""Hand checked test fixtures: bar numbered CSVs and Python lists into a `Market` (AC-11).

The format is frozen in spec 0002 (*Fixture format*, SO-3). Bar k is the k-th weekday
counting from Thu 2020-01-02, with no holidays. Listing and delisting are inferred from each
ticker's first and last bar; an optional `<name>.securities.csv` sidecar overrides them.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from engine.contracts import (
    BARS_SCHEMA,
    SECURITIES_SCHEMA,
    DataMeta,
    Market,
    validate_market,
)

CALENDAR_START = date(2020, 1, 2)
BENCHMARK = "FIXTURE-INDEX"
HEADER = ["ticker", "bar", "open", "high", "low", "close", "volume"]
SIDECAR_HEADER = ["ticker", "listed_bar", "delisted_bar", "delist_reason"]
DEFAULT_VOLUME = 1_000_000.0
PRICE_COLUMNS = ("open", "high", "low", "close", "volume")


class FixtureError(ValueError):
    """A fixture could not be loaded; the message lists every problem."""

    def __init__(self, source: str, problems: list[str]) -> None:
        self.problems = problems
        super().__init__(f"bad fixture {source}:\n" + "\n".join(f"  - {p}" for p in problems))


def bar_date(bar: int) -> date:
    """The date of 1 based bar `bar`: the bar-th weekday counting from 2020-01-02."""
    if bar < 1:
        raise ValueError(f"bars start at 1, got {bar}")
    day, remaining = CALENDAR_START, bar - 1
    while remaining:
        day += timedelta(days=1)
        if day.weekday() < 5:
            remaining -= 1
    return day


@dataclass(frozen=True)
class Bar:
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class FrameSpec:
    """One ticker for `make_market`: `close` alone, or full OHLCV lists of equal length.

    With `close` alone, open, high and low default to close and volume to 1,000,000.
    """

    start_bar: int
    close: Sequence[float]
    open: Sequence[float] | None = None
    high: Sequence[float] | None = None
    low: Sequence[float] | None = None
    volume: Sequence[float] | None = None

    def bars(self) -> dict[int, Bar]:
        n = len(self.close)
        given = {"open": self.open, "high": self.high, "low": self.low, "volume": self.volume}
        for name, values in given.items():
            if values is not None and len(values) != n:
                raise ValueError(f"{name} has {len(values)} values, close has {n}")
        return {
            self.start_bar + i: Bar(
                open=self.open[i] if self.open is not None else self.close[i],
                high=self.high[i] if self.high is not None else self.close[i],
                low=self.low[i] if self.low is not None else self.close[i],
                close=self.close[i],
                volume=self.volume[i] if self.volume is not None else DEFAULT_VOLUME,
            )
            for i in range(n)
        }


@dataclass
class _Override:
    listed_bar: int | None = None
    delisted_bar: int | None = None
    delist_reason: str | None = None


@dataclass
class _Builder:
    """Collects bars per ticker, then infers securities and meta the same way for both entry
    points."""

    name: str
    bars: dict[str, dict[int, Bar]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    def check_contiguous(self) -> None:
        for ticker, rows in self.bars.items():
            numbers = sorted(rows)
            missing = sorted(set(range(numbers[0], numbers[-1] + 1)) - set(numbers))
            if missing:
                self.problems.append(f"{ticker}: gap in bars, missing {missing}")

    def build(self, last_bar: int, overrides: dict[str, _Override]) -> Market:
        if BENCHMARK in self.bars:
            covered = set(self.bars[BENCHMARK])
            if covered != set(range(1, last_bar + 1)):
                self.problems.append(f"{BENCHMARK} must cover every bar from 1 to {last_bar}")
        for ticker, override in overrides.items():
            rows = self.bars.get(ticker)
            if rows is None:
                self.problems.append(f"sidecar names unknown ticker {ticker}")
                continue
            first, last = min(rows), max(rows)
            if override.listed_bar is not None and override.listed_bar > first:
                self.problems.append(
                    f"sidecar {ticker}: listed_bar {override.listed_bar} is after its first "
                    f"bar {first}"
                )
            if override.delisted_bar is not None and override.delisted_bar < last:
                self.problems.append(
                    f"sidecar {ticker}: delisted_bar {override.delisted_bar} is before its "
                    f"last bar {last}"
                )
        if self.problems:
            raise FixtureError(self.name, self.problems)

        if BENCHMARK not in self.bars:
            self.bars[BENCHMARK] = {
                k: Bar(100.0, 100.0, 100.0, 100.0, DEFAULT_VOLUME) for k in range(1, last_bar + 1)
            }

        bar_rows = [
            {"ticker": ticker, "date": bar_date(k), **vars(bar)}
            for ticker in sorted(self.bars)
            for k, bar in sorted(self.bars[ticker].items())
        ]
        security_rows = []
        for ticker in sorted(self.bars):
            first, last = min(self.bars[ticker]), max(self.bars[ticker])
            override = overrides.get(ticker, _Override())
            listed = override.listed_bar if override.listed_bar is not None else first
            delisted: int | None = last if last < last_bar else None
            reason = "fixture" if delisted is not None else None
            if override.delisted_bar is not None:
                delisted, reason = override.delisted_bar, override.delist_reason or "fixture"
            security_rows.append(
                {
                    "ticker": ticker,
                    "name": ticker,
                    "sector": "fixture",
                    "listed_from": bar_date(listed),
                    "delisted_on": bar_date(delisted) if delisted is not None else None,
                    "delist_reason": reason,
                }
            )
        market = Market(
            bars=pl.DataFrame(bar_rows, schema=BARS_SCHEMA),
            securities=pl.DataFrame(security_rows, schema=SECURITIES_SCHEMA),
            meta=DataMeta(
                data_mode="synthetic",
                seed=None,
                data_version=f"fixture:{self.name}",
                start=bar_date(1),
                end=bar_date(last_bar),
                n_tickers=len(self.bars) - 1,
                survivors_only=False,
                benchmark=BENCHMARK,
            ),
        )
        validate_market(market)
        return market


def _number(raw: str, column: str, line: int, problems: list[str]) -> float | None:
    try:
        return float(raw)
    except ValueError:
        shown = repr(raw) if raw.strip() else "blank"
        problems.append(f"line {line}: {column} is {shown}, expected a number")
        return None


def _rows(path: Path) -> list[tuple[int, list[str]]]:
    """Non comment, non empty CSV rows with their 1 based line numbers."""
    with path.open(newline="", encoding="utf-8") as handle:
        lines = [(i, line) for i, line in enumerate(handle, start=1) if not line.startswith("#")]
    parsed = csv.reader(line for _, line in lines)
    return [(lines[i][0], row) for i, row in enumerate(parsed) if row]


def _read_sidecar(path: Path, problems: list[str]) -> dict[str, _Override]:
    rows = _rows(path)
    if not rows or rows[0][1] != SIDECAR_HEADER:
        problems.append(f"{path.name}: header must be {','.join(SIDECAR_HEADER)}")
        return {}
    overrides: dict[str, _Override] = {}
    for line, row in rows[1:]:
        if len(row) != len(SIDECAR_HEADER):
            problems.append(f"{path.name} line {line}: expected {len(SIDECAR_HEADER)} values")
            continue
        ticker, listed, delisted, reason = (v.strip() for v in row)
        override = _Override(delist_reason=reason or None)
        for raw, attr in ((listed, "listed_bar"), (delisted, "delisted_bar")):
            if raw:
                if raw.isdigit() and int(raw) >= 1:
                    setattr(override, attr, int(raw))
                else:
                    problems.append(f"{path.name} line {line}: {attr} {raw!r} is not a bar")
        overrides[ticker] = override
    return overrides


def load_fixture(path: str | Path) -> Market:
    """Load an oracle fixture CSV (and its optional sidecar) into a validated `Market`."""
    path = Path(path)
    builder = _Builder(name=path.stem)
    rows = _rows(path)
    if not rows or rows[0][1] != HEADER:
        raise FixtureError(path.name, [f"header must be exactly {','.join(HEADER)}"])

    for line, row in rows[1:]:
        if len(row) != len(HEADER):
            builder.problems.append(f"line {line}: expected {len(HEADER)} values, got {len(row)}")
            continue
        ticker, raw_bar, *raw_values = (v.strip() for v in row)
        if not ticker:
            builder.problems.append(f"line {line}: ticker is blank")
        if not (raw_bar.isdigit() and int(raw_bar) >= 1):
            builder.problems.append(f"line {line}: bar {raw_bar!r} is not a 1 based integer")
        values = [
            _number(raw, column, line, builder.problems)
            for raw, column in zip(raw_values, PRICE_COLUMNS, strict=True)
        ]
        if not ticker or not raw_bar.isdigit() or int(raw_bar) < 1 or None in values:
            continue
        bar = int(raw_bar)
        rows_for_ticker = builder.bars.setdefault(ticker, {})
        if bar in rows_for_ticker:
            builder.problems.append(f"line {line}: {ticker} bar {bar} appears twice")
        o, h, low, c, v = (x for x in values if x is not None)
        rows_for_ticker[bar] = Bar(o, h, low, c, v)

    if not builder.bars:
        builder.problems.append("no bars")
        raise FixtureError(path.name, builder.problems)
    builder.check_contiguous()

    sidecar = path.with_name(f"{path.stem}.securities.csv")
    overrides = _read_sidecar(sidecar, builder.problems) if sidecar.exists() else {}
    last_bar = max(max(rows) for rows in builder.bars.values())
    return builder.build(last_bar, overrides)


def make_market(
    tickers: dict[str, FrameSpec], end_bar: int | None = None, name: str = "built"
) -> Market:
    """Build a `Market` from Python lists, with the same calendar and inference as CSVs.

    `end_bar` sets the dataset's last bar (default: the highest bar of any ticker), so a
    ticker that stops earlier counts as delisted.
    """
    builder = _Builder(name=name)
    for ticker, spec in tickers.items():
        if spec.start_bar < 1:
            builder.problems.append(f"{ticker}: start_bar must be at least 1")
            continue
        builder.bars[ticker] = spec.bars()
    if not builder.bars:
        raise FixtureError(name, ["no tickers"])
    highest = max(max(rows) for rows in builder.bars.values())
    last_bar = highest if end_bar is None else end_bar
    if last_bar < highest:
        builder.problems.append(f"end_bar {last_bar} is before the last bar {highest}")
    return builder.build(last_bar, {})
