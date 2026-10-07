"""Dataset files and the D-2 sanity checks (spec 0006)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from engine.contracts import Market, MarketError
from engine.data import (
    DATA_DIR_ENV,
    bar_problems,
    check_market,
    market_dir,
    read_market,
    write_market,
)
from engine.data.fixtures import FrameSpec, make_market
from engine.synthetic import SyntheticConfig, generate
from engine.synthetic.__main__ import main

SMALL = SyntheticConfig(n_tickers=30, n_sessions=320, min_delisted=3)


@pytest.fixture(scope="module")
def small() -> Market:
    return generate(7, SMALL)


def tiny() -> Market:
    return make_market({"AAA": FrameSpec(start_bar=1, close=[10.0, 11.0, 12.0])})


def with_bars(market: Market, bars: pl.DataFrame) -> Market:
    return Market(bars=bars, securities=market.securities, meta=market.meta)


def test_round_trip_is_equal(small: Market, tmp_path: Path) -> None:
    write_market(small, tmp_path)
    loaded = read_market(tmp_path)
    assert loaded.bars.equals(small.bars)
    assert loaded.securities.equals(small.securities)
    assert loaded.meta == small.meta


def test_files_are_byte_identical_for_the_same_seed(small: Market, tmp_path: Path) -> None:
    write_market(small, tmp_path / "a")
    write_market(generate(7, SMALL), tmp_path / "b")
    for name in ("bars.parquet", "securities.parquet", "meta.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_read_market_names_missing_files(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="make data"):
        read_market(tmp_path)


def test_market_dir_reads_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    assert market_dir() == Path("data/synthetic")
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    assert market_dir() == tmp_path


def test_read_market_uses_the_environment_by_default(
    small: Market, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_market(small, tmp_path)
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    assert read_market().meta == small.meta


def test_cli_writes_the_dataset(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--seed", "42", "--out", str(tmp_path)]) == 0
    assert "500 tickers" in capsys.readouterr().out
    market = read_market(tmp_path)
    assert market.meta.seed == 42


def test_a_sane_market_has_no_problems() -> None:
    check_market(tiny())
    assert bar_problems(tiny()) == []


@pytest.mark.parametrize(
    ("column", "value", "label"),
    [
        ("low", 10.5, "low above min(open, close)"),
        ("high", 9.5, "high below max(open, close)"),
        ("volume", 0.0, "volume not positive"),
        ("close", -1.0, "not positive"),
        ("open", float("nan"), "not finite"),
    ],
)
def test_each_bad_bar_is_reported(column: str, value: float, label: str) -> None:
    market = tiny()
    bars = market.bars.with_columns(
        pl.when((pl.col("ticker") == "AAA") & (pl.col("date") == date(2020, 1, 2)))
        .then(pl.lit(value))
        .otherwise(pl.col(column))
        .alias(column)
    )
    problems = bar_problems(with_bars(market, bars))
    assert any(label in p for p in problems), problems
    with pytest.raises(MarketError):
        check_market(with_bars(market, bars))


def test_bars_after_delisting_or_before_listing_are_reported() -> None:
    market = tiny()
    securities = market.securities.with_columns(
        pl.when(pl.col("ticker") == "AAA")
        .then(pl.lit(date(2020, 1, 3)))
        .otherwise(pl.col("delisted_on"))
        .alias("delisted_on"),
        pl.when(pl.col("ticker") == "AAA")
        .then(pl.lit("test"))
        .otherwise(pl.col("delist_reason"))
        .alias("delist_reason"),
        pl.when(pl.col("ticker") == "AAA")
        .then(pl.lit(date(2020, 1, 3)))
        .otherwise(pl.col("listed_from"))
        .alias("listed_from"),
    )
    broken = Market(bars=market.bars, securities=securities, meta=market.meta)
    problems = bar_problems(broken)
    assert any("after delisted_on" in p for p in problems), problems
    assert any("before listed_from" in p for p in problems), problems
