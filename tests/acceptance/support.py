"""Shared builders for acceptance tests, written from spec 0002 (contracts and fixture format).

Fixtures are plain Python lists. The same lists feed the engine (through the frozen
`engine.data.fixtures.make_market` builder, AC-11) and the golden reference, so the expected
values never come from engine code. The bar calendar below is reimplemented from the spec
(bar 1 is 2020-01-02, weekdays only) rather than imported.
"""

from __future__ import annotations

import math
import random
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, NoReturn

import pytest

from engine.api import backtest, scan
from engine.contracts import (
    BacktestRequest,
    BacktestResponse,
    Market,
    PortfolioResult,
    Rule,
    ScanRequest,
    ScanResponse,
    TradeLabResult,
)
from engine.data.fixtures import FrameSpec, make_market
from golden.reference import TickerBars

QA_QUESTIONS = "docs/qa/ac-questions.md"
CALENDAR_START = date(2020, 1, 2)
SLIP = 0.001  # 10 bps per side, the default


def bar_date(bar: int) -> date:
    """The k-th weekday counting from 2020-01-02 (spec 0002, fixture format)."""
    day = CALENDAR_START
    count = 1
    while count < bar:
        day += timedelta(days=1)
        if day.weekday() < 5:
            count += 1
    return day


# ---------------------------------------------------------------- rules and configs


def ind(name: str, n: int | None = None, offset: int = 0, mult: float = 1.0) -> dict[str, Any]:
    return {"kind": "ind", "ind": name, "n": n, "offset": offset, "mult": mult}


def val(x: float) -> dict[str, Any]:
    return {"kind": "value", "value": x}


def rule_json(
    *conditions: tuple[dict[str, Any], str, dict[str, Any]], name: str = "qa"
) -> dict[str, Any]:
    return {
        "name": name,
        "conditions": [{"left": a, "op": op, "right": b} for a, op, b in conditions],
    }


def make_rule(*conditions: tuple[dict[str, Any], str, dict[str, Any]], name: str = "qa") -> Rule:
    return Rule.model_validate(rule_json(*conditions, name=name))


VOLUME_SPIKE = rule_json((ind("volume"), ">", val(1_500_000)), name="volume spike")


def config(name: str, *exits: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "exits": list(exits)}


# ---------------------------------------------------------------- markets


@dataclass
class Frame:
    """One ticker's bars as lists, starting at `start_bar` (1 based)."""

    start_bar: int
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.volume:
            self.volume = [1_000_000.0] * len(self.close)
        lengths = {len(self.open), len(self.high), len(self.low), len(self.close), len(self.volume)}
        if len(lengths) != 1:
            raise ValueError("every column needs the same length")

    @property
    def last_bar(self) -> int:
        return self.start_bar + len(self.close) - 1

    def bar(self, k: int) -> int:
        """List index of absolute bar k."""
        return k - self.start_bar

    def golden(self, ticker: str) -> TickerBars:
        return TickerBars(
            ticker=ticker,
            dates=[bar_date(self.start_bar + i) for i in range(len(self.close))],
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
        )


def flat(start_bar: int, n: int, price: float = 10.0, spread: float = 0.5) -> Frame:
    """n bars at a constant price with a symmetric high and low band."""
    return Frame(
        start_bar=start_bar,
        open=[price] * n,
        high=[price + spread] * n,
        low=[price - spread] * n,
        close=[price] * n,
    )


def set_bar(frame: Frame, k: int, o: float, h: float, lo: float, c: float) -> None:
    i = frame.bar(k)
    frame.open[i], frame.high[i], frame.low[i], frame.close[i] = o, h, lo, c


def build_market(frames: dict[str, Frame], end_bar: int | None = None) -> Market:
    specs = {
        t: FrameSpec(
            start_bar=f.start_bar,
            close=f.close,
            open=f.open,
            high=f.high,
            low=f.low,
            volume=f.volume,
        )
        for t, f in frames.items()
    }
    return make_market(specs, end_bar=end_bar, name="qa")


