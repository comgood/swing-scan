"""Public use cases, the application layer. Acceptance tests call only these (spec 0002).

Parts of `backtest` whose scope feature has not landed raise `NotYetImplemented`, which the
API maps to 501. A stray `NotImplementedError` from a real bug stays a 500.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np
import polars as pl
from pydantic import ValidationError
from pydantic_core import PydanticCustomError

from .contracts import (
    TEMPLATES,
    Assumptions,
    BacktestRequest,
    BacktestResponse,
    BenchmarkMetrics,
    BenchmarkSplit,
    IndOperand,
    Market,
    Point,
    PortfolioMetrics,
    PortfolioResult,
    PortfolioSplit,
    Rule,
    ScanRequest,
    ScanResponse,
    ScanRow,
    Trial,
    scan_columns,
)
from .contracts._errors import error_at
from .contracts.trial import pair_key, structure_key
from .exits import build_exits
from .indicators import IndicatorKey, cache_for, dependencies, key_of
from .indicators.compute import POS
from .rules import COOLDOWN, compile_rule, entry_signals, operand_values
from .sim import START_EQUITY, BarArrays, make_trade, run_portfolio, signal_sessions

FEATURE_NAMES = {
    7: "Synthetic market",
    8: "Template scan",
    9: "Portfolio backtest core",
    11: "Exit types",
    12: "Exit lab",
}


class NotYetImplemented(Exception):
    """A use case whose scope feature has not landed yet."""

    def __init__(self, feature: int, what: str) -> None:
        self.feature = feature
        name = FEATURE_NAMES.get(feature, "a later feature")
        super().__init__(
            f"{what} is not implemented yet; it arrives with scope feature {feature} ({name})."
        )


VOL_RATIO_KEY = IndicatorKey("avg_volume", 50)
"""`vol_ratio` is `volume / avg_volume(50)` (spec 0002 value sourcing)."""


@dataclass(frozen=True)
class ScanTiming:
    """What one scan did, for the API's scan log line (spec 0005, AC-8)."""

    duration_ms: float
    n_conditions: int
    n_rows: int
    cache: Literal["warm", "cold"]
    """`warm` when every column the scan reads was already cached."""
    as_of: date


def _distinct_operands(rule: Rule) -> list[IndOperand]:
    """Indicator operands deduped by `(ind, n, offset, mult)`, in `scan_columns` order."""
    seen: dict[tuple[str, int | None, int, float], IndOperand] = {}
    for condition in rule.conditions:
        for operand in (condition.left, condition.right):
            if isinstance(operand, IndOperand):
                seen.setdefault((operand.ind, operand.n, operand.offset, operand.mult), operand)
    return list(seen.values())


def columns_read(rule: Rule) -> list[IndicatorKey]:
    """Every cached column a scan of `rule` reads: its operands, `ret(n)` under each `rs(n)`,
    and `avg_volume(50)` for `vol_ratio`."""
    keys = [key_of(operand) for operand in _distinct_operands(rule)] + [VOL_RATIO_KEY]
    return list(dict.fromkeys(dependencies(keys)))


def as_of_not_session(as_of: date, first: date, last: date) -> ValidationError:
    """The 422 for an `as_of` that is not a session, located at `as_of` (spec 0005, AC-6)."""
    error = PydanticCustomError(
        "as_of_not_session",
        "as_of must be a session between {min} and {max}",
        {"min": first.isoformat(), "max": last.isoformat()},
    )
    return error_at(("as_of",), error, as_of.isoformat())


def warm(market: Market) -> None:
    """Compute and pin every column the templates read, so their scans start warm (AC-7)."""
    keys = [key for template in TEMPLATES for key in columns_read(template.rule)]
    cache_for(market).pin(keys)


