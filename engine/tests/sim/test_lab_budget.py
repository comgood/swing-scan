"""The X-7 time budget on the seed 42 market (spec 0009, AC-11 and assumed decision 11).

"Warm" is the second of two identical calls in one process: the first pays for indicators and
the cache, the second is what a warm Lambda answers. It must finish, serialization included,
in under 10 s with a body under 6 MB. A hard gate locally; on CI (shared runners are noisy) a
slow run only warns, while the body size and the identical bodies still fail.
"""

from __future__ import annotations

import os
import time
import warnings
from typing import Any

import pytest

from engine import api
from engine.contracts import TEMPLATES, BacktestRequest, Market, TradeLabResult
from engine.synthetic import generate

BUDGET_S = 10.0
MAX_BODY_BYTES = 6_000_000

# The five default configs of the lab (backtest.trade_lab.json) plus a sixth, every exit type.
SIX_CONFIGS: list[dict[str, Any]] = [
    {"name": "Baseline", "exits": [{"type": "stop_pct", "pct": 8}, {"type": "time", "bars": 20}]},
    {
        "name": "ATR stop and target",
        "exits": [
            {"type": "stop_atr", "k": 2, "n": 14},
            {"type": "target", "pct": 15},
            {"type": "time", "bars": 30},
        ],
    },
    {"name": "MA exit, no stop", "exits": [{"type": "close_below_ma", "ma": "ema", "n": 21}]},
    {
        "name": "Trailing 10%",
        "exits": [{"type": "trail_pct", "pct": 10}, {"type": "time", "bars": 40}],
    },
    {"name": "Wide target, no stop", "exits": [{"type": "target", "pct": 60}]},
    {
        "name": "Stop, target, time",
        "exits": [
            {"type": "stop_pct", "pct": 5},
            {"type": "target", "pct": 10},
            {"type": "time", "bars": 15},
        ],
    },
]


@pytest.fixture(scope="module")
def seed_42() -> Market:
    return generate(42)


def _timed(request: BacktestRequest, market: Market) -> tuple[float, TradeLabResult, str]:
    started = time.perf_counter()
    result = api.backtest(request, market)
    body = result.model_dump_json(by_alias=True)
    assert isinstance(result, TradeLabResult)
    return time.perf_counter() - started, result, body


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.id)
def test_six_configs_and_the_baseline_answer_warm_within_budget(
    template: Any, seed_42: Market
) -> None:  # covers: AC-11, AC-12
    request = BacktestRequest.model_validate({"rule": template.rule, "configs": SIX_CONFIGS})
    _, _, cold_body = _timed(request, seed_42)
    seconds, result, body = _timed(request, seed_42)

    print(
        f"\nX-7 {template.id}: warm {seconds:.2f} s, body {len(body) / 1000:.0f} KB, "
        f"{result.entries.count} strategy and "
        f"{result.entries.random_is_count + result.entries.random_oos_count} random entries"
    )
    assert body == cold_body, "two identical requests must give identical bodies"
    assert len(body.encode()) < MAX_BODY_BYTES
    assert result.entries.count > 0
    assumptions = result.assumptions
    assert assumptions.sizing == "unit_notional"
    assert assumptions.same_ticker_overlap is True
    assert assumptions.max_positions is None
    assert assumptions.horizon_bars == request.sim.horizon_bars
    assert assumptions.seed == request.sim.seed
    assert assumptions.configs == list(request.configs)
    assert assumptions.baseline_config_index == 0
    if seconds >= BUDGET_S:
        message = f"X-7 missed for {template.id}: warm {seconds:.2f} s >= {BUDGET_S} s"
        if os.environ.get("CI"):
            warnings.warn(message, stacklevel=1)
        else:
            pytest.fail(message)
