"""Rule compiler: a `Rule` into per bar `valid` and `value` columns, with no `eval` (R-3, R-4).

A condition is valid at t when both operands are non null at t (and at t-1 for a cross). A
rule is valid when every condition is; an invalid rule evaluates false. Comparisons use the
raw float64 values, never rounded (AC-2).
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from engine.contracts import Condition, IndOperand, Operand, Rule
from engine.indicators import IndicatorCache, key_of


@dataclass(frozen=True)
class CompiledRule:
    """Per bar booleans aligned to the bars' row order, never null."""

    valid: pl.Series
    value: pl.Series
    """Valid and true."""


def _shift(cache: IndicatorCache, series: pl.Series, k: int) -> pl.Series:
    """The value k rows back within the same ticker, null before the ticker's first bar."""
    if k == 0:
        return series
    shifted = series.shift(k)
    return (
        pl.select(pl.when(cache.pos >= k).then(shifted).otherwise(None))
        .to_series()
        .alias(series.name)
    )


def operand_values(operand: IndOperand, cache: IndicatorCache) -> pl.Series:
    """The operand on every bar: the cached column, shifted by `offset`, times `mult`."""
    raw = cache.get(key_of(operand)).fill_nan(None)
    shifted = _shift(cache, raw, operand.offset)
    return shifted * operand.mult if operand.mult != 1 else shifted


def _series(operand: Operand, cache: IndicatorCache) -> pl.Series:
    if isinstance(operand, IndOperand):
        return operand_values(operand, cache)
    return pl.repeat(operand.value, cache.bars.height, dtype=pl.Float64, eager=True)


def _compare(op: str, a: pl.Series, b: pl.Series) -> pl.Series:
    if op == ">":
        return a > b
    if op == "<":
        return a < b
    if op == ">=":
        return a >= b
    if op == "<=":
        return a <= b
    raise ValueError(f"unknown comparison {op!r}")


def _previous(operand: Operand, series: pl.Series, cache: IndicatorCache) -> pl.Series:
    """The operand at t-1, with its offset counted from t-1; a number is the same."""
    return _shift(cache, series, 1) if isinstance(operand, IndOperand) else series


def _condition(condition: Condition, cache: IndicatorCache) -> tuple[pl.Series, pl.Series]:
    left = _series(condition.left, cache)
    right = _series(condition.right, cache)
    valid = left.is_not_null() & right.is_not_null()
    if condition.op in ("crosses_above", "crosses_below"):
        # A[t] > B[t] and A[t-1] <= B[t-1] (or the mirror); a first bar is never valid.
        prev_left = _previous(condition.left, left, cache)
        prev_right = _previous(condition.right, right, cache)
        valid = valid & prev_left.is_not_null() & prev_right.is_not_null()
        if condition.op == "crosses_above":
            crossed = (left > right) & (prev_left <= prev_right)
        else:
            crossed = (left < right) & (prev_left >= prev_right)
        return valid, crossed.fill_null(False) & valid
    value = _compare(condition.op, left, right).fill_null(False) & valid
    return valid, value


def compile_rule(rule: Rule, cache: IndicatorCache) -> CompiledRule:
    """AND every condition; the rule is valid only where every condition is valid."""
    valid, value = _condition(rule.conditions[0], cache)
    for condition in rule.conditions[1:]:
        c_valid, c_value = _condition(condition, cache)
        valid, value = valid & c_valid, value & c_value
    return CompiledRule(valid=valid.alias("valid"), value=(value & valid).alias("value"))