def scan_timed(request: ScanRequest, market: Market) -> tuple[ScanResponse, ScanTiming]:
    """`scan`, plus what it did. Raises the `as_of_not_session` `ValidationError`."""
    started = time.perf_counter()
    cache = cache_for(market)
    first, last = cache.sessions[0], cache.sessions[-1]
    as_of = request.as_of if request.as_of is not None else last
    if as_of not in cache.session_set:
        raise as_of_not_session(as_of, first, last)
    state: Literal["warm", "cold"] = (
        "warm" if all(key in cache for key in columns_read(request.rule)) else "cold"
    )

    compiled = compile_rule(request.rule, cache)
    signals = entry_signals(
        cache.pos, cache.is_last, compiled.valid, compiled.value, ignore_last_bar=True
    )
    operands = _distinct_operands(request.rule)
    average_volume = cache.get(VOL_RATIO_KEY)
    frame = cache.bars.select("ticker", "date", "close", "volume", POS).with_columns(
        compiled.value.alias("_hit"),
        signals.alias("new_today"),
        average_volume.alias("_avg_volume"),
        *(operand_values(op, cache).alias(f"_op{i}") for i, op in enumerate(operands)),
    )
    hits = (
        frame.with_columns(
            # The previous row of the same ticker; null on its first bar.
            pl.when(pl.col(POS) >= 1)
            .then((pl.col("close") / pl.col("close").shift(1) - 1) * 100)
            .alias("chg_pct"),
            # Null while the average warms up, and when it is 0 (never infinite).
            pl.when(pl.col("_avg_volume") != 0)
            .then(pl.col("volume") / pl.col("_avg_volume"))
            .alias("vol_ratio"),
        )
        .filter((pl.col("date") == as_of) & (pl.col("ticker") != cache.benchmark) & pl.col("_hit"))
        .sort(["new_today", "ticker"], descending=[True, False])
    )
    op_columns = [f"_op{i}" for i in range(len(operands))]
    rows = [
        ScanRow(
            ticker=row["ticker"],
            close=row["close"],
            chg_pct=row["chg_pct"],
            vol_ratio=row["vol_ratio"],
            operands=[row[c] for c in op_columns],
            new_today=row["new_today"],
        )
        for row in hits.iter_rows(named=True)
    ]
    response = ScanResponse(as_of=as_of, columns=scan_columns(request.rule), rows=rows)
    timing = ScanTiming(
        duration_ms=(time.perf_counter() - started) * 1000,
        n_conditions=len(request.rule.conditions),
        n_rows=len(rows),
        cache=state,
        as_of=as_of,
    )
    return response, timing


def scan(request: ScanRequest, market: Market) -> ScanResponse:
    """Tickers alive on `as_of`, not the benchmark, whose rule is valid and true (S-1, S-2).

    `as_of` defaults to the last session; one that is not a session raises the
    `as_of_not_session` `ValidationError`. `new_today` is the shared entry signal on `as_of`
    with only the last bar term ignored (S-3). `chg_pct` uses the ticker's previous row and
    `vol_ratio` is null when `avg_volume(50)` is null or 0. Rows are sorted new first, then
    ticker A to Z. Values are unrounded.
    """
    return scan_timed(request, market)[0]


MAX_POINTS = 500
MAX_TRADES = 2000
OOS_FRACTION = 0.3


def thin(n: int, limit: int = MAX_POINTS) -> list[int]:
    """Indexes 0, k, 2k, … plus the last, k = ceil(n / limit), so at most `limit` points."""
    if n == 0:
        return []
    k = math.ceil(n / limit)
    picked = list(range(0, n, k))
    if picked[-1] != n - 1:
        picked.append(n - 1)
    return picked[-limit:] if len(picked) > limit else picked


def _empty_metrics(n_trades: int) -> PortfolioMetrics:
    """Trade counts only; the metric formulas arrive with spec 0007 BE milestone 3."""
    return PortfolioMetrics(
        n_trades=n_trades,
        cagr_pct=None,
        max_dd_pct=None,
        sharpe=None,
        win_rate_pct=None,
        avg_win_pct=None,
        avg_loss_pct=None,
        expectancy_pct=None,
        expectancy_r=None,
        profit_factor=None,
        avg_bars_held=None,
        exposure_pct=None,
    )


