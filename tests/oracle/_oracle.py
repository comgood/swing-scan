"""Shared helpers for the backtest correctness oracles (scope feature 6, doc 02 section 7.6).

Drafted by QA from doc 01 section 6.4, doc 02 sections 6 and 7 and spec 0002 only, never from
engine code. The owner recomputes every expected value, then moves this folder to
`tests/oracle/` (see README.md). Expected values are written as arithmetic on the fixture
prices, so each one can be checked by hand.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.api import backtest
from engine.contracts import (
    BacktestRequest,
    BacktestResponse,
    Market,
    PortfolioResult,
    Trade,
    TradeLabResult,
)
from engine.data.fixtures import FrameSpec, bar_date, load_fixture, make_market

FIXTURES = Path(__file__).parent / "fixtures"

# Default slippage is 10 bps per side (spec 0002 SimParams, doc 02 section 7.1).
SLIP_IN = 1.001
SLIP_OUT = 0.999

__all__ = [
    "FIXTURES",
    "SLIP_IN",
    "SLIP_OUT",
    "FrameSpec",
    "bar_date",
    "close_above",
    "config",
    "fixture",
    "ind",
    "lab",
    "make_market",
    "only_trade",
    "portfolio",
    "random_walk_market",
    "rule",
    "val",
]


def ind(name: str, n: int | None = None, offset: int = 0, mult: float = 1.0) -> dict[str, Any]:
    return {"kind": "ind", "ind": name, "n": n, "offset": offset, "mult": mult}


def val(x: float) -> dict[str, Any]:
    return {"kind": "value", "value": x}


def rule(*conditions: tuple[dict[str, Any], str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "name": "oracle",
        "conditions": [{"left": a, "op": op, "right": b} for a, op, b in conditions],
    }


def close_above(level: float) -> dict[str, Any]:
    """The one condition rule most fixtures use: `close > level`."""
    return rule((ind("close"), ">", val(level)))


def config(name: str, *exits: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "exits": list(exits)}


def fixture(name: str) -> Market:
    return load_fixture(FIXTURES / f"{name}.csv")


def _run(
    rule_json: dict[str, Any], configs: Sequence[dict[str, Any]], market: Market, **sim: Any
) -> BacktestResponse:
    request = BacktestRequest.model_validate(
        {"rule": rule_json, "configs": list(configs), "sim": sim}
    )
    return backtest(request, market)


def portfolio(
    rule_json: dict[str, Any], exits: Sequence[dict[str, Any]], market: Market, **sim: Any
) -> PortfolioResult:
    """One config, so portfolio mode (spec 0002, value sourcing `mode`)."""
    result = _run(rule_json, [config("only", *exits)], market, **sim)
    assert isinstance(result, PortfolioResult), result.mode
    return result


def lab(
    rule_json: dict[str, Any], configs: Sequence[dict[str, Any]], market: Market, **sim: Any
) -> TradeLabResult:
    """Two to six configs, so trade mode (the exit lab)."""
    result = _run(rule_json, configs, market, **sim)
    assert isinstance(result, TradeLabResult), result.mode
    return result


def only_trade(trades: Sequence[Trade], ticker: str) -> Trade:
    mine = [t for t in trades if t.ticker == ticker]
    assert len(mine) == 1, f"expected one {ticker} trade, got {len(mine)}"
    return mine[0]


# ------------------------------------------------------------ B-10 random walk market


@dataclass(frozen=True)
class _Walk:
    start_bar: int
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]


def _walk(rng: random.Random, start_bar: int, n: int, drift: float) -> _Walk:
    o, h, lo, c, v = [], [], [], [], []
    price = rng.uniform(30.0, 80.0)
    for _ in range(n):
        open_ = price * (1 + rng.gauss(0, 0.004))
        close = open_ * (1 + rng.gauss(drift, 0.015))
        high = max(open_, close) * (1 + abs(rng.gauss(0, 0.006)))
        low = min(open_, close) * (1 - abs(rng.gauss(0, 0.006)))
        spike = 3.0 if rng.random() < 0.08 else 1.0
        o.append(round(open_, 4))
        h.append(round(high, 4))
        lo.append(round(low, 4))
        c.append(round(close, 4))
        v.append(float(round(rng.uniform(800_000, 1_200_000) * spike)))
        price = close
    return _Walk(start_bar, o, h, lo, c, v)


def _poison(rng: random.Random, walk: _Walk, after_bar: int) -> _Walk:
    """Replace every bar after `after_bar` with valid but unrelated garbage."""
    o, h, lo, c, v = (list(x) for x in (walk.open, walk.high, walk.low, walk.close, walk.volume))
    for i in range(len(o)):
        if walk.start_bar + i <= after_bar:
            continue
        a, b = rng.uniform(1.0, 500.0), rng.uniform(1.0, 500.0)
        o[i], c[i] = round(a, 4), round(b, 4)
        h[i] = round(max(a, b) * rng.uniform(1.0, 1.5), 4)
        lo[i] = round(min(a, b) * rng.uniform(0.5, 1.0), 4)
        v[i] = float(round(rng.uniform(1.0, 50_000_000.0)))
    return _Walk(walk.start_bar, o, h, lo, c, v)


def random_walk_market(
    *, seed: int, tickers: int, bars: int, poison_after: int | None = None
) -> Market:
    """A seeded market: most tickers live throughout, some list late, some delist early.

    With `poison_after`, every bar after that bar is garbage; bars up to it are identical
    to the clean market from the same seed (B-10).
    """
    rng = random.Random(seed)  # noqa: S311 (test data, not security)
    garbage = random.Random(seed + 1)  # noqa: S311 (test data, not security)
    frames: dict[str, FrameSpec] = {}
    for k in range(tickers):
        start = 1 if k % 5 else rng.randint(2, 120)  # every fifth ticker lists late
        end = bars if k % 7 else rng.randint(300, bars - 1)  # every seventh delists
        walk = _walk(rng, start, end - start + 1, drift=rng.uniform(-0.0005, 0.0015))
        if poison_after is not None:
            walk = _poison(garbage, walk, poison_after)
        frames[f"RW{k:02d}"] = FrameSpec(
            start_bar=walk.start_bar,
            close=walk.close,
            open=walk.open,
            high=walk.high,
            low=walk.low,
            volume=walk.volume,
        )
    return make_market(frames, end_bar=bars)
