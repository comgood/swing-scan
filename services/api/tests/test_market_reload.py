"""The store change check and the inline reload (spec 0011, AC-7, AC-8, AC-13, AC-14).

These drive `api.state` directly, because the module loads its market at import and the
reload rebinds that same module attribute. `serving()` puts the module into the state import
would have left it in for a given store, so each test starts from a known dataset.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient

from api import state
from engine.contracts import Market
from engine.data import change_key, read_market, write_market
from engine.data.fixtures import FrameSpec, make_market
from engine.data.store import BARS_FILE, dataset_key


def market_of(n_bars: int) -> Market:
    """A tiny market whose last session moves with `n_bars`, so `meta.end` identifies it."""
    flat = FrameSpec(1, [10.0] * n_bars)
    return make_market({"AAA": flat, "DEMO-INDEX": flat})


def serving(root: Path, monkeypatch: pytest.MonkeyPatch, *, due: bool = True) -> None:
    """Point `api.state` at `root` and load what is there, as import does."""
    monkeypatch.setenv("MARKET_STORE_URI", str(root))
    monkeypatch.delenv("DATA_MODE", raising=False)
    monkeypatch.setattr(state, "market", state.load_market())
    loaded = state.market
    monkeypatch.setattr(state, "_change_key", change_key(loaded.meta) if loaded else None)
    elapsed = state.STORE_CHECK_FLOOR_SECONDS + 1 if due else 0.0
    monkeypatch.setattr(state, "_checked_at", time.monotonic() - elapsed)


def test_a_check_before_the_floor_does_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = market_of(40)
    write_market(first, tmp_path / "synthetic")
    serving(tmp_path, monkeypatch, due=False)
    write_market(market_of(45), tmp_path / "synthetic")
    state.refresh_if_changed()
    assert state.market is not None and state.market.meta.end == first.meta.end


def test_a_changed_dataset_is_reloaded_and_served(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_market(market_of(40), tmp_path / "synthetic")
    serving(tmp_path, monkeypatch)
    later = market_of(45)
    write_market(later, tmp_path / "synthetic")

    state.refresh_if_changed()

    assert state.market is not None and state.market.meta.end == later.meta.end
    from api.main import app

    with TestClient(app) as client:
        assert client.get("/api/v1/meta").json()["data"]["end"] == later.meta.end.isoformat()


def test_a_check_that_finds_no_change_starts_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_market(market_of(40), tmp_path / "synthetic")
    serving(tmp_path, monkeypatch)
    before = state.market
    reads: list[str] = []
    monkeypatch.setattr("api.state.read_market", lambda: reads.append("read"))

    state.refresh_if_changed()

    assert state.market is before and reads == []


def test_only_the_first_of_two_checks_reloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The floor is bypassed on purpose, so what stops the second reload is the change key.
    write_market(market_of(40), tmp_path / "synthetic")
    serving(tmp_path, monkeypatch)
    write_market(market_of(45), tmp_path / "synthetic")
    reloads: list[Market] = []

    def counted() -> Market:
        loaded = read_market()
        reloads.append(loaded)
        return loaded

    monkeypatch.setattr("api.state.read_market", counted)
    for _ in range(2):
        monkeypatch.setattr(
            state, "_checked_at", time.monotonic() - state.STORE_CHECK_FLOOR_SECONDS - 1
        )
        state.refresh_if_changed()
    assert len(reloads) == 1


def test_a_reload_warms_the_new_dataset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_market(market_of(40), tmp_path / "synthetic")
    serving(tmp_path, monkeypatch)
    write_market(market_of(45), tmp_path / "synthetic")
    warmed: list[Market] = []
    monkeypatch.setattr("api.state.use_cases.warm", warmed.append)

    state.refresh_if_changed()

    assert warmed and warmed[-1] is state.market


def test_a_failed_reload_keeps_the_old_market_and_is_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    first = market_of(40)
    write_market(first, tmp_path / "synthetic")
    serving(tmp_path, monkeypatch)

    # New meta, but bars that fail the D-2 checks: the reload must be abandoned.
    later = market_of(45)
    write_market(later, tmp_path / "synthetic")
    bars_key = dataset_key(tmp_path / "synthetic", BARS_FILE)
    pl.read_parquet(bars_key).with_columns(
        pl.when(pl.int_range(pl.len()) == 3).then(0.0).otherwise(pl.col("volume")).alias("volume")
    ).write_parquet(bars_key)

    with caplog.at_level(logging.ERROR, logger="api.state"):
        state.refresh_if_changed()
    assert state.market is not None and state.market.meta.end == first.meta.end
    assert "reload failed" in caplog.text

    write_market(later, tmp_path / "synthetic")
    monkeypatch.setattr(
        state, "_checked_at", time.monotonic() - state.STORE_CHECK_FLOOR_SECONDS - 1
    )
    state.refresh_if_changed()
    assert state.market.meta.end == later.meta.end


def test_a_dataset_that_appears_later_is_picked_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serving(tmp_path, monkeypatch)  # nothing in the store: /scan answers 501
    assert state.market is None

    appeared = market_of(40)
    write_market(appeared, tmp_path / "synthetic")
    state.refresh_if_changed()

    assert state.market is not None and state.market.meta.end == appeared.meta.end


def test_every_request_runs_the_check(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.main import app

    checks: list[object] = []
    monkeypatch.setattr(state, "refresh_if_changed", lambda: checks.append(None))
    with TestClient(app) as client:
        client.get("/api/v1/health")
        client.get("/api/v1/health")
    assert len(checks) == 2
