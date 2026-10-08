"""`scripts/check_synthetic.py`, the `make data-check` CI gate for D-1 to D-3 (spec 0006).

The script must fail CI when the generator stops being deterministic or loses its planted
delistings, so both failure paths are proven here with small, fast markets.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from engine.contracts import Market
from engine.synthetic import SyntheticConfig, generate

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_synthetic.py"
SMALL = SyntheticConfig(n_tickers=30, n_sessions=320, min_delisted=3)


@pytest.fixture
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_synthetic", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_passes_on_the_real_seed_42_market(
    script: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:  # D-1, D-2, D-3
    assert script.main() == 0
    out = capsys.readouterr().out
    assert "bars.parquet:" in out
    assert "delisted tickers" in out


def test_fails_when_two_builds_differ(
    script: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:  # D-1
    seeds = iter([1, 2])

    def drifting(seed: int) -> Market:
        return generate(next(seeds), SMALL)

    monkeypatch.setattr(script, "generate", drifting)
    assert script.main() == 1
    assert "D-1: bars.parquet differs" in capsys.readouterr().err


def test_fails_with_fewer_than_20_delistings(
    script: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:  # D-3
    monkeypatch.setattr(script, "generate", lambda seed: generate(seed, SMALL))
    assert script.main() == 1
    assert "D-3: only 3 delisted tickers" in capsys.readouterr().err
