"""The published window and the tick that moves it (spec 0012).

The truncation tests run on the real seed 42 master, because the numbers they prove (D-3 at
both ends of the runway) are the ones the published demo stands on. The tick tests run on a
small master instead, injected the way the other dataset tests inject one, so the branches
are covered without regenerating 1818 sessions per case.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from engine.contracts import Market
from engine.data import read_market, read_meta, session_dates, truncate_market, write_market
from engine.synthetic import SyntheticConfig, generate
from engine.synthetic.config import PUBLISHED_START_SESSIONS
from engine.synthetic.tick import tick

SMALL = SyntheticConfig(n_tickers=20, n_sessions=320, min_delisted=3)
SMALL_SEED = 1
SMALL_PUBLISHED = 300
"""Sessions published in the small store, leaving 20 ticks of runway."""

DATED_COLUMNS = ("listed_from", "delisted_on")


@pytest.fixture(scope="module")
def master() -> Market:
    return generate(42)


def drawdown(market: Market) -> float:
    bench = market.bars.filter(pl.col("ticker") == market.meta.benchmark).sort("date")
    value: float = bench.select((pl.col("close") / pl.col("close").cum_max() - 1).min()).item()
    return value


def n_delisted(market: Market) -> int:
    return market.securities.filter(pl.col("delisted_on").is_not_null()).height


def test_the_initial_cursor_is_the_date_the_demo_already_ends_on(master: Market) -> None:
    # AC-10: the as of date must not jump when the longer master lands.
    assert session_dates(master)[PUBLISHED_START_SESSIONS - 1].isoformat() == "2025-10-31"


@pytest.mark.parametrize("cursor_at", [PUBLISHED_START_SESSIONS, 1500, 1818])
def test_the_published_window_is_sane_and_hides_the_future(master: Market, cursor_at: int) -> None:
    # AC-5 and AC-6. truncate_market runs check_market itself, so reaching the asserts at all
    # is half the proof; the delist pair rule is the half that broke in the spec's measuring.
    cursor = session_dates(master)[cursor_at - 1]
    published = truncate_market(master, cursor)

    assert published.meta.end == cursor
    assert published.bars.filter(pl.col("date") > cursor).height == 0
    for column in DATED_COLUMNS:
        assert published.securities.filter(pl.col(column) > cursor).height == 0
    assert (
        published.securities.filter(
            pl.col("delisted_on").is_null() != pl.col("delist_reason").is_null()
        ).height
        == 0
    )


def test_d3_holds_at_both_ends_of_the_runway(master: Market) -> None:
    # AC-7: the whole reason delisting_fraction moved to 0.08.
    for cursor_at in (PUBLISHED_START_SESSIONS, len(session_dates(master))):
        published = truncate_market(master, session_dates(master)[cursor_at - 1])
        assert n_delisted(published) >= 20, cursor_at
        assert drawdown(published) <= -0.20, cursor_at


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A small store published short of its master, with the tick regenerating that master."""
    monkeypatch.setattr(
        "engine.synthetic.tick.generate", lambda seed: generate(seed, SMALL), raising=True
    )
    small = generate(SMALL_SEED, SMALL)
    write_market(truncate_market(small, session_dates(small)[SMALL_PUBLISHED - 1]), tmp_path)
    return tmp_path


def small_sessions() -> list[date]:
    return session_dates(generate(SMALL_SEED, SMALL))


def test_a_tick_appends_exactly_one_session_and_rewrites_no_history(store: Path) -> None:  # AC-1
    before = read_market(store)
    sessions = small_sessions()

    assert tick(str(store)) == 0

    after = read_market(store)
    assert after.meta.end == sessions[SMALL_PUBLISHED]
    assert after.bars.filter(pl.col("date") <= before.meta.end).equals(before.bars)
    appended = after.bars.filter(pl.col("date") == after.meta.end)
    assert appended.height > 0
    assert after.bars.height == before.bars.height + appended.height


def test_a_tick_aborts_and_writes_nothing_when_the_published_bars_were_altered(
    store: Path, capsys: pytest.CaptureFixture[str]
) -> None:  # AC-2
    bars = store / "bars.parquet"
    # Volume, so the altered dataset still passes the D-2 bar checks on the way in.
    pl.read_parquet(bars).with_columns(
        pl.when(pl.col("date") == pl.col("date").min())
        .then(pl.col("volume") * 2)
        .otherwise(pl.col("volume"))
        .alias("volume")
    ).write_parquet(bars)
    before = read_meta(store)

    assert tick(str(store)) == 1
    assert "do not match the master" in capsys.readouterr().err
    assert read_meta(store) == before


def test_the_same_tick_run_twice_advances_the_cursor_once(
    store: Path, capsys: pytest.CaptureFixture[str]
) -> None:  # AC-3
    target = small_sessions()[SMALL_PUBLISHED]

    assert tick(str(store), target) == 0
    assert tick(str(store), target) == 0

    assert "already current" in capsys.readouterr().out
    assert read_market(store).meta.end == target


def test_a_target_beyond_the_next_session_is_refused(
    store: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = read_meta(store)

    assert tick(str(store), small_sessions()[SMALL_PUBLISHED + 1]) == 1

    assert "one tick advances one session" in capsys.readouterr().err
    assert read_meta(store) == before


def test_a_tick_interrupted_after_bars_is_finished_by_the_next_one(store: Path) -> None:  # AC-4
    before = read_meta(store)
    small = generate(SMALL_SEED, SMALL)
    target = session_dates(small)[SMALL_PUBLISHED]
    # The torn write: new bars in place, meta still pointing at the old dataset.
    truncate_market(small, target).bars.write_parquet(store / "bars.parquet")
    assert read_meta(store) == before, "a reader must still see the previous dataset"

    assert tick(str(store)) == 0

    completed = read_market(store)
    assert completed.meta.end == target
    assert completed.bars.equals(truncate_market(small, target).bars)


def test_the_tick_stops_cleanly_when_the_runway_is_exhausted(
    store: Path, capsys: pytest.CaptureFixture[str]
) -> None:  # AC-8
    small = generate(SMALL_SEED, SMALL)
    write_market(small, store)  # published right up to the master's last session
    before = read_meta(store)

    assert tick(str(store)) == 0

    assert "runway exhausted" in capsys.readouterr().out
    assert read_meta(store) == before


def test_a_dataset_with_no_seed_is_refused(store: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # The live prefix is seedless, so this is also what stops a tick pointed at live data.
    published = read_market(store)
    unseeded = published.meta.model_copy(update={"data_mode": "live", "seed": None})
    write_market(Market(bars=published.bars, securities=published.securities, meta=unseeded), store)

    assert tick(str(store)) == 1
    assert "carries no seed" in capsys.readouterr().err


def test_the_cli_can_write_only_the_published_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from engine.synthetic.__main__ import main

    monkeypatch.setattr("engine.synthetic.__main__.generate", lambda seed: generate(seed, SMALL))
    monkeypatch.setattr("engine.synthetic.__main__.PUBLISHED_START_SESSIONS", SMALL_PUBLISHED)

    assert main(["--seed", str(SMALL_SEED), "--out", str(tmp_path), "--published"]) == 0
    assert read_market(tmp_path).meta.end == small_sessions()[SMALL_PUBLISHED - 1]
