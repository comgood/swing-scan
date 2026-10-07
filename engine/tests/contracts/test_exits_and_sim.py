"""AC-3 and AC-4: bad exit setups and sim settings fail with a path and the range."""

from __future__ import annotations

from typing import Any

import pytest

from engine.contracts import BacktestRequest, ExitConfig, SimParams

from .conftest import errors_of, only_error, rule

STOP = {"type": "stop_pct", "pct": 8}


def request(configs: list[dict[str, Any]], **sim: Any) -> dict[str, Any]:
    return {"rule": rule(), "configs": configs, "sim": sim}


def config(name: str = "Baseline", exits: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"name": name, "exits": [STOP] if exits is None else exits}


@pytest.mark.parametrize("count", [0, 7])
def test_config_count_must_be_1_to_6(count: int) -> None:
    configs = [config(f"C{i}") for i in range(count)]
    error = only_error(BacktestRequest, request(configs))
    assert error["loc"] == ("configs",)
    assert error["ctx"] == {"min": 1, "max": 6}


@pytest.mark.parametrize(
    ("exit_", "field", "bounds"),
    [
        ({"type": "stop_pct", "pct": 31}, "pct", (1, 30)),
        ({"type": "stop_atr", "k": 0.4}, "k", (0.5, 6)),
        ({"type": "stop_atr", "n": 51}, "n", (2, 50)),
        ({"type": "target", "pct": 101}, "pct", (1, 100)),
        ({"type": "trail_pct", "pct": 1}, "pct", (2, 30)),
        ({"type": "close_below_ma", "n": 4}, "n", (5, 200)),
        ({"type": "time", "bars": 121}, "bars", (1, 120)),
    ],
)
def test_exit_params_out_of_range(
    exit_: dict[str, Any], field: str, bounds: tuple[float, float]
) -> None:
    error = only_error(ExitConfig, config(exits=[exit_]))
    assert error["type"] == "out_of_range"
    assert error["loc"] == ("exits", 0, exit_["type"], field)
    assert error["ctx"] == {"min": bounds[0], "max": bounds[1]}


def test_bad_ma_type_lists_the_allowed_values() -> None:
    bad: dict[str, Any] = {"type": "close_below_ma", "ma": "wma"}
    error = only_error(ExitConfig, config(exits=[bad]))
    assert error["type"] == "literal_error"


def test_exit_count_must_be_1_to_6() -> None:
    error = only_error(ExitConfig, config(exits=[]))
    assert error["loc"] == ("exits",)
    assert error["ctx"] == {"min": 1, "max": 6}


def test_duplicate_exit_type_points_at_the_duplicate() -> None:
    exits: list[dict[str, Any]] = [STOP, {"type": "time"}, {"type": "stop_pct", "pct": 5}]
    error = only_error(BacktestRequest, request([config(exits=exits)]))
    assert error["type"] == "duplicate_exit_type"
    assert error["loc"] == ("configs", 0, "exits", 2, "type")


def test_duplicate_config_name_points_at_the_duplicate() -> None:
    error = only_error(BacktestRequest, request([config("A"), config("B"), config(" A ")]))
    assert error["type"] == "duplicate_config_name"
    assert error["loc"] == ("configs", 2, "name")


@pytest.mark.parametrize("name", ["", "x" * 41])
def test_config_name_length(name: str) -> None:
    error = only_error(ExitConfig, config(name))
    assert error["loc"] == ("name",)
    assert error["ctx"] == {"min": 1, "max": 40}


@pytest.mark.parametrize(
    ("field", "value", "bounds"),
    [
        ("max_positions", 0, (1, 20)),
        ("max_positions", 21, (1, 20)),
        ("slippage_bps", 51, (0, 50)),
        ("horizon_bars", 4, (5, 252)),
        ("seed", -1, (0, 2**31 - 1)),
        ("seed", 2**31, (0, 2**31 - 1)),
    ],
)
def test_sim_ranges(field: str, value: int, bounds: tuple[int, int]) -> None:
    error = only_error(SimParams, {field: value})
    assert error["type"] == "out_of_range"
    assert error["loc"] == (field,)
    assert error["ctx"] == {"min": bounds[0], "max": bounds[1]}


@pytest.mark.parametrize(
    ("start", "end"), [("2024-01-02", "2024-01-02"), ("2024-02-01", "2024-01-02")]
)
def test_start_must_be_before_end(start: str, end: str) -> None:
    error = only_error(SimParams, {"start": start, "end": end})
    assert error["type"] == "end_not_after_start"
    assert error["loc"] == ("end",)


@pytest.mark.parametrize(
    "bad", ["2024/01/02", "02-01-2024", "2024-1-2", 1704153600, "2024-01-02T00:00:00"]
)
@pytest.mark.parametrize("field", ["start", "end"])
def test_malformed_dates_are_rejected(field: str, bad: Any) -> None:
    errors = errors_of(SimParams, {field: bad})
    assert errors[0]["loc"] == (field,)


def test_omitted_sim_takes_every_default() -> None:
    parsed = BacktestRequest.model_validate({"rule": rule(), "configs": [config()]})
    assert parsed.sim == SimParams(max_positions=10, slippage_bps=10, horizon_bars=60, seed=42)
