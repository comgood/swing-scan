"""Write every mock in `contracts/mocks/` (`make mocks`, spec 0002 AC-12).

Mocks are real contract models filled from a seeded generator (seed 42), never from market
data, so they are safe to commit (D-6). Counts and rates agree with the trades they
summarise. Each 422 and 501 mock is a real response from the app through `TestClient`.
Every float is rounded to 6 places so the output is byte identical on macOS and Linux.
"""

from __future__ import annotations

import json
import math
import random
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pydantic import BaseModel, TypeAdapter

from api.main import app
from engine.contracts import (
    CONTRACT_VERSION,
    INDICATOR_SPECS,
    TEMPLATES,
    Assumptions,
    BenchmarkMetrics,
    BenchmarkSplit,
    BestIs,
    ConfigRow,
    DataMeta,
    EdgeMetrics,
    EdgeSplit,
    Entries,
    ExitConfig,
    ExitReason,
    Guides,
    IndicatorSpec,
    MetaResponse,
    Point,
    PortfolioMetrics,
    PortfolioResult,
    PortfolioSplit,
    Rule,
    ScanResponse,
    ScanRow,
    TemplateOut,
    Trade,
    TradeLabResult,
    TradeMetrics,
    TradeSplit,
    Trial,
    Warning,
    entries_hash,
    pair_key,
    scan_columns,
    structure_key,
)

OUT = Path(__file__).resolve().parents[1] / "contracts" / "mocks"
SEED = 42
OOS_FRACTION = 0.3
SLIPPAGE_BPS = 10.0
HORIZON = 60
TRADE_CAP = 2000
POINT_CAP = 500

BENCHMARK = "SYN-INDEX"
TICKERS = [f"SYN{i:03d}" for i in range(1, 501)]


def weekdays(start: date, end: date) -> list[date]:
    days = (end - start).days + 1
    return [d for d in (start + timedelta(i) for i in range(days)) if d.weekday() < 5]


SESSIONS = weekdays(date(2021, 1, 4), date(2025, 12, 31))
OOS_INDEX = int(len(SESSIONS) * (1 - OOS_FRACTION))
OOS_START = SESSIONS[OOS_INDEX]

META = DataMeta(
    data_mode="synthetic",
    seed=SEED,
    data_version=f"synthetic:v1:seed{SEED}",
    start=SESSIONS[0],
    end=SESSIONS[-1],
    n_tickers=len(TICKERS),
    survivors_only=False,
    benchmark=BENCHMARK,
)


# ---- Output ----------------------------------------------------------------------------


def rounded(value: Any) -> Any:
    if isinstance(value, float):
        r = round(value, 6)
        return 0.0 if r == 0 else r  # no "-0.0"
    if isinstance(value, list):
        return [rounded(v) for v in value]
    if isinstance(value, dict):
        return {k: rounded(v) for k, v in value.items()}
    return value


def write(name: str, payload: Any) -> None:
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="json")
    text = json.dumps(rounded(payload), indent=2, ensure_ascii=False) + "\n"
    (OUT / name).write_text(text)
    print(f"  {name}")


def dump_list(model: type[BaseModel], items: Sequence[BaseModel]) -> Any:
    return TypeAdapter(list[model]).dump_python(list(items), mode="json")  # type: ignore[valid-type]


# ---- Trade and metric helpers ----------------------------------------------------------


@dataclass(frozen=True)
class Move:
    """One entry's underlying price path, shared by every config so configs correlate."""

    ticker: str
    entry_index: int
    ret_pct: float
    mae_pct: float
    mfe_pct: float
    bars: int


def random_move(rng: random.Random, ticker: str, entry_index: int, drift: float) -> Move:
    ret = rng.gauss(drift, 9)
    mae = min(0.0, ret, -abs(rng.gauss(4, 3)))
    mfe = max(0.0, ret, abs(rng.gauss(6, 4)))
    return Move(ticker, entry_index, ret, mae, mfe, rng.randint(3, 58))


def stop_level(config: ExitConfig) -> float | None:
    """The tightest initial stop distance in percent (ATR stops modelled as 3 x k)."""
    levels = []
    for exit_ in config.exits:
        if exit_.type in ("stop_pct", "trail_pct"):
            levels.append(exit_.pct)
        elif exit_.type == "stop_atr":
            levels.append(3 * exit_.k)
    return min(levels) if levels else None


