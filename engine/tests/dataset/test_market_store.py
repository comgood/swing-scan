"""The market store: `meta.parquet`, the layout version, the change key and the push script.

Spec 0011. A local directory and an `s3://` prefix go through the same code, so everything
here runs against a directory; the store specific half is the error classification, driven by
the messages Polars raises for a cloud read.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import polars as pl
import pytest

from engine.contracts import Market
from engine.data import SUPPORTED_LAYOUT_VERSION, change_key, read_market, read_meta, write_market
from engine.data.fixtures import FrameSpec, make_market
from engine.data.store import DATASET_FILES, LAYOUT_VERSION_COLUMN, META_FILE, dataset_key

PUSH_SCRIPT = Path(__file__).parents[3] / "scripts" / "push_market.py"

TEST_STORE_ENV = "SWING_SCAN_TEST_STORE_URI"
"""An existing bucket prefix to exercise the `s3://` branch against, MinIO locally.

Absent, that one test skips, the way the saved rules tests skip without a `DATABASE_URL`:
CI stays green and a real run is the evidence.
"""


def tiny() -> Market:
    flat = FrameSpec(1, [10.0] * 40)
    return make_market({"AAA": flat, "DEMO-INDEX": flat})


def live(market: Market) -> Market:
    meta = market.meta.model_copy(update={"data_mode": "live", "seed": None})
    return Market(bars=market.bars, securities=market.securities, meta=meta)


def push(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PUSH_SCRIPT), *args], capture_output=True, text=True, check=False
    )


def test_meta_is_the_last_object_written() -> None:
    # The change key lives in the object written last, so new meta always has new bars behind it.
    assert DATASET_FILES[-1] == META_FILE


def test_meta_parquet_carries_the_layout_version_and_the_change_key(tmp_path: Path) -> None:
    market = tiny()
    write_market(market, tmp_path)
    assert read_meta(tmp_path) == (SUPPORTED_LAYOUT_VERSION, change_key(market.meta))


def test_an_unsupported_layout_version_is_refused_naming_both(tmp_path: Path) -> None:
    write_market(tiny(), tmp_path)
    key = dataset_key(tmp_path, META_FILE)
    pl.read_parquet(key).with_columns(
        pl.lit(SUPPORTED_LAYOUT_VERSION + 1).cast(pl.Int32).alias(LAYOUT_VERSION_COLUMN)
    ).write_parquet(key)
    with pytest.raises(ValueError, match=rf"layout_version {SUPPORTED_LAYOUT_VERSION + 1}") as err:
        read_market(tmp_path)
    assert f"supports layout_version {SUPPORTED_LAYOUT_VERSION}" in str(err.value)


def test_an_absent_dataset_names_the_root_and_how_to_fix_it(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="make data"):
        read_market(tmp_path / "nothing")


def test_new_bars_without_new_meta_leave_the_change_key_alone(tmp_path: Path) -> None:
    # The torn write case: a writer interrupted after bars still advertises the old dataset.
    market = tiny()
    write_market(market, tmp_path)
    bars = dataset_key(tmp_path, DATASET_FILES[0])
    pl.read_parquet(bars).with_columns(pl.col("close") * 2).write_parquet(bars)
    assert read_meta(tmp_path)[1] == change_key(market.meta)


def test_a_404_from_the_store_reads_as_an_absent_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    def not_found(key: str) -> pl.DataFrame:
        raise pl.exceptions.ComputeError(
            f"Object at location {key} not found: Client error with status 404 Not Found"
        )

    monkeypatch.setattr(pl, "read_parquet", not_found)
    with pytest.raises(FileNotFoundError):
        read_market("s3://bucket/synthetic")


def test_access_denied_from_the_store_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # A misconfigured role must fail loudly instead of looking like an empty store.
    def denied(key: str) -> pl.DataFrame:
        raise pl.exceptions.ComputeError(
            "Generic S3 error: Client error with status 403 Forbidden: AccessDenied"
        )

    monkeypatch.setattr(pl, "read_parquet", denied)
    with pytest.raises(pl.exceptions.ComputeError):
        read_market("s3://bucket/synthetic")


def test_push_is_rerunnable(tmp_path: Path) -> None:
    source, dest = tmp_path / "from", tmp_path / "to"
    write_market(tiny(), source / "synthetic")
    first = push("--from", str(source), "--to", str(dest))
    assert first.returncode == 0, first.stderr
    before = {name: dataset_key(dest / "synthetic", name) for name in DATASET_FILES}
    bytes_before = {name: Path(key).read_bytes() for name, key in before.items()}
    assert push("--from", str(source), "--to", str(dest)).returncode == 0
    assert {n: Path(k).read_bytes() for n, k in before.items()} == bytes_before
    assert read_market(dest / "synthetic").meta == tiny().meta


def test_push_refuses_a_live_dataset_without_the_flag(tmp_path: Path) -> None:
    source, dest = tmp_path / "from", tmp_path / "to"
    write_market(live(tiny()), source / "live")
    refused = push("--mode", "live", "--from", str(source), "--to", str(dest))
    assert refused.returncode == 1
    assert "--allow-live" in refused.stderr
    assert not (dest / "live").exists()
    allowed = push("--mode", "live", "--from", str(source), "--to", str(dest), "--allow-live")
    assert allowed.returncode == 0, allowed.stderr
    assert read_market(dest / "live").meta.data_mode == "live"


@pytest.mark.skipif(
    not os.environ.get(TEST_STORE_ENV),
    reason=f"no {TEST_STORE_ENV}: the s3:// branch needs a bucket (MinIO locally, spec 0011)",
)
def test_a_store_and_a_directory_hold_the_same_dataset(tmp_path: Path) -> None:
    store = os.environ[TEST_STORE_ENV]
    write_market(tiny(), tmp_path / "synthetic")
    pushed = push("--from", str(tmp_path), "--to", store)
    assert pushed.returncode == 0, pushed.stderr

    from_store = read_market(dataset_key(store, "synthetic"))
    from_directory = read_market(tmp_path / "synthetic")
    assert from_store.bars.equals(from_directory.bars)
    assert from_store.securities.equals(from_directory.securities)
    assert from_store.meta == from_directory.meta
