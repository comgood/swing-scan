"""Public use cases, the application layer. Acceptance tests call only these (spec 0002).

`backtest` is a stub until its scope feature lands; it raises `NotYetImplemented`, which the
API maps to 501. A stray `NotImplementedError` from a real bug stays a 500.
"""

from __future__ import annotations

import polars as pl

from .contracts import (
    BacktestRequest,
    BacktestResponse,
    IndOperand,
    Market,
    Rule,
    ScanRequest,
    ScanResponse,
    ScanRow,
    scan_columns,
)
from .indicators import cache_for
from .rules import compile_rule, entry_signals, operand_values

FEATURE_NAMES = {7: "Synthetic market", 8: "Template scan", 9: "Portfolio backtest core"}


class NotYetImplemented(Exception):
    """A use case whose scope feature has not landed yet."""

    def __init__(self, feature: int, what: str) -> None:
        self.feature = feature
        name = FEATURE_NAMES.get(feature, "a later feature")
        super().__init__(
            f"{what} is not implemented yet; it arrives with scope feature {feature} ({name})."
        )


def _distinct_operands(rule: Rule) -> list[IndOperand]:
    """Indicator operands deduped by `(ind, n, offset, mult)`, in `scan_columns` order."""
    seen: dict[tuple[str, int | None, int, float], IndOperand] = {}
    for condition in rule.conditions:
        for operand in (condition.left, condition.right):
            if isinstance(operand, IndOperand):
                seen.setdefault((operand.ind, operand.n, operand.offset, operand.mult), operand)
    return list(seen.values())


def scan(request: ScanRequest, market: Market) -> ScanResponse:
    """Tickers alive on `as_of`, not the benchmark, whose rule is valid and true (S-1, S-2).

    `new_today` is the shared entry signal on `as_of` with only the last bar term ignored
    (S-3). Rows are sorted new first, then ticker A to Z.
    """
    cache = cache_for(market)
    as_of = request.as_of if request.as_of is not None else cache.sessions[-1]
    compiled = compile_rule(request.rule, cache)
    signals = entry_signals(
        cache.pos, cache.is_last, compiled.valid, compiled.value, ignore_last_bar=True
    )
    operands = _distinct_operands(request.rule)
    frame = cache.bars.select("ticker", "date", "close").with_columns(
        compiled.value.alias("_hit"),
        signals.alias("new_today"),
        *(operand_values(op, cache).alias(f"_op{i}") for i, op in enumerate(operands)),
    )
    hits = frame.filter(
        (pl.col("date") == as_of) & (pl.col("ticker") != cache.benchmark) & pl.col("_hit")
    ).sort(["new_today", "ticker"], descending=[True, False])
    op_columns = [f"_op{i}" for i in range(len(operands))]
    rows = [
        ScanRow(
            ticker=row["ticker"],
            close=row["close"],
            chg_pct=None,  # filled by the scan contract milestone
            vol_ratio=None,
            operands=[row[c] for c in op_columns],
            new_today=row["new_today"],
        )
        for row in hits.iter_rows(named=True)
    ]
    return ScanResponse(as_of=as_of, columns=scan_columns(request.rule), rows=rows)


def backtest(request: BacktestRequest, market: Market) -> BacktestResponse:
    """Backtest a rule with 1 config (portfolio) or 2 to 6 configs (exit lab) (feature 9)."""
    raise NotYetImplemented(9, "backtest")
