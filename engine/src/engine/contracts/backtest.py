"""`POST /backtest` request and both response modes (spec 0002, doc 02 §5.4 and §7).

`len(configs)` picks the mode: 1 config is a portfolio backtest, 2 to 6 is the trade mode
exit lab. Response models declare no defaults, so every field is required in the
generated TypeScript; an undefined number is `null`, never NaN or Infinity (AC-14).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from ._errors import ContractModel, IsoDate, bounded, error_at
from .exits import ExitConfig, ExitConfigs
from .rule import Rule

# ---- Request ---------------------------------------------------------------------------


class SimParams(ContractModel):
    max_positions: Annotated[int, bounded(1, 20)] = 10
    """Portfolio mode only: open positions at once, equal weight."""
    slippage_bps: Annotated[float, bounded(0, 50)] = 10
    horizon_bars: Annotated[int, bounded(5, 252)] = 60
    """Trade mode only: the longest a trade may run before a `horizon` exit."""
    seed: Annotated[int, bounded(0, 2**31 - 1)] = 42
    """Trade mode only: the random baseline draw. Changing the default needs an ADR."""
    start: IsoDate | None = None
    end: IsoDate | None = None

    @model_validator(mode="after")
    def _start_before_end(self) -> SimParams:
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise error_at(
                ("end",),
                PydanticCustomError(
                    "end_not_after_start",
                    "end must be after start ({start})",
                    {"start": self.start.isoformat()},
                ),
                self.end.isoformat(),
            )
        return self


class BacktestRequest(ContractModel):
    rule: Rule
    configs: ExitConfigs
    sim: SimParams = Field(default_factory=SimParams)


# ---- Shared response parts -------------------------------------------------------------

ExitReason = Literal[
    "stop_pct",
    "stop_atr",
    "trail_pct",
    "target",
    "time",
    "ma",
    "delisted",
    "horizon",
    "end_of_test",
]

Segment = Literal["is", "oos"]


class Trade(ContractModel):
    ticker: str
    entry_date: IsoDate
    entry_price: float
    exit_date: IsoDate
    exit_price: float
    return_pct: float
    bars_held: int
    exit_reason: ExitReason
    r_multiple: float | None
    mae_pct: Annotated[float, bounded(None, 0)]
    mfe_pct: Annotated[float, bounded(0, None)]
    mae_r: float | None
    mfe_r: float | None
    segment: Segment


class Point(ContractModel):
    date: IsoDate
    value: float


class Trial(ContractModel):
    structure_key: str
    pair_keys: list[str]
    """One per config, in config order."""


WarningCode = Literal["no_entries", "horizon_exits_over_10pct", "trades_truncated"]


class Warning(ContractModel):
    code: WarningCode
    config_index: int | None
    message: str


class Assumptions(ContractModel):
    """Every setting that shaped the result, echoed so a run can be reproduced."""

    fill_model: Literal["signal_close_entry_next_open"]
    slippage_bps: float
    commission_bps: float
    sizing: Literal["equal_weight", "unit_notional"]
    max_positions: int | None
    entry_rising_edge: Literal[True]
    cooldown_bars: int
    cooldown_basis: Literal["signal"]
    no_last_bar_entry: Literal[True]
    same_ticker_overlap: bool
    horizon_bars: int | None
    seed: int | None
    configs: list[ExitConfig]
    baseline_config_index: int
    delisting_rule: Literal["exit_last_close"]
    oos_start: IsoDate
    oos_fraction: float
    data_mode: Literal["synthetic", "live"]
    data_version: str
    data_seed: int | None


# ---- Portfolio mode --------------------------------------------------------------------


class PortfolioMetrics(ContractModel):
    n_trades: int
    cagr_pct: float | None
    max_dd_pct: float | None
    sharpe: float | None
    win_rate_pct: float | None
    avg_win_pct: float | None
    avg_loss_pct: float | None
    expectancy_pct: float | None
    expectancy_r: float | None
    profit_factor: float | None
    avg_bars_held: float | None
    exposure_pct: float | None


class BenchmarkMetrics(ContractModel):
    cagr_pct: float | None
    max_dd_pct: float | None


class PortfolioSplit(ContractModel):
    is_: PortfolioMetrics = Field(validation_alias="is", serialization_alias="is")
    oos: PortfolioMetrics


class BenchmarkSplit(ContractModel):
    is_: BenchmarkMetrics = Field(validation_alias="is", serialization_alias="is")
    oos: BenchmarkMetrics


class PortfolioResult(ContractModel):
    mode: Literal["portfolio"]
    assumptions: Assumptions
    oos_start: IsoDate
    trial: Trial
    warnings: list[Warning]
    metrics: PortfolioSplit
    benchmark_metrics: BenchmarkSplit
    equity: Annotated[list[Point], bounded(0, 500)]
    benchmark: Annotated[list[Point], bounded(0, 500)]
    trades: Annotated[list[Trade], bounded(0, 2000)]
    trades_total: int
    trades_truncated: bool

    @model_validator(mode="after")
    def _oos_start_matches(self) -> PortfolioResult:
        if self.oos_start != self.assumptions.oos_start:
            raise ValueError("oos_start must equal assumptions.oos_start")
        return self


# ---- Trade mode (exit lab) -------------------------------------------------------------


class TradeMetrics(ContractModel):
    """Per trade metrics. No CAGR, max DD or Sharpe in trade mode (X-8)."""

    n_trades: int
    distinct_weeks: int
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


class EdgeMetrics(ContractModel):
    """Strategy minus random, per metric. Null when either side is null."""

    expectancy_pct: float | None
    expectancy_r: float | None
    expectancy_per_bar_pct: float | None
    win_rate_pct: float | None


class TradeSplit(ContractModel):
    is_: TradeMetrics = Field(validation_alias="is", serialization_alias="is")
    oos: TradeMetrics


class EdgeSplit(ContractModel):
    is_: EdgeMetrics = Field(validation_alias="is", serialization_alias="is")
    oos: EdgeMetrics


class ConfigRow(ContractModel):
    name: str
    strategy: TradeSplit
    random: TradeSplit
    edge: EdgeSplit


class Entries(ContractModel):
    count: int
    is_count: int
    oos_count: int
    distinct_weeks: int
    hash: str
    random_is_count: int
    random_oos_count: int


class BestIs(ContractModel):
    """The config index with the best IS value per ranked metric. OOS is never ranked (X-3)."""

    win_rate_pct: int | None
    avg_win_pct: int | None
    avg_loss_pct: int | None
    expectancy_pct: int | None
    expectancy_r: int | None
    expectancy_per_bar_pct: int | None
    profit_factor: int | None
    avg_mae_pct: int | None
    avg_mfe_pct: int | None
    horizon_exit_pct: int | None


class Guides(ContractModel):
    """Stop and target guides from the baseline config's IS trades only (X-5)."""

    winner_mae_p75_pct: float | None
    winner_mae_p90_pct: float | None
    mfe_median_pct: float | None


class TradeLabResult(ContractModel):
    mode: Literal["trade"]
    assumptions: Assumptions
    oos_start: IsoDate
    trial: Trial
    warnings: list[Warning]
    entries: Entries
    rows: Annotated[list[ConfigRow], bounded(2, 6)]
    best_is: BestIs
    guides_is: Guides
    baseline_trades: Annotated[list[Trade], bounded(0, 2000)]
    baseline_trades_total: int
    baseline_trades_truncated: bool

    @model_validator(mode="after")
    def _oos_start_matches(self) -> TradeLabResult:
        if self.oos_start != self.assumptions.oos_start:
            raise ValueError("oos_start must equal assumptions.oos_start")
        return self


BacktestResponse = Annotated[PortfolioResult | TradeLabResult, Field(discriminator="mode")]
"""Tagged by `mode`: `portfolio` for 1 config, `trade` for 2 to 6."""
