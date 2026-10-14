"""Data criteria D-1 to D-6 (doc 01 section 6.1).

D-1 to D-3 call the synthetic generator's public entry points (spec 0006):
`engine.synthetic.generate(seed)`, the `python -m engine.synthetic --seed N --out DIR` command and
`engine.data.read_market(DIR)`. The live loader (feature 14) has no frozen entry point yet, so
D-4 and D-5 reach it through an owed hook. The assertions use the frozen `Market` shape
(spec 0002, `BARS_SCHEMA`, `SECURITIES_SCHEMA`, `DataMeta`). D-6 is checked black box through
the guard's command line.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from datetime import date
from functools import cache
from pathlib import Path

import polars as pl
import pytest

from acceptance.support import owed
from engine.contracts import Market
from engine.data import read_market
from engine.synthetic import generate

REPO = Path(__file__).resolve().parents[2]
DATA_LEAK_GUARD = REPO / "scripts" / "guards" / "data_leak.py"


def load_synthetic_market(seed: int) -> Market:
    """A fresh generation every call, so D-1 compares two independent runs."""
    return generate(seed)


@cache
def _seed_42() -> Market:
    return generate(42)


def load_live_market() -> Market:
    owed("D-4", "entry point that reads the local live dataset written by make load-live")


def _bar_sanity_violations(market: Market) -> pl.DataFrame:
    bars = market.bars
    return bars.filter(
        (pl.col("low") > pl.min_horizontal("open", "close"))
        | (pl.col("high") < pl.max_horizontal("open", "close"))
        | (pl.col("volume") <= 0)
    )


@pytest.mark.ac("D-1")
def test_same_seed_gives_identical_frames() -> None:
    first = load_synthetic_market(42)
    second = load_synthetic_market(42)
    assert first.bars.equals(second.bars)
    assert first.securities.equals(second.securities)
    assert first.meta == second.meta


@pytest.mark.ac("D-1")
def test_another_seed_gives_another_market() -> None:
    assert not load_synthetic_market(7).bars.equals(_seed_42().bars)


@pytest.mark.ac("D-1")
def test_the_command_writes_the_same_market_that_generate_returns(tmp_path: Path) -> None:
    """Spec 0006: `python -m engine.synthetic --seed 42 --out DIR`, read back by `read_market`."""
    subprocess.run(
        [sys.executable, "-m", "engine.synthetic", "--seed", "42", "--out", str(tmp_path)],
        check=True,
        capture_output=True,
        timeout=300,
    )
    loaded = read_market(tmp_path)
    expected = _seed_42()
    assert loaded.bars.equals(expected.bars)
    assert loaded.securities.equals(expected.securities)
    assert loaded.meta == expected.meta


@pytest.mark.ac("D-2")
def test_every_bar_is_sane_and_nothing_trades_after_delisting() -> None:
    market = _seed_42()
    assert _bar_sanity_violations(market).height == 0
    delisted = market.securities.filter(pl.col("delisted_on").is_not_null()).select(
        "ticker", "delisted_on"
    )
    late = market.bars.join(delisted, on="ticker").filter(pl.col("date") > pl.col("delisted_on"))
    assert late.height == 0


@pytest.mark.ac("D-2")
def test_prices_are_positive_and_nothing_trades_before_listing() -> None:
    market = _seed_42()
    prices = market.bars.select("open", "high", "low", "close").to_numpy()
    assert all(math.isfinite(x) and x > 0 for x in prices.ravel())
    listed = market.securities.select("ticker", "listed_from")
    early = market.bars.join(listed, on="ticker").filter(pl.col("date") < pl.col("listed_from"))
    assert early.height == 0
    # Every ticker in the bars is in the securities, and the other way round.
    assert set(market.bars["ticker"].unique()) == set(market.securities["ticker"])


@pytest.mark.ac("D-3")
def test_has_a_bear_segment_and_at_least_20_delistings() -> None:
    market = _seed_42()
    n_delisted = market.securities.filter(pl.col("delisted_on").is_not_null()).height
    assert n_delisted >= 20
    # A bear segment, read from the benchmark: a fall of at least 20% from a running peak.
    bench = market.bars.filter(pl.col("ticker") == market.meta.benchmark).sort("date")
    drawdown = bench.select((pl.col("close") / pl.col("close").cum_max() - 1).min()).item()
    assert drawdown <= -0.20


@pytest.mark.ac("D-4")
def test_live_load_starts_2016_and_includes_spy() -> None:
    market = load_live_market()
    firsts = market.bars.group_by("ticker").agg(pl.col("date").min().alias("first"))
    listed = firsts.join(market.securities.select("ticker", "listed_from"), on="ticker")
    too_early = listed.filter(
        (pl.col("first") < date(2016, 1, 4)) & (pl.col("first") < pl.col("listed_from"))
    )
    assert too_early.height == 0
    assert "SPY" in set(market.bars["ticker"].to_list())
    assert market.meta.data_mode == "live"
    assert market.meta.survivors_only is True


@pytest.mark.ac("D-5")
def test_live_mode_refuses_a_public_host() -> None:
    owed("D-5", "how the API learns its host and refuses DATA_MODE=live off localhost")


def _guard(cwd: Path, *files: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DATA_LEAK_GUARD), *files],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.ac("D-6")
@pytest.mark.parametrize("path", ["data/bars.parquet", "data/live/prices.csv", "data/x.parquet"])
def test_data_leak_guard_blocks_market_data(tmp_path: Path, path: str) -> None:
    target = tmp_path / path
    target.parent.mkdir(parents=True)
    target.write_text("ticker,date,close\nAAA,2020-01-02,10\n")
    result = _guard(tmp_path, path)
    assert result.returncode != 0
    assert path in result.stdout + result.stderr


@pytest.mark.ac("D-6")
def test_data_leak_guard_blocks_a_parquet_under_any_name(tmp_path: Path) -> None:
    # The suffix list cannot catch a market dump saved as prices.dat, so the guard reads
    # parquet's magic bytes. Without that, renaming the file is enough to commit real bars.
    target = tmp_path / "notes" / "prices.dat"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"PAR1" + b"\x00" * 64)
    result = _guard(tmp_path, "notes/prices.dat")
    assert result.returncode != 0
    assert "parquet" in result.stdout + result.stderr


@pytest.mark.ac("D-6")
@pytest.mark.parametrize("name", ["ALPACA_API_SECRET_KEY", "APCA_API_SECRET_KEY"])
def test_data_leak_guard_blocks_an_alpaca_key_in_either_spelling(tmp_path: Path, name: str) -> None:
    # Alpaca's own SDK and docs use APCA_; gitleaks does not recognise either spelling, so
    # these two patterns are the only thing standing between a copied .env and a public repo.
    # Assembled at runtime so this file never holds a key shaped string itself.
    fake = "wJalrXUtnFEMI" + "K7MDENGbPxRfiCYEXAMPLEKEY"
    (tmp_path / ".env").write_text(f"{name}={fake}\n")
    result = _guard(tmp_path, ".env")
    assert result.returncode != 0
    assert "Alpaca API key" in result.stdout + result.stderr


@pytest.mark.ac("D-6")
def test_data_leak_guard_allows_test_fixtures(tmp_path: Path) -> None:
    target = tmp_path / "tests" / "fixtures" / "small.csv"
    target.parent.mkdir(parents=True)
    target.write_text("ticker,bar,open,high,low,close,volume\n")
    assert _guard(tmp_path, "tests/fixtures/small.csv").returncode == 0


def _gitleaks() -> str | None:
    found = shutil.which("gitleaks")
    if found:
        return found
    cached = sorted(Path.home().glob(".cache/pre-commit/*/golangenv-default/bin/gitleaks"))
    return str(cached[0]) if cached else None


@pytest.mark.ac("D-6")
def test_secret_scan_blocks_an_api_key(tmp_path: Path) -> None:
    binary = _gitleaks()
    if binary is None:
        pytest.skip("gitleaks is not installed here; the CI guards job runs it on every PR")
    # Built at runtime so this file never holds a key shaped string itself.
    fake = "AKIA" + "QYLPMN5HHHFPZAM2"
    (tmp_path / "settings.py").write_text(f'aws_access_key_id = "{fake}"\n')
    result = subprocess.run(
        [binary, "dir", str(tmp_path), "--no-banner", "--redact"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