def random_walk_frames(
    n_tickers: int, n_bars: int, seed: int, *, churn: bool = True
) -> dict[str, Frame]:
    """Seeded random walk tickers. With `churn`, some list late and some delist early."""
    rng = random.Random(seed)  # noqa: S311 (test data, not security)
    frames: dict[str, Frame] = {}
    for i in range(n_tickers):
        start, length = 1, n_bars
        if churn and i % 7 == 3:
            start = rng.randint(20, n_bars // 3)
            length = n_bars - start + 1
        if churn and i % 7 == 5:
            length = rng.randint(n_bars // 2, n_bars - 5)
        drift = rng.gauss(0.0004, 0.0004)
        open_: list[float] = []
        high: list[float] = []
        low: list[float] = []
        close: list[float] = []
        volume: list[float] = []
        level = 30.0
        for _ in range(length):
            prev = level
            level = prev * math.exp(rng.gauss(drift, 0.02))
            o = prev * math.exp(rng.gauss(0.0, 0.006))
            open_.append(o)
            close.append(level)
            high.append(max(o, level) * (1 + abs(rng.gauss(0.0, 0.01))))
            low.append(min(o, level) * (1 - abs(rng.gauss(0.0, 0.01))))
            volume.append(rng.lognormvariate(13.8, 0.35))
        frames[f"T{i:03d}"] = Frame(start, open_, high, low, close, volume)
    return frames


# ---------------------------------------------------------------- use cases


def run_scan(
    rule: Rule | dict[str, Any], market: Market, as_of: date | None = None
) -> ScanResponse:
    rule_model = rule if isinstance(rule, Rule) else Rule.model_validate(rule)
    return scan(ScanRequest(rule=rule_model, as_of=as_of), market)


def run_backtest(
    rule: Rule | dict[str, Any],
    configs: Sequence[dict[str, Any]],
    market: Market,
    **sim: Any,
) -> BacktestResponse:
    rule_json_ = rule.model_dump(mode="json") if isinstance(rule, Rule) else rule
    request = BacktestRequest.model_validate(
        {"rule": rule_json_, "configs": list(configs), "sim": sim}
    )
    return backtest(request, market)


def portfolio(
    rule: Rule | dict[str, Any], exits: Sequence[dict[str, Any]], market: Market, **sim: Any
) -> PortfolioResult:
    result = run_backtest(rule, [config("only", *exits)], market, **sim)
    assert isinstance(result, PortfolioResult), (
        f"one config must run in portfolio mode, got {result.mode}"
    )
    return result


def trade_lab(
    rule: Rule | dict[str, Any], configs: Sequence[dict[str, Any]], market: Market, **sim: Any
) -> TradeLabResult:
    result = run_backtest(rule, configs, market, **sim)
    assert isinstance(result, TradeLabResult), (
        f"2 to 6 configs must run in trade mode, got {result.mode}"
    )
    return result


# ---------------------------------------------------------------- owed hooks


def owed(anchor: str, what: str) -> NoReturn:
    """Fail a pending test whose entry point or rule is not frozen yet.

    The assertions around the call are written; only the hook is owed. The anchor points at the
    open question in `docs/qa/ac-questions.md`.
    """
    pytest.fail(f"owed: {what} (see {QA_QUESTIONS}#{anchor})")


WEB_ACCEPTANCE = Path(__file__).resolve().parents[2] / "apps" / "web" / "tests" / "acceptance"


def ui_covered_by(crit: str, *files: str) -> None:
    """Point the gate at the Vitest files that cover a criterion's UI half.

    Vitest runs those files in `pnpm --filter web test` (always blocking). This check keeps the
    pointer honest: each file exists, names the ID in a test title, and owes nothing for it.
    """
    for name in files:
        path = WEB_ACCEPTANCE / name
        assert path.is_file(), f"{crit}: {path} is missing"
        text = path.read_text(encoding="utf-8")
        assert re.search(rf"""\bit\(\s*["'`]{re.escape(crit)}:""", text), (
            f"{crit}: {name} has no it('{crit}: ...') test"
        )
        assert not re.search(rf"""\bit\.todo\(\s*["'`]{re.escape(crit)}:""", text), (
            f"{crit}: {name} still owes an it.todo for it"
        )


def ui_owed(crit: str) -> NoReturn:
    """The UI half of a criterion lives in `apps/web/tests/acceptance/` (Vitest), not here."""
    owed(
        "ui-tests",
        f"{crit} UI test belongs in apps/web/tests/acceptance/ (Vitest against the mocks), "
        "not written yet",
    )
