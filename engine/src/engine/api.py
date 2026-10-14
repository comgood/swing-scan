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
import numpy.typing as npt
import polars as pl
from pydantic import ValidationError
from pydantic_core import PydanticCustomError

from .baseline import eligible_pool, sample
from .contracts import (
    TEMPLATES,
    Assumptions,
    BacktestRequest,
    BacktestResponse,
    BenchmarkMetrics,
    BenchmarkSplit,
    ConfigRow,
    EdgeSplit,
    Entries,
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
    Trade,
    TradeLabResult,
    TradeSplit,
    Trial,
    entries_hash,
    scan_columns,
)
from .contracts import (
    Warning as ResultWarning,
)
from .contracts._errors import error_at
from .contracts.trial import pair_key, structure_key
from .exits import build_exits
from .indicators import IndicatorKey, cache_for, dependencies, key_of
from .indicators.cache import IndicatorCache
from .indicators.compute import POS
from .metrics import (
    CurveStats,
    best_is,
    curve_stats,
    distinct_weeks,
    edge,
    even_spread,
    exposure_pct,
    guides_is,
    over_horizon_limit,
    thin,
    trade_metrics,
    trade_stats,
)
from .rules import COOLDOWN, compile_rule, entry_signals, operand_values
from .sim import (
    START_EQUITY,
    BarArrays,
    entry_points,
    make_trade,
    run_portfolio,
    run_trade_mode,
    signal_sessions,
)

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


MAX_TRADES = 2000
OOS_FRACTION = 0.3


def range_outside_data(
    field: Literal["start", "end"], value: date, first: date, last: date
) -> ValidationError:
    """The 422 for a `sim.start` or `sim.end` outside the data's sessions (spec 0002)."""
    error = PydanticCustomError(
        "range_outside_data",
        f"{field} must be between {{min}} and {{max}}",
        {"min": first.isoformat(), "max": last.isoformat()},
    )
    return error_at(("sim", field), error, value.isoformat())


def no_session_in_window(start: date, end: date, first: date, last: date) -> ValidationError:
    """The 422 for a window inside the data that holds no session (a weekend, a holiday)."""
    error = PydanticCustomError(
        "range_outside_data",
        f"no session between start {start.isoformat()} and end {end.isoformat()}; "
        "the data runs from {min} to {max}",
        {"min": first.isoformat(), "max": last.isoformat()},
    )
    return error_at(("sim", "start"), error, start.isoformat())


REQUEST_ERRORS = frozenset({"range_outside_data", "as_of_not_session"})
"""The `ValidationError` types the use cases raise about the request (422s, spec 0002). Any
other `ValidationError` out of a use case is an engine bug building the response (a 500)."""


def _cut(market: Market, end: date) -> Market:
    """The market with every bar after `end` removed, so nothing later is read (B-10)."""
    return Market(
        bars=market.bars.filter(pl.col("date") <= end),
        securities=market.securities,
        meta=market.meta,
    )


def _window(market: Market, start: date | None, end: date | None) -> tuple[Market, list[date]]:
    """The market cut at `end` and the window's sessions (benchmark dates in [start, end]).

    Raises `range_outside_data` when `start` or `end` lies outside the data, or the window
    holds no session. Indicators still warm up on the bars before `start`. The market is
    also cut at the last session, so no bar dated after it reaches the loop.
    """
    full = cache_for(market)
    first, last = full.sessions[0], full.sessions[-1]
    if start is not None and not first <= start <= last:
        raise range_outside_data("start", start, first, last)
    if end is not None and not first <= end <= last:
        raise range_outside_data("end", end, first, last)
    if end is not None and end < last:
        market = _cut(market, end)
    dates = cache_for(market).bars.filter(pl.col("ticker") == market.meta.benchmark)["date"]
    sessions = [day for day in dates.sort().to_list() if start is None or day >= start]
    if not sessions:
        raise no_session_in_window(start or first, end or last, first, last)
    if market.bars["date"].max() != sessions[-1]:
        # A bar after the benchmark's last session would never be stepped; cut it like `end`.
        market = _cut(market, sessions[-1])
    return market, sessions


def _signal_rows(rule: Rule, cache: IndicatorCache) -> npt.NDArray[np.int64]:
    """Rows of the shared entry signals (S-3), benchmark excluded, in `market.bars` order."""
    compiled = compile_rule(rule, cache)
    signals = entry_signals(cache.pos, cache.is_last, compiled.valid, compiled.value)
    universe = (cache.bars["ticker"] != cache.benchmark).to_numpy()
    return np.flatnonzero(signals.to_numpy() & universe)


def _oos_split(sessions: list[date]) -> int:
    """Index of the first OOS session: the last 30% of the window's sessions."""
    return math.floor((1 - OOS_FRACTION) * len(sessions))


