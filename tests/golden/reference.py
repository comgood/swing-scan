"""Naive, loop based reference for rule evaluation and entry signals (doc 02 sections 6 and 15.8).

Written from doc 01 section 6.2 and 6.4 and doc 02 section 6 only, never from the engine. It is
slow on purpose: plain Python lists and explicit loops, one ticker at a time, so a reviewer can
check every line against the criteria. R-2, B-14 to B-16, S-3 and X-1 compare the engine to it.

Conventions the docs leave open are recorded in `docs/qa/ac-questions.md` and listed here:
- `sma(n)`, `avg_volume(n)` and `highest(n)` / `lowest(n)` use the n bars ending at t (today
  included), so they first exist on bar n. With `offset: 1` they cover t-n to t-1 (R-4).
- `ema(n)` is seeded with the simple mean of the first n closes on bar n, then uses
  `alpha = 2 / (n + 1)` (ac-questions "EMA seed").
- `ret(n)` is `close[t] / close[t-n] - 1` and first exists on bar n + 1.
- `rsi`, `atr` and `rs` are not needed by the templates and raise `NotImplementedError`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

Json = Mapping[str, Any]
Value = float | None

PRICE_FIELDS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class TickerBars:
    """One ticker's bars while it is alive, oldest first. Bar i is index i (0 based)."""

    ticker: str
    dates: Sequence[date]
    open: Sequence[float]
    high: Sequence[float]
    low: Sequence[float]
    close: Sequence[float]
    volume: Sequence[float]

    def __len__(self) -> int:
        return len(self.dates)

    def field(self, name: str) -> Sequence[float]:
        series: Sequence[float] = getattr(self, name)
        return series


def _window_mean(xs: Sequence[float], n: int) -> list[Value]:
    out: list[Value] = []
    for t in range(len(xs)):
        if t < n - 1:
            out.append(None)
            continue
        total = 0.0
        for k in range(t - n + 1, t + 1):
            total += xs[k]
        out.append(total / n)
    return out


def _window_extreme(xs: Sequence[float], n: int, *, highest: bool) -> list[Value]:
    out: list[Value] = []
    for t in range(len(xs)):
        if t < n - 1:
            out.append(None)
            continue
        best = xs[t - n + 1]
        for k in range(t - n + 2, t + 1):
            best = max(best, xs[k]) if highest else min(best, xs[k])
        out.append(best)
    return out


def _ema(xs: Sequence[float], n: int) -> list[Value]:
    out: list[Value] = []
    alpha = 2.0 / (n + 1)
    prev: float | None = None
    for t in range(len(xs)):
        if t < n - 1:
            out.append(None)
            continue
        prev = sum(xs[:n]) / n if prev is None else alpha * xs[t] + (1 - alpha) * prev
        out.append(prev)
    return out


def _ret(xs: Sequence[float], n: int) -> list[Value]:
    return [None if t < n else xs[t] / xs[t - n] - 1 for t in range(len(xs))]


def indicator(bars: TickerBars, name: str, n: int | None) -> list[Value]:
    """The raw indicator series (no offset, no mult)."""
    if name in PRICE_FIELDS:
        return [float(x) for x in bars.field(name)]
    if n is None:
        raise ValueError(f"{name} needs n")
    if name == "sma":
        return _window_mean(bars.close, n)
    if name == "avg_volume":
        return _window_mean(bars.volume, n)
    if name == "ema":
        return _ema(bars.close, n)
    if name == "highest":
        return _window_extreme(bars.high, n, highest=True)
    if name == "lowest":
        return _window_extreme(bars.low, n, highest=False)
    if name == "ret":
        return _ret(bars.close, n)
    raise NotImplementedError(f"the golden reference does not implement {name}")


def operand_series(bars: TickerBars, operand: Json) -> list[Value]:
    """An operand's value on every bar, with offset and mult applied. None means not computable."""
    if operand["kind"] == "value":
        return [float(operand["value"])] * len(bars)
    raw = indicator(bars, str(operand["ind"]), operand.get("n"))
    offset = int(operand.get("offset", 0))
    mult = float(operand.get("mult", 1.0))
    out: list[Value] = []
    for t in range(len(bars)):
        src = t - offset
        v = raw[src] if src >= 0 else None
        out.append(None if v is None or math.isnan(v) else v * mult)
    return out


def _compare(op: str, a: float, b: float) -> bool:
    if op == ">":
        return a > b
    if op == "<":
        return a < b
    if op == ">=":
        return a >= b
    if op == "<=":
        return a <= b
    raise ValueError(op)


def condition_series(bars: TickerBars, condition: Json) -> list[bool | None]:
    """True or false per bar, or None when the condition is not valid (not computable)."""
    left = operand_series(bars, condition["left"])
    right = operand_series(bars, condition["right"])
    op = str(condition["op"])
    out: list[bool | None] = []
    for t in range(len(bars)):
        a, b = left[t], right[t]
        if a is None or b is None:
            out.append(None)
            continue
        if op in ("crosses_above", "crosses_below"):
            if t == 0:
                out.append(None)
                continue
            pa, pb = left[t - 1], right[t - 1]
            if pa is None or pb is None:
                out.append(None)
                continue
            if op == "crosses_above":
                out.append(a > b and pa <= pb)
            else:
                out.append(a < b and pa >= pb)
            continue
        out.append(_compare(op, a, b))
    return out


def rule_series(bars: TickerBars, rule: Json) -> list[bool | None]:
    """The rule per bar: None when any condition is invalid, else the AND of the conditions."""
    per_condition = [condition_series(bars, c) for c in rule["conditions"]]
    out: list[bool | None] = []
    for t in range(len(bars)):
        values = [series[t] for series in per_condition]
        if any(v is None for v in values):
            out.append(None)
        else:
            out.append(all(bool(v) for v in values))
    return out


def hits(bars: TickerBars, rule: Json) -> list[bool]:
    """Bars where the rule is valid and true (what a scan returns, S-1)."""
    return [v is True for v in rule_series(bars, rule)]


def entry_signals(
    bars: TickerBars, rule: Json, *, cooldown: int = 10, ignore_last_bar: bool = False
) -> list[int]:
    """Accepted entry signal bar indices for one ticker (doc 02 section 6).

    edge(t)   = rule valid and true at t, and valid and false at t-1 (B-14)
    signal(t) = edge(t), not the ticker's last bar (B-15, skipped when `ignore_last_bar`),
                and no accepted signal in t-cooldown .. t-1 (B-16)
    """
    series = rule_series(bars, rule)
    last = len(bars) - 1
    accepted: list[int] = []
    for t in range(1, len(bars)):
        edge = series[t] is True and series[t - 1] is False
        if not edge:
            continue
        if t == last and not ignore_last_bar:
            continue
        if accepted and t - accepted[-1] <= cooldown:
            continue
        accepted.append(t)
    return accepted
