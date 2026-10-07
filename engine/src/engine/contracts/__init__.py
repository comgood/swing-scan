"""The frozen shared contracts: every shape the lanes build against (spec 0002).

These Pydantic models are the only definition. `contracts/openapi.json`, the TypeScript
types in `packages/api-client` and the mocks in `contracts/mocks/` are generated from them.
This package imports only the standard library, `pydantic` and `polars` (AC-15).
"""

from ._errors import ContractModel, bounded
from .backtest import (
    Assumptions,
    BacktestRequest,
    BacktestResponse,
    BenchmarkMetrics,
    BenchmarkSplit,
    BestIs,
    ConfigRow,
    EdgeMetrics,
    EdgeSplit,
    Entries,
    ExitReason,
    Guides,
    Point,
    PortfolioMetrics,
    PortfolioResult,
    PortfolioSplit,
    SimParams,
    Trade,
    TradeLabResult,
    TradeMetrics,
    TradeSplit,
    Trial,
    Warning,
    WarningCode,
)
from .exits import (
    STOP_TYPES,
    CloseBelowMa,
    Exit,
    ExitConfig,
    ExitConfigs,
    ExitType,
    StopAtr,
    StopPct,
    Target,
    TimeExit,
    TrailPct,
)
from .indicators import INDICATOR_SPECS, IndicatorSpec, IndName
from .market import (
    BARS_SCHEMA,
    SECURITIES_SCHEMA,
    DataMeta,
    Market,
    MarketError,
    validate_market,
)
from .meta import MetaResponse, NotImplementedBody
from .rule import TEMPLATES, Condition, IndOperand, Op, Operand, Rule, TemplateOut, ValueOperand
from .scan import ScanRequest, ScanResponse, ScanRow, column_label, scan_columns
from .trial import canonical_json, entries_hash, pair_key, structure_key

CONTRACT_VERSION = "1.0.0"
"""`info.version` of `contracts/openapi.json`. Additive optional fields bump the minor
version; a breaking change bumps the major and the git tag (`contracts-v2`)."""

__all__ = [
    "BARS_SCHEMA",
    "CONTRACT_VERSION",
    "INDICATOR_SPECS",
    "SECURITIES_SCHEMA",
    "STOP_TYPES",
    "TEMPLATES",
    "Assumptions",
    "BacktestRequest",
    "BacktestResponse",
    "BenchmarkMetrics",
    "BenchmarkSplit",
    "BestIs",
    "CloseBelowMa",
    "Condition",
    "ConfigRow",
    "ContractModel",
    "DataMeta",
    "EdgeMetrics",
    "EdgeSplit",
    "Entries",
    "Exit",
    "ExitConfig",
    "ExitConfigs",
    "ExitReason",
    "ExitType",
    "Guides",
    "IndName",
    "IndOperand",
    "IndicatorSpec",
    "Market",
    "MarketError",
    "MetaResponse",
    "NotImplementedBody",
    "Op",
    "Operand",
    "Point",
    "PortfolioMetrics",
    "PortfolioResult",
    "PortfolioSplit",
    "Rule",
    "ScanRequest",
    "ScanResponse",
    "ScanRow",
    "SimParams",
    "StopAtr",
    "StopPct",
    "Target",
    "TemplateOut",
    "TimeExit",
    "Trade",
    "TradeLabResult",
    "TradeMetrics",
    "TradeSplit",
    "TrailPct",
    "Trial",
    "ValueOperand",
    "Warning",
    "WarningCode",
    "bounded",
    "canonical_json",
    "column_label",
    "entries_hash",
    "pair_key",
    "scan_columns",
    "structure_key",
    "validate_market",
]