def _metrics(trades: list[Trade], curve: CurveStats, invested: list[float]) -> PortfolioMetrics:
    stats = trade_stats(trades)
    return PortfolioMetrics(
        n_trades=stats.n_trades,
        cagr_pct=curve.cagr_pct,
        max_dd_pct=curve.max_dd_pct,
        sharpe=curve.sharpe,
        win_rate_pct=stats.win_rate_pct,
        avg_win_pct=stats.avg_win_pct,
        avg_loss_pct=stats.avg_loss_pct,
        expectancy_pct=stats.expectancy_pct,
        expectancy_r=stats.expectancy_r,
        profit_factor=stats.profit_factor,
        avg_bars_held=stats.avg_bars_held,
        exposure_pct=exposure_pct(invested),
    )


def _split_curve(curve: list[float], at: int) -> tuple[CurveStats, CurveStats]:
    """IS and OOS curve stats of one continuous curve that starts from `START_EQUITY`."""
    head, tail = curve[:at], curve[at:]
    before = head[-1] if head else START_EQUITY
    return (
        curve_stats(head, START_EQUITY, START_EQUITY),
        curve_stats(tail, before, max([START_EQUITY, *head])),
    )


def _warnings(n_trades: int) -> list[ResultWarning]:
    warnings: list[ResultWarning] = []
    if n_trades == 0:
        warnings.append(
            ResultWarning(
                code="no_entries",
                config_index=0,
                message=(
                    "No entries: the rule never produced a signal that could be filled in "
                    "this window, so there are no trades and no metrics to show."
                ),
            )
        )
    if n_trades > MAX_TRADES:
        warnings.append(
            ResultWarning(
                code="trades_truncated",
                config_index=None,
                message=(
                    f"Showing the latest 2,000 trades of {n_trades:,}. "
                    "The metrics above use all of them."
                ),
            )
        )
    return warnings


def _portfolio(request: BacktestRequest, market: Market) -> PortfolioResult:
    config = request.configs[0]
    sim = request.sim
    slip = sim.slippage_bps / 10_000
    market, sessions = _window(market, sim.start, sim.end)
    cache = cache_for(market)
    bars = BarArrays.build(market, cache)
    exits = build_exits(config, cache.get)

    signal_rows = _signal_rows(request.rule, cache)
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

    split = _oos_split(sessions)
    oos_start = sessions[split]
    trades = sorted(
        (
            make_trade(
                t.position, t.fill, bars.date[t.entry_row], bars.date[t.exit_row], slip, oos_start
            )
            for t in run.trades
        ),
        key=lambda t: (t.entry_date, t.ticker),
    )
    benchmark = cache.bars.filter(
        (pl.col("ticker") == cache.benchmark) & pl.col("date").is_in(sessions)
    ).sort("date")
    bench_closes = benchmark["close"].to_list()
    bench_curve = [close / bench_closes[0] * START_EQUITY for close in bench_closes]

    is_curve, oos_curve = _split_curve(run.equity, split)
    is_bench, oos_bench = _split_curve(bench_curve, split)
    is_trades = [t for t in trades if t.segment == "is"]
    oos_trades = [t for t in trades if t.segment == "oos"]
    points = thin(len(sessions))
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
        warnings=_warnings(len(trades)),
        metrics=PortfolioSplit(
            is_=_metrics(is_trades, is_curve, run.invested[:split]),
            oos=_metrics(oos_trades, oos_curve, run.invested[split:]),
        ),
        benchmark_metrics=BenchmarkSplit(
            is_=BenchmarkMetrics(cagr_pct=is_bench.cagr_pct, max_dd_pct=is_bench.max_dd_pct),
            oos=BenchmarkMetrics(cagr_pct=oos_bench.cagr_pct, max_dd_pct=oos_bench.max_dd_pct),
        ),
        equity=[Point(date=sessions[i], value=run.equity[i]) for i in points],
        benchmark=[Point(date=sessions[i], value=bench_curve[i]) for i in points],
        trades=trades[-MAX_TRADES:],
        trades_total=len(trades),
        trades_truncated=len(trades) > MAX_TRADES,
    )


def _lab_warnings(
    names: list[str], strategy: list[list[Trade]], n_entries: int, horizon: int
) -> list[ResultWarning]:
    """`no_entries`, then each `horizon_exits_over_10pct` in config order, then
    `trades_truncated` (spec 0009 value sourcing)."""
    warnings: list[ResultWarning] = []
    if n_entries == 0:
        warnings.append(
            ResultWarning(
                code="no_entries",
                config_index=None,
                message=(
                    "No entries: the rule never produced a signal in this window, so there "
                    "are no trades to compare."
                ),
            )
        )
    warnings += [
        ResultWarning(
            code="horizon_exits_over_10pct",
            config_index=i,
            message=(
                f"{names[i]}: more than 10% of these trades were still open at the "
                f"{horizon} bar horizon, so they were closed early and the results are "
                "cut short."
            ),
        )
        for i, trades in enumerate(strategy)
        if over_horizon_limit(trades)
    ]
    baseline_total = len(strategy[0])
    if baseline_total > MAX_TRADES:
        warnings.append(
            ResultWarning(
                code="trades_truncated",
                config_index=None,
                message=(
                    f"Showing 2,000 of the {baseline_total:,} baseline trades. "
                    "The metrics above use all of them."
                ),
            )
        )
    return warnings