def _portfolio(request: BacktestRequest, market: Market) -> PortfolioResult:
    config = request.configs[0]
    sim = request.sim
    slip = sim.slippage_bps / 10_000
    cache = cache_for(market)
    bars = BarArrays.build(market, cache)
    exits = build_exits(config, cache.get)

    compiled = compile_rule(request.rule, cache)
    signals = entry_signals(cache.pos, cache.is_last, compiled.valid, compiled.value)
    universe = (cache.bars["ticker"] != cache.benchmark).to_numpy()
    signal_rows = np.flatnonzero(signals.to_numpy() & universe)

    benchmark = cache.bars.filter(pl.col("ticker") == cache.benchmark).sort("date")
    sessions: list[date] = benchmark["date"].to_list()
    session_index = {day: i for i, day in enumerate(sessions)}
    rs126 = cache.get(IndicatorKey("rs", 126)).fill_null(float("nan")).to_numpy()
    run = run_portfolio(
        sessions,
        signal_sessions(signal_rows, bars, session_index),
        rs126,
        bars,
        exits,
        sim.max_positions,
        slip,
    )

    oos_start = sessions[math.floor((1 - OOS_FRACTION) * len(sessions))]
    trades = sorted(
        (
            make_trade(
                t.position, t.fill, bars.date[t.entry_row], bars.date[t.exit_row], slip, oos_start
            )
            for t in run.trades
        ),
        key=lambda t: (t.entry_date, t.ticker),
    )
    closes = benchmark["close"].to_list()
    points = thin(len(sessions))
    n_oos = sum(t.segment == "oos" for t in trades)
    no_benchmark = BenchmarkMetrics(cagr_pct=None, max_dd_pct=None)
    assumptions = Assumptions(
        fill_model="signal_close_entry_next_open",
        slippage_bps=sim.slippage_bps,
        commission_bps=0,
        sizing="equal_weight",
        max_positions=sim.max_positions,
        entry_rising_edge=True,
        cooldown_bars=COOLDOWN,
        cooldown_basis="signal",
        no_last_bar_entry=True,
        same_ticker_overlap=False,
        horizon_bars=None,
        seed=None,
        configs=[config],
        baseline_config_index=0,
        delisting_rule="exit_last_close",
        oos_start=oos_start,
        oos_fraction=OOS_FRACTION,
        data_mode=market.meta.data_mode,
        data_version=market.meta.data_version,
        data_seed=market.meta.seed,
    )
    return PortfolioResult(
        mode="portfolio",
        assumptions=assumptions,
        oos_start=oos_start,
        trial=Trial(
            structure_key=structure_key(request.rule),
            pair_keys=[pair_key(request.rule, config)],
        ),
        warnings=[],
        metrics=PortfolioSplit(is_=_empty_metrics(len(trades) - n_oos), oos=_empty_metrics(n_oos)),
        benchmark_metrics=BenchmarkSplit(is_=no_benchmark, oos=no_benchmark),
        equity=[Point(date=sessions[i], value=run.equity[i]) for i in points],
        benchmark=[
            Point(date=sessions[i], value=closes[i] / closes[0] * START_EQUITY) for i in points
        ],
        trades=trades[-MAX_TRADES:],
        trades_total=len(trades),
        trades_truncated=len(trades) > MAX_TRADES,
    )


def backtest(request: BacktestRequest, market: Market) -> BacktestResponse:
    """1 config runs the portfolio day loop (feature 9); 2 to 6 configs are the exit lab,
    which answers `NotYetImplemented` until feature 12. Exit types feature 11 builds answer
    `NotYetImplemented` too."""
    if len(request.configs) > 1:
        raise NotYetImplemented(12, "Trade mode (the exit lab)")
    return _portfolio(request, market)
