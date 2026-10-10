"""D-5 on the dataset, not on `DATA_MODE`: a live market never loads on a public host.

`test_settings.py` covers the environment variable half. These cover the half that matters
when nobody sets it: the dataset says what it is, and the health route repeats the dataset's
own answer, so the web app's "not real prices" banner (U-1, U-2) cannot be wrong.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import state
from engine.contracts import Market
from engine.data import write_market
from engine.data.fixtures import FrameSpec, make_market

UVICORN = ["uvicorn", "api.main:app"]
PUBLIC = ["uvicorn", "api.main:app", "--host", "0.0.0.0"]  # noqa: S104


def live_market() -> Market:
    """A tiny market whose `meta` says it is real vendor data."""
    flat = FrameSpec(1, [10.0] * 40)
    market = make_market({"AAA": flat, "DEMO-INDEX": flat})
    meta = market.meta.model_copy(
        update={"data_mode": "live", "seed": None, "data_version": "alpaca-iex"}
    )
    return Market(bars=market.bars, securities=market.securities, meta=meta)


@pytest.fixture
def live_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    out = tmp_path / "live"
    write_market(live_market(), out)
    monkeypatch.setenv("SYNTHETIC_DATA_DIR", str(out))
    return out


def test_a_live_dataset_refuses_a_public_host(
    live_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", PUBLIC)
    with pytest.raises(RuntimeError, match="is live data"):
        state.load_market()


def test_a_live_dataset_refuses_lambda_even_with_no_data_mode_set(
    live_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The hole this closes: `make dev` instead of `make dev-live` leaves DATA_MODE unset, so
    # the settings guard never fires and real prices used to be served regardless.
    monkeypatch.delenv("DATA_MODE", raising=False)
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "swing-scan-api")
    monkeypatch.setattr("sys.argv", UVICORN)
    with pytest.raises(RuntimeError, match="refusing to start"):
        state.load_market()


def test_a_live_dataset_loads_on_your_own_machine(
    live_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.setattr("sys.argv", UVICORN)
    market = state.load_market()
    assert market is not None and market.meta.data_mode == "live"


def test_health_reports_the_datasets_own_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.main import app

    monkeypatch.setattr(state, "market", live_market())
    with TestClient(app) as client:
        assert client.get("/api/v1/health").json()["data_mode"] == "live"
