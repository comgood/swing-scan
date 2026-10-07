"""AC-11: oracle CSV fixtures and Python built markets share one calendar and inference."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from engine.data.fixtures import (
    BENCHMARK,
    FixtureError,
    FrameSpec,
    bar_date,
    load_fixture,
    make_market,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def security(market_securities: pl.DataFrame, ticker: str) -> dict[str, object]:
    return market_securities.filter(pl.col("ticker") == ticker).row(0, named=True)


def test_calendar_is_weekdays_from_2020_01_02() -> None:
    assert bar_date(1) == date(2020, 1, 2)
    assert bar_date(2) == date(2020, 1, 3)
    assert bar_date(3) == date(2020, 1, 6)  # skips the weekend
    assert bar_date(261) == date(2020, 12, 31)


def test_csv_infers_listing_and_delisting() -> None:
    market = load_fixture(FIXTURES / "listing.csv")
    s = market.securities
    assert security(s, "AAA")["delisted_on"] is None  # alive at the end of data
    assert security(s, "BBB")["listed_from"] == date(2020, 1, 6)
    ccc = security(s, "CCC")
    assert ccc["delisted_on"] == date(2020, 1, 7) and ccc["delist_reason"] == "fixture"
    assert security(s, "AAA")["name"] == "AAA" and security(s, "AAA")["sector"] == "fixture"


def test_csv_adds_a_flat_benchmark_and_fixture_meta() -> None:
    market = load_fixture(FIXTURES / "listing.csv")
    index = market.bars.filter(pl.col("ticker") == BENCHMARK)
    assert index.height == 5 and index["close"].to_list() == [100.0] * 5
    meta = market.meta
    assert meta.benchmark == BENCHMARK and meta.seed is None
    assert meta.data_version == "fixture:listing" and meta.n_tickers == 3
    assert (meta.start, meta.end) == (date(2020, 1, 2), date(2020, 1, 8))
    assert not meta.survivors_only


def test_sidecar_expresses_a_final_bar_delisting() -> None:
    market = load_fixture(FIXTURES / "final_bar_delisting.csv")
    aaa = security(market.securities, "AAA")
    assert aaa["delisted_on"] == date(2020, 1, 6) and aaa["delist_reason"] == "acquired"


def write(tmp: Path, name: str, body: str) -> Path:
    path = tmp / name
    path.write_text(body)
    return path


HEADER = "ticker,bar,open,high,low,close,volume\n"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("AAA,1,1,1,1,1,\n", "volume is blank"),
        ("AAA,1,1,1,x,1,1\n", "low is 'x'"),
        ("AAA,1,1,1,1,1,1\nAAA,3,1,1,1,1,1\n", "gap in bars"),
        ("AAA,1,1,1,1,1,1\nAAA,2,1,1,1,1,1\nFIXTURE-INDEX,2,1,1,1,1,1\n", "must cover every bar"),
        ("AAA,1.5,1,1,1,1,1\n", "not a 1 based integer"),
        ("AAA,0,1,1,1,1,1\n", "not a 1 based integer"),
        ("AAA,1,1,1,1,1,1\nAAA,1,1,1,1,1,1\n", "appears twice"),
        (",1,1,1,1,1,1\n", "ticker is blank"),
        ("AAA,1,1,1,1,1\n", "expected 7 values"),
    ],
)
def test_load_errors(tmp_path: Path, body: str, message: str) -> None:
    with pytest.raises(FixtureError, match=message):
        load_fixture(write(tmp_path, "bad.csv", HEADER + body))


def test_every_problem_is_listed_at_once(tmp_path: Path) -> None:
    body = "AAA,1,1,1,1,1,\nBBB,1,1,1,1,1,1\nBBB,3,1,1,1,1,1\n"
    with pytest.raises(FixtureError) as caught:
        load_fixture(write(tmp_path, "bad.csv", HEADER + body))
    assert len(caught.value.problems) == 2


def test_wrong_header(tmp_path: Path) -> None:
    with pytest.raises(FixtureError, match="header"):
        load_fixture(write(tmp_path, "bad.csv", "ticker,date,close\n"))


@pytest.mark.parametrize(
    ("sidecar", "message"),
    [
        ("BBB,,3,\n", "unknown ticker"),
        ("AAA,2,,\n", "listed_bar 2 is after"),
        ("AAA,,1,\n", "delisted_bar 1 is before"),
    ],
)
def test_sidecar_errors(tmp_path: Path, sidecar: str, message: str) -> None:
    write(tmp_path, "x.securities.csv", "ticker,listed_bar,delisted_bar,delist_reason\n" + sidecar)
    with pytest.raises(FixtureError, match=message):
        load_fixture(write(tmp_path, "x.csv", HEADER + "AAA,1,1,1,1,1,1\nAAA,2,1,1,1,1,1\n"))


def test_make_market_matches_the_csv_loader() -> None:
    from_csv = load_fixture(FIXTURES / "listing.csv")
    rows = from_csv.bars.filter(pl.col("ticker") != BENCHMARK)
    specs = {}
    for ticker in ("AAA", "BBB", "CCC"):
        t = rows.filter(pl.col("ticker") == ticker)
        first = 1 if ticker != "BBB" else 3
        specs[ticker] = FrameSpec(
            start_bar=first,
            open=t["open"].to_list(),
            high=t["high"].to_list(),
            low=t["low"].to_list(),
            close=t["close"].to_list(),
            volume=t["volume"].to_list(),
        )
    built = make_market(specs, name="listing")
    assert built.bars.equals(from_csv.bars)
    assert built.securities.equals(from_csv.securities)
    assert built.meta == from_csv.meta


def test_make_market_close_only_defaults_and_long_series() -> None:
    market = make_market({"LONG": FrameSpec(1, [10.0] * 261)}, end_bar=270)
    long = market.bars.filter(pl.col("ticker") == "LONG")
    assert long.height == 261
    assert long.row(0, named=True)["volume"] == 1_000_000.0
    assert long.row(0, named=True)["high"] == 10.0
    assert security(market.securities, "LONG")["delisted_on"] == bar_date(261)
    assert market.meta.end == bar_date(270)


def test_make_market_rejects_an_end_bar_before_the_data() -> None:
    with pytest.raises(FixtureError, match="end_bar"):
        make_market({"A": FrameSpec(1, [1.0, 2.0])}, end_bar=1)


def test_comment_lines_are_ignored(tmp_path: Path) -> None:  # covers: AC-11
    body = (
        "# hand math: 10 * 1.1 = 11\n"
        + HEADER
        + "# bar 2 below\nAAA,1,10,10,10,10,1\nAAA,2,11,11,11,11,1\n"
    )
    market = load_fixture(write(tmp_path, "commented.csv", body))
    assert market.bars.filter(pl.col("ticker") == "AAA")["close"].to_list() == [10.0, 11.0]


def test_a_csv_benchmark_is_kept_instead_of_the_flat_one(tmp_path: Path) -> None:
    body = HEADER + "AAA,1,1,1,1,1,1\nFIXTURE-INDEX,1,50,50,50,50,1\n"
    market = load_fixture(write(tmp_path, "own_index.csv", body))
    assert market.bars.filter(pl.col("ticker") == BENCHMARK)["close"].to_list() == [50.0]


def test_frame_spec_rejects_mismatched_list_lengths() -> None:
    with pytest.raises(ValueError, match="open has 1 values"):
        make_market({"A": FrameSpec(1, [1.0, 2.0], open=[1.0])})


def test_bar_numbers_start_at_one() -> None:
    with pytest.raises(ValueError):
        bar_date(0)