def apply_exits(
    move: Move, config: ExitConfig, horizon: int | None
) -> tuple[float, int, ExitReason]:
    """Shape a move by a config's exits: (return %, bars held, exit reason)."""
    by_type = {e.type: e for e in config.exits}
    stop = stop_level(config)
    if stop is not None and move.mae_pct <= -stop:
        reason: ExitReason = next(t for t in ("stop_pct", "stop_atr", "trail_pct") if t in by_type)
        return -stop - SLIPPAGE_BPS / 100, max(1, move.bars // 3), reason
    target = by_type.get("target")
    if target is not None and target.type == "target" and move.mfe_pct >= target.pct:
        return target.pct - SLIPPAGE_BPS / 100, max(1, move.bars // 2), "target"
    time_exit = by_type.get("time")
    if time_exit is not None and time_exit.type == "time":
        bars = time_exit.bars
        return move.ret_pct * min(1.0, bars / move.bars), bars, "time"
    if horizon is not None and move.bars > horizon:
        return move.ret_pct, horizon, "horizon"
    if "close_below_ma" in by_type:
        return move.ret_pct, move.bars, "ma"
    if "trail_pct" in by_type:
        return move.ret_pct, move.bars, "trail_pct"
    # Only a target left and it was never hit: the trade runs to the horizon.
    return move.ret_pct, horizon or move.bars, "horizon"


def make_trade(rng: random.Random, move: Move, config: ExitConfig, horizon: int | None) -> Trade:
    ret, bars, reason = apply_exits(move, config, horizon)
    last = len(SESSIONS) - 1
    if move.entry_index + bars > last:
        bars, reason = last - move.entry_index, "end_of_test"
    entry_price = round(rng.uniform(10, 200), 4)
    exit_price = round(entry_price * (1 + ret / 100), 4)
    return_pct = (exit_price / entry_price - 1) * 100
    mae = min(move.mae_pct, return_pct, 0.0)
    mfe = max(move.mfe_pct, return_pct, 0.0)
    stop = stop_level(config)
    return Trade(
        ticker=move.ticker,
        entry_date=SESSIONS[move.entry_index],
        entry_price=entry_price,
        exit_date=SESSIONS[move.entry_index + bars],
        exit_price=exit_price,
        return_pct=return_pct,
        bars_held=bars,
        exit_reason=reason,
        r_multiple=return_pct / stop if stop else None,
        mae_pct=mae,
        mfe_pct=mfe,
        mae_r=mae / stop if stop else None,
        mfe_r=mfe / stop if stop else None,
        segment="is" if move.entry_index < OOS_INDEX else "oos",
    )


def by_entry(trades: list[Trade]) -> list[Trade]:
    return sorted(trades, key=lambda t: (t.entry_date, t.ticker))


def mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def distinct_weeks(trades: Sequence[Trade]) -> int:
    return len({t.entry_date.isocalendar()[:2] for t in trades})


@dataclass(frozen=True)
class Stats:
    """The per trade metrics shared by both modes (spec 0002, Metric definitions)."""

    n_trades: int
    win_rate_pct: float | None
    avg_win_pct: float | None
    avg_loss_pct: float | None
    expectancy_pct: float | None
    expectancy_r: float | None
    expectancy_per_bar_pct: float | None
    profit_factor: float | None
    avg_bars_held: float | None
    avg_mae_pct: float | None
    avg_mfe_pct: float | None
    horizon_exit_pct: float | None


def trade_stats(trades: Sequence[Trade]) -> Stats:
    n = len(trades)
    returns = [t.return_pct for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    r_values = [t.r_multiple for t in trades if t.r_multiple is not None]
    bars = sum(t.bars_held for t in trades)
    return Stats(
        n_trades=n,
        win_rate_pct=len(wins) / n * 100 if n else None,
        avg_win_pct=mean(wins),
        avg_loss_pct=mean(losses),
        expectancy_pct=mean(returns),
        expectancy_r=mean(r_values),
        expectancy_per_bar_pct=sum(returns) / bars if bars else None,
        profit_factor=sum(wins) / abs(sum(losses)) if n and losses and sum(losses) else None,
        avg_bars_held=mean([float(t.bars_held) for t in trades]),
        avg_mae_pct=mean([t.mae_pct for t in trades]),
        avg_mfe_pct=mean([t.mfe_pct for t in trades]),
        horizon_exit_pct=(sum(t.exit_reason == "horizon" for t in trades) / n * 100 if n else None),
    )


def trade_metrics(trades: Sequence[Trade]) -> TradeMetrics:
    s = trade_stats(trades)
    return TradeMetrics(
        n_trades=s.n_trades,
        distinct_weeks=distinct_weeks(trades),
        win_rate_pct=s.win_rate_pct,
        avg_win_pct=s.avg_win_pct,
        avg_loss_pct=s.avg_loss_pct,
        expectancy_pct=s.expectancy_pct,
        expectancy_r=s.expectancy_r,
        expectancy_per_bar_pct=s.expectancy_per_bar_pct,
        profit_factor=s.profit_factor,
        avg_bars_held=s.avg_bars_held,
        avg_mae_pct=s.avg_mae_pct,
        avg_mfe_pct=s.avg_mfe_pct,
        horizon_exit_pct=s.horizon_exit_pct,
    )


def split(trades: Sequence[Trade]) -> tuple[list[Trade], list[Trade]]:
    return [t for t in trades if t.segment == "is"], [t for t in trades if t.segment == "oos"]


# ---- Equity curves ---------------------------------------------------------------------


def random_walk(rng: random.Random, drift: float, vol: float) -> list[float]:
    values = [100.0]
    for _ in SESSIONS[1:]:
        values.append(values[-1] * (1 + rng.gauss(drift, vol)))
    return values


def stride(values: list[float]) -> list[Point]:
    """Evenly strided to at most 500 points, keeping the first, the last and `oos_start`."""
    n = len(values)
    keep = {round(i * (n - 1) / (POINT_CAP - 2)) for i in range(POINT_CAP - 1)} | {OOS_INDEX}
    return [Point(date=SESSIONS[i], value=values[i]) for i in sorted(keep)]


def curve_metrics(values: list[float], start: int, end: int) -> tuple[float, float, float | None]:
    """CAGR %, max drawdown % (≤ 0) and Sharpe over sessions [start, end)."""
    seg = values[start:end]
    days = (SESSIONS[end - 1] - SESSIONS[start]).days
    cagr = ((seg[-1] / seg[0]) ** (365.25 / days) - 1) * 100
    peak, max_dd = seg[0], 0.0
    for v in seg:
        peak = max(peak, v)
        max_dd = min(max_dd, (v / peak - 1) * 100)
    rets = [b / a - 1 for a, b in pairwise(seg)]
    sd = statistics.stdev(rets) if len(rets) > 1 else 0.0
    sharpe = statistics.fmean(rets) / sd * math.sqrt(252) if sd else None
    return cagr, max_dd, sharpe


def exposure_pct(trades: Sequence[Trade], start: int, end: int) -> float:
    index = {d: i for i, d in enumerate(SESSIONS)}
    held: set[int] = set()
    for t in trades:
        held.update(range(index[t.entry_date], index[t.exit_date] + 1))
    return len(held & set(range(start, end))) / (end - start) * 100


# ---- Shared response parts -------------------------------------------------------------


def assumptions(configs: list[ExitConfig], portfolio: bool) -> Assumptions:
    return Assumptions(
        fill_model="signal_close_entry_next_open",
        slippage_bps=SLIPPAGE_BPS,
        commission_bps=0,
        sizing="equal_weight" if portfolio else "unit_notional",
        max_positions=10 if portfolio else None,
        entry_rising_edge=True,
        cooldown_bars=10,
        cooldown_basis="signal",
        no_last_bar_entry=True,
        same_ticker_overlap=not portfolio,
        horizon_bars=None if portfolio else HORIZON,
        seed=None if portfolio else SEED,
        configs=configs,
        baseline_config_index=0,
        delisting_rule="exit_last_close",
        oos_start=OOS_START,
        oos_fraction=OOS_FRACTION,
        data_mode=META.data_mode,
        data_version=META.data_version,
        data_seed=META.seed,
    )


def trial(rule: Rule, configs: list[ExitConfig]) -> Trial:
    return Trial(structure_key=structure_key(rule), pair_keys=[pair_key(rule, c) for c in configs])


def benchmark_parts(rng: random.Random) -> tuple[list[Point], BenchmarkSplit]:
    values = random_walk(rng, 0.0003, 0.011)
    is_m = curve_metrics(values, 0, OOS_INDEX)
    oos_m = curve_metrics(values, OOS_INDEX, len(SESSIONS))
    split_ = BenchmarkSplit(
        is_=BenchmarkMetrics(cagr_pct=is_m[0], max_dd_pct=is_m[1]),
        oos=BenchmarkMetrics(cagr_pct=oos_m[0], max_dd_pct=oos_m[1]),
    )
    return stride(values), split_


def cap(trades: list[Trade]) -> list[Trade]:
    """Over 2,000 trades, keep 2,000 evenly spread through the entry order."""
    total = len(trades)
    if total <= TRADE_CAP:
        return trades
    return [trades[round(i * (total - 1) / (TRADE_CAP - 1))] for i in range(TRADE_CAP)]


# ---- Portfolio mode --------------------------------------------------------------------

PORTFOLIO_CONFIG = ExitConfig.model_validate(
    {"name": "Baseline", "exits": [{"type": "stop_pct", "pct": 8}, {"type": "time", "bars": 20}]}
)


def null_portfolio_metrics() -> PortfolioMetrics:
    return PortfolioMetrics(
        n_trades=0,
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


def portfolio_metrics(
    trades: list[Trade], equity: list[float], start: int, end: int
) -> PortfolioMetrics:
    if not trades:
        return null_portfolio_metrics()
    s = trade_stats(trades)
    cagr, max_dd, sharpe = curve_metrics(equity, start, end)
    return PortfolioMetrics(
        n_trades=s.n_trades,
        cagr_pct=cagr,
        max_dd_pct=max_dd,
        sharpe=sharpe,
        win_rate_pct=s.win_rate_pct,
        avg_win_pct=s.avg_win_pct,
        avg_loss_pct=s.avg_loss_pct,
        expectancy_pct=s.expectancy_pct,
        expectancy_r=s.expectancy_r,
        profit_factor=s.profit_factor,
        avg_bars_held=s.avg_bars_held,
        exposure_pct=exposure_pct(trades, start, end),
    )


def portfolio_result(rng: random.Random, rule: Rule, n_trades: int) -> PortfolioResult:
    config = PORTFOLIO_CONFIG
    last_entry = len(SESSIONS) - 2  # no entry on the last bar
    trades = by_entry(
        [
            make_trade(
                rng,
                random_move(rng, rng.choice(TICKERS), rng.randint(0, last_entry), 1.2),
                config,
                None,
            )
            for _ in range(n_trades)
        ]
    )
    equity = random_walk(rng, 0.0004, 0.009) if trades else [100.0] * len(SESSIONS)
    is_trades, oos_trades = split(trades)
    benchmark, benchmark_metrics = benchmark_parts(rng)
    shown = cap(trades)
    warnings = []
    if not trades:
        warnings.append(
            Warning(code="no_entries", config_index=None, message="The rule produced no entries.")
        )
    if len(shown) < len(trades):
        warnings.append(
            Warning(
                code="trades_truncated",
                config_index=0,
                message=f"Showing {len(shown)} of {len(trades)} trades; metrics use every trade.",
            )
        )
    return PortfolioResult(
        mode="portfolio",
        assumptions=assumptions([config], portfolio=True),
        oos_start=OOS_START,
        trial=trial(rule, [config]),
        warnings=warnings,
        metrics=PortfolioSplit(
            is_=portfolio_metrics(is_trades, equity, 0, OOS_INDEX),
            oos=portfolio_metrics(oos_trades, equity, OOS_INDEX, len(SESSIONS)),
        ),
        benchmark_metrics=benchmark_metrics,
        equity=stride(equity),
        benchmark=benchmark,
        trades=shown,
        trades_total=len(trades),
        trades_truncated=len(shown) < len(trades),
    )


# ---- Trade mode (exit lab) -------------------------------------------------------------

LAB_CONFIGS = [
    ExitConfig.model_validate(c)
    for c in (
        {
            "name": "Baseline",
            "exits": [{"type": "stop_pct", "pct": 8}, {"type": "time", "bars": 20}],
        },
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
    )
]


def edge(strategy: TradeMetrics, random_: TradeMetrics) -> EdgeMetrics:
    def diff(a: float | None, b: float | None) -> float | None:
        return a - b if a is not None and b is not None else None

    return EdgeMetrics(
        expectancy_pct=diff(strategy.expectancy_pct, random_.expectancy_pct),
        expectancy_r=diff(strategy.expectancy_r, random_.expectancy_r),
        expectancy_per_bar_pct=diff(
            strategy.expectancy_per_bar_pct, random_.expectancy_per_bar_pct
        ),
        win_rate_pct=diff(strategy.win_rate_pct, random_.win_rate_pct),
    )


HIGHER_IS_BETTER = (
    "win_rate_pct",
    "avg_win_pct",
    "avg_loss_pct",
    "expectancy_pct",
    "expectancy_r",
    "expectancy_per_bar_pct",
    "profit_factor",
    "avg_mae_pct",
    "avg_mfe_pct",
)


def best_is(rows: list[ConfigRow]) -> BestIs:
    best: dict[str, int | None] = {}
    for metric in (*HIGHER_IS_BETTER, "horizon_exit_pct"):
        sign = -1 if metric == "horizon_exit_pct" else 1
        scored = [
            (sign * value, -i)
            for i, row in enumerate(rows)
            if (value := getattr(row.strategy.is_, metric)) is not None
        ]
        best[metric] = -max(scored)[1] if scored else None
    return BestIs.model_validate(best)


def percentile(values: list[float], q: float) -> float | None:
    """NumPy's default (linear interpolation) percentile."""
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def guides(baseline_is: list[Trade]) -> Guides:
    # Percentiles of adverse depth (-mae_pct), reported back signed: p90 is deeper than p75.
    depths = [-t.mae_pct for t in baseline_is if t.return_pct > 0]

    def deep(q: float) -> float | None:
        value = percentile(depths, q)
        return -value if value is not None else None

    return Guides(
        winner_mae_p75_pct=deep(0.75),
        winner_mae_p90_pct=deep(0.90),
        mfe_median_pct=percentile([t.mfe_pct for t in baseline_is], 0.5),
    )


def trade_lab_result(rng: random.Random, rule: Rule) -> TradeLabResult:
    configs = LAB_CONFIGS
    last_entry = len(SESSIONS) - 2
    moves = sorted(
        (
            random_move(rng, rng.choice(TICKERS), rng.randint(0, last_entry), 1.0)
            for _ in range(180)
        ),
        key=lambda m: (m.entry_index, m.ticker),
    )
    is_count = sum(m.entry_index < OOS_INDEX for m in moves)
    oos_count = len(moves) - is_count
    # The random baseline: one seeded draw, stratified to the strategy's IS and OOS counts.
    random_moves = [
        random_move(rng, rng.choice(TICKERS), rng.randint(0, OOS_INDEX - 1), 1.2)
        for _ in range(is_count)
    ] + [
        random_move(rng, rng.choice(TICKERS), rng.randint(OOS_INDEX, last_entry), 1.2)
        for _ in range(oos_count)
    ]
    rows: list[ConfigRow] = []
    baseline_trades: list[Trade] = []
    warnings: list[Warning] = []
    for i, config in enumerate(configs):
        strategy = by_entry([make_trade(rng, m, config, HORIZON) for m in moves])
        random_ = by_entry([make_trade(rng, m, config, HORIZON) for m in random_moves])
        s_is, s_oos = (trade_metrics(part) for part in split(strategy))
        r_is, r_oos = (trade_metrics(part) for part in split(random_))
        rows.append(
            ConfigRow(
                name=config.name,
                strategy=TradeSplit(is_=s_is, oos=s_oos),
                random=TradeSplit(is_=r_is, oos=r_oos),
                edge=EdgeSplit(is_=edge(s_is, r_is), oos=edge(s_oos, r_oos)),
            )
        )
        if i == 0:
            baseline_trades = strategy
        if any((m.horizon_exit_pct or 0) > 10 for m in (s_is, s_oos)):
            warnings.append(
                Warning(
                    code="horizon_exits_over_10pct",
                    config_index=i,
                    message=(
                        f"{config.name}: more than 10% of trades hit the {HORIZON} bar "
                        "horizon, so its results are cut short."
                    ),
                )
            )
    shown = cap(baseline_trades)
    return TradeLabResult(
        mode="trade",
        assumptions=assumptions(configs, portfolio=False),
        oos_start=OOS_START,
        trial=trial(rule, configs),
        warnings=warnings,
        entries=Entries(
            count=len(moves),
            is_count=is_count,
            oos_count=oos_count,
            distinct_weeks=len({SESSIONS[m.entry_index].isocalendar()[:2] for m in moves}),
            hash=entries_hash((m.ticker, SESSIONS[m.entry_index]) for m in moves),
            random_is_count=is_count,
            random_oos_count=oos_count,
        ),
        rows=rows,
        best_is=best_is(rows),
        guides_is=guides(split(baseline_trades)[0]),
        baseline_trades=shown,
        baseline_trades_total=len(baseline_trades),
        baseline_trades_truncated=len(shown) < len(baseline_trades),
    )


# ---- Scan ------------------------------------------------------------------------------


def scan_response(rng: random.Random, rule: Rule) -> ScanResponse:
    """About 40 hits for the 52 week breakout template, with a few new today."""
    columns = scan_columns(rule)
    if columns != ["close", "highest(252)[1]", "volume", "1.5×avg_volume(50)"]:
        raise RuntimeError(f"the scan mock expects the breakout template, got {columns}")
    rows = []
    for ticker in sorted(rng.sample(TICKERS, 40)):
        close = rng.uniform(8, 300)
        avg_volume = rng.uniform(2e5, 4e6)
        volume = avg_volume * rng.uniform(1.6, 4)
        rows.append(
            ScanRow(
                ticker=ticker,
                close=close,
                chg_pct=rng.uniform(0.5, 8),
                vol_ratio=volume / avg_volume,
                operands=[close, close * rng.uniform(0.9, 0.995), volume, 1.5 * avg_volume],
                new_today=rng.random() < 0.25,
            )
        )
    rows.sort(key=lambda r: (not r.new_today, r.ticker))
    return ScanResponse(as_of=SESSIONS[-1], columns=columns, rows=rows)


# ---- Error mocks through the real app ----------------------------------------------------


def condition(ind: str, n: int | None = None) -> dict[str, Any]:
    left: dict[str, Any] = {"kind": "ind", "ind": ind}
    if n is not None:
        left["n"] = n
    return {"left": left, "op": ">", "right": {"kind": "value", "value": 5}}


def error_mocks() -> None:
    client = TestClient(app)
    ok_rule = TEMPLATES[0].rule.model_dump(mode="json")
    config = {"name": "Baseline", "exits": [{"type": "stop_pct", "pct": 8}]}

    def post(name: str, path: str, body: dict[str, Any], status: int) -> None:
        res = client.post(f"/api/v1/{path}", json=body)
        if res.status_code != status:
            raise RuntimeError(f"{name}: expected {status}, got {res.status_code}: {res.text}")
        write(name, res.json())

    post(
        "422.rule.unknown_indicator.json",
        "scan",
        {"rule": {"name": "Bad", "conditions": [condition("macd", 12)]}},
        422,
    )
    post(
        "422.rule.n_out_of_range.json",
        "scan",
        {"rule": {"name": "Bad", "conditions": [condition("rsi", 60)]}},
        422,
    )
    post(
        "422.rule.too_many_conditions.json",
        "scan",
        {"rule": {"name": "Bad", "conditions": [condition("close")] * 9}},
        422,
    )
    post(
        "422.exits.duplicate_type.json",
        "backtest",
        {
            "rule": ok_rule,
            "configs": [
                {
                    "name": "Baseline",
                    "exits": [{"type": "stop_pct", "pct": 8}, {"type": "stop_pct", "pct": 5}],
                }
            ],
        },
        422,
    )
    post(
        "422.exits.too_many_configs.json",
        "backtest",
        {"rule": ok_rule, "configs": [{**config, "name": f"Config {i}"} for i in range(1, 8)]},
        422,
    )
    post(
        "422.sim.out_of_range.json",
        "backtest",
        {"rule": ok_rule, "configs": [config], "sim": {"max_positions": 25}},
        422,
    )
    post("501.scan.json", "scan", {"rule": ok_rule}, 501)


# ---- Main ------------------------------------------------------------------------------


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)  # noqa: S311  (seeded mock numbers, not security)
    rule = TEMPLATES[0].rule
    print(f"writing {OUT}")
    write(
        "meta.json",
        MetaResponse(contract_version=CONTRACT_VERSION, data=META, oos_start=OOS_START),
    )
    write("indicators.json", dump_list(IndicatorSpec, list(INDICATOR_SPECS.values())))
    write("templates.json", dump_list(TemplateOut, TEMPLATES))
    write("scan.json", scan_response(rng, rule))
    write("scan.empty.json", ScanResponse(as_of=SESSIONS[-1], columns=scan_columns(rule), rows=[]))
    write("backtest.portfolio.json", portfolio_result(rng, rule, 150))
    write("backtest.portfolio.truncated.json", portfolio_result(rng, rule, 2600))
    write("backtest.trade_lab.json", trade_lab_result(rng, rule))
    write("backtest.no_entries.json", portfolio_result(rng, rule, 0))
    error_mocks()


if __name__ == "__main__":
    main()