def _split(trades: list[Trade]) -> TradeSplit:
    return TradeSplit(
        is_=trade_metrics([t for t in trades if t.segment == "is"]),
        oos=trade_metrics([t for t in trades if t.segment == "oos"]),
    )


def _trade_lab(request: BacktestRequest, market: Market) -> TradeLabResult:
    """Trade mode, the exit lab (spec 0009): one entry list for every config, each entry a
    unit notional trade walked through the config's exits by `walk_trade()` up to the
    horizon, then per trade metrics in IS and OOS columns. A seeded random entry sample with
    the strategy's IS and OOS counts walks the same exits; `edge` is strategy minus random
    (assumed decision 3).
    """
    sim = request.sim
    slip = sim.slippage_bps / 10_000
    market, sessions = _window(market, sim.start, sim.end)
    cache = cache_for(market)
    bars = BarArrays.build(market, cache)
    oos_start = sessions[_oos_split(sessions)]

    session_set = set(sessions)
    signal_rows = [
        r for r in _signal_rows(request.rule, cache).tolist() if bars.date[r] in session_set
    ]
    entries = entry_points(signal_rows, bars, slip, oos_start)
    is_count = sum(e.segment == "is" for e in entries)
    drawn = sample(
        eligible_pool(cache, sessions[0], oos_start),
        is_count,
        len(entries) - is_count,
        sim.seed,
    )
    random_entries = entry_points(drawn.tolist(), bars, slip, oos_start)

    exit_sets = [build_exits(config, cache.get) for config in request.configs]
    runs = run_trade_mode(
        entries, random_entries, exit_sets, bars, sim.horizon_bars, slip, oos_start
    )

    rows = []
    for config, run in zip(request.configs, runs, strict=True):
        strategy, random = _split(run.strategy), _split(run.random)
        rows.append(
            ConfigRow(
                name=config.name,
                strategy=strategy,
                random=random,
                edge=EdgeSplit(
                    is_=edge(strategy.is_, random.is_), oos=edge(strategy.oos, random.oos)
                ),
            )
        )
    baseline = sorted(runs[0].strategy, key=lambda t: (t.entry_date, t.ticker))
    names = [config.name for config in request.configs]
    assumptions = Assumptions(
        fill_model="signal_close_entry_next_open",
        slippage_bps=sim.slippage_bps,
        commission_bps=0,
        sizing="unit_notional",
        max_positions=None,
        entry_rising_edge=True,
        cooldown_bars=COOLDOWN,
        cooldown_basis="signal",
        no_last_bar_entry=True,
        same_ticker_overlap=True,
        horizon_bars=sim.horizon_bars,
        seed=sim.seed,
        configs=list(request.configs),
        baseline_config_index=0,
        delisting_rule="exit_last_close",
        oos_start=oos_start,
        oos_fraction=OOS_FRACTION,
        data_mode=market.meta.data_mode,
        data_version=market.meta.data_version,
        data_seed=market.meta.seed,
    )
    return TradeLabResult(
        mode="trade",
        assumptions=assumptions,
        oos_start=oos_start,
        trial=Trial(
            structure_key=structure_key(request.rule),
            pair_keys=[pair_key(request.rule, config) for config in request.configs],
        ),
        warnings=_lab_warnings(
            names, [run.strategy for run in runs], len(entries), sim.horizon_bars
        ),
        entries=Entries(
            count=len(entries),
            is_count=is_count,
            oos_count=len(entries) - is_count,
            distinct_weeks=distinct_weeks([e.entry_date for e in entries]),
            hash=entries_hash((e.ticker, e.entry_date) for e in entries),
            random_is_count=sum(e.segment == "is" for e in random_entries),
            random_oos_count=sum(e.segment == "oos" for e in random_entries),
        ),
        rows=rows,
        best_is=best_is([row.strategy.is_ for row in rows]),
        guides_is=guides_is([t for t in baseline if t.segment == "is"]),
        baseline_trades=even_spread(baseline, MAX_TRADES),
        baseline_trades_total=len(baseline),
        baseline_trades_truncated=len(baseline) > MAX_TRADES,
    )


def backtest(request: BacktestRequest, market: Market) -> BacktestResponse:
    """1 config runs the portfolio day loop (feature 9); 2 to 6 configs run trade mode, the
    exit lab (feature 12). A `sim.start` or `sim.end` outside the data raises the
    `range_outside_data` `ValidationError`."""
    if len(request.configs) > 1:
        return _trade_lab(request, market)
    return _portfolio(request, market)
