"""Scan contract: `chg_pct`, `vol_ratio`, `as_of`, warm start, timing (spec 0005, AC-4 to 7)."""

from __future__ import annotations

import math
import random
import time
from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest
from pydantic import ValidationError

from engine import api
from engine.contracts import (
    BARS_SCHEMA,
    SECURITIES_SCHEMA,
    TEMPLATES,
    DataMeta,
    Market,
    Rule,
    ScanRequest,
    ScanRow,
)
from engine.data.fixtures import FrameSpec, bar_date, make_market
from engine.indicators import cache_for
from golden.reference import TickerBars, entry_signals

from .helpers import ind, rule, val

ALWAYS = rule((ind("close"), ">", val(0)))


def _row(market: Market, ticker: str, as_of: date | None = None) -> ScanRow:
    result = api.scan(ScanRequest(rule=ALWAYS, as_of=as_of), market)
    return next(r for r in result.rows if r.ticker == ticker)


def test_chg_pct_uses_the_previous_row_and_is_null_on_the_first_bar() -> None:
    market = make_market({"AAA": FrameSpec(1, [10.0, 11.0]), "NEW": FrameSpec(2, [5.0])})
    assert _row(market, "AAA", bar_date(1)).chg_pct is None
    assert _row(market, "AAA").chg_pct == pytest.approx(10.0)
    assert _row(market, "NEW").chg_pct is None


def test_vol_ratio_is_null_in_warm_up_then_volume_over_its_50_bar_average() -> None:
    volume = [1_000_000.0] * 49 + [3_000_000.0]
    market = make_market({"AAA": FrameSpec(1, [10.0] * 50, volume=volume)})
    assert _row(market, "AAA", bar_date(49)).vol_ratio is None
    average = (49 * 1_000_000.0 + 3_000_000.0) / 50
    assert _row(market, "AAA").vol_ratio == pytest.approx(3_000_000.0 / average)


def test_vol_ratio_is_null_when_the_average_is_zero() -> None:
    market = make_market({"AAA": FrameSpec(1, [10.0] * 50, volume=[0.0] * 50)})
    assert _row(market, "AAA").vol_ratio is None


@pytest.mark.parametrize(
    "as_of",
    [date(2020, 1, 4), date(2020, 1, 1), bar_date(11)],  # a Saturday, before, after
)
def test_an_as_of_that_is_not_a_session_is_a_validation_error(as_of: date) -> None:
    market = make_market({"AAA": FrameSpec(1, [10.0] * 10)})
    with pytest.raises(ValidationError) as caught:
        api.scan(ScanRequest(rule=ALWAYS, as_of=as_of), market)
    (error,) = caught.value.errors(include_url=False)
    assert error["type"] == "as_of_not_session"
    assert error["loc"] == ("as_of",)
    assert error["ctx"] == {"min": "2020-01-02", "max": bar_date(10).isoformat()}


def test_timing_reports_cold_then_warm() -> None:
    market = make_market({"AAA": FrameSpec(1, [10.0, 11.0])})
    request = ScanRequest(rule=rule((ind("close"), ">", ind("sma", 2))))
    _, first = api.scan_timed(request, market)
    _, second = api.scan_timed(request, market)
    assert (first.cache, second.cache) == ("cold", "warm")
    assert (second.n_conditions, second.n_rows, second.as_of) == (1, 1, bar_date(2))
    assert second.duration_ms >= 0


def test_rs_reads_its_ret_and_vol_ratio_reads_avg_volume_50() -> None:
    keys = api.columns_read(rule((ind("rs", 20), ">", val(50))))
    assert [(k.ind, k.n) for k in keys] == [("rs", 20), ("ret", 20), ("avg_volume", 50)]


def test_warm_pins_every_template_column() -> None:
    market = make_market({"AAA": FrameSpec(1, [10.0] * 5)})
    api.warm(market)
    cache = cache_for(market)
    for template in TEMPLATES:
        assert set(api.columns_read(template.rule)) <= cache.pinned
        _, timing = api.scan_timed(ScanRequest(rule=template.rule), market)
        assert timing.cache == "warm"


def test_the_response_is_the_same_cold_or_warm() -> None:
    market = make_market({"AAA": FrameSpec(1, [10.0 + i for i in range(60)])})
    request = ScanRequest(rule=TEMPLATES[1].rule)
    cold = api.scan(request, market)
    assert cold == api.scan(request, market)


def _walk(seed: int, n_tickers: int, n_bars: int) -> dict[str, FrameSpec]:
    rng = random.Random(seed)  # noqa: S311 (test data)
    tickers: dict[str, FrameSpec] = {}
    for i in range(n_tickers):
        start = rng.randint(2, n_bars // 3) if i % 5 == 1 else 1
        stop = rng.randint(n_bars // 2, n_bars - 3) if i % 5 == 3 else n_bars
        level, close = 6.0, []
        for _ in range(stop - start + 1):
            level *= math.exp(rng.gauss(0.0, 0.03))
            close.append(level)
        tickers[f"T{i:02d}"] = FrameSpec(start, close)
    return tickers


def test_new_today_equals_the_golden_entry_signals_on_every_date() -> None:
    tickers = _walk(seed=5, n_tickers=24, n_bars=150)
    market = make_market(tickers)
    rule_ = rule((ind("close"), "crosses_above", ind("ema", 5)), (ind("close"), ">", val(5)))
    expected: dict[date, set[str]] = {}
    for ticker, spec in tickers.items():
        dates = [bar_date(spec.start_bar + i) for i in range(len(spec.close))]
        bars = TickerBars(ticker, dates, *[spec.close] * 5)
        for i in entry_signals(bars, rule_.model_dump(mode="json"), ignore_last_bar=True):
            expected.setdefault(dates[i], set()).add(ticker)
    assert expected, "the walk must produce signals"
    for bar in range(1, 151):
        result = api.scan(ScanRequest(rule=rule_, as_of=bar_date(bar)), market)
        new_today = {r.ticker for r in result.rows if r.new_today}
        assert new_today == expected.get(bar_date(bar), set()), f"bar {bar}"


def _big_market(n_tickers: int = 500, n_bars: int = 1260) -> Market:
    """A 500 ticker, 5 year random walk built directly with NumPy (fast to construct)."""
    rng = np.random.default_rng(3)
    days: list[date] = []
    day = date(2020, 1, 2)
    while len(days) < n_bars:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    names = [f"T{i:03d}" for i in range(n_tickers)] + ["ZZ-INDEX"]
    close = 30 * np.exp(np.cumsum(rng.normal(0, 0.02, (len(names), n_bars)), axis=1))
    spread = 1 + np.abs(rng.normal(0, 0.01, close.shape))
    bars = pl.DataFrame(
        {
            "ticker": np.repeat(names, n_bars),
            "date": days * len(names),
            "open": close.ravel(),
            "high": (close * spread).ravel(),
            "low": (close / spread).ravel(),
            "close": close.ravel(),
            "volume": rng.lognormal(13.8, 0.35, close.size),
        }
    ).cast(BARS_SCHEMA)  # type: ignore[arg-type]
    securities = pl.DataFrame(
        {
            "ticker": names,
            "name": names,
            "sector": ["test"] * len(names),
            "listed_from": [days[0]] * len(names),
            "delisted_on": [None] * len(names),
            "delist_reason": [None] * len(names),
        },
        schema=SECURITIES_SCHEMA,
    )
    meta = DataMeta(
        data_mode="synthetic",
        seed=3,
        data_version="test",
        start=days[0],
        end=days[-1],
        n_tickers=n_tickers,
        survivors_only=False,
        benchmark="ZZ-INDEX",
    )
    return Market(bars=bars, securities=securities, meta=meta)


EIGHT = Rule.model_validate(
    {
        "name": "eight conditions",
        "conditions": [
            {"left": ind("close"), "op": ">", "right": ind("highest", 252, offset=1)},
            {"left": ind("volume"), "op": ">", "right": ind("avg_volume", 50, mult=1.5)},
            {"left": ind("ema", 21), "op": ">", "right": ind("ema", 21, offset=5)},
            {"left": ind("close"), "op": ">", "right": ind("sma", 50)},
            {"left": ind("rsi", 14), "op": "<", "right": val(80)},
            {"left": ind("atr", 14), "op": ">", "right": val(0.01)},
            {"left": ind("rs"), "op": ">", "right": val(10)},
            {"left": ind("close"), "op": ">", "right": val(5)},
        ],
    }
)


def test_a_warm_scan_of_8_conditions_on_500_tickers_by_1260_bars_is_under_a_second() -> None:
    market = _big_market()
    request = ScanRequest(rule=EIGHT)
    api.scan(request, market)  # cold: computes every column
    started = time.perf_counter()
    _, timing = api.scan_timed(request, market)
    elapsed = time.perf_counter() - started
    assert timing.cache == "warm"
    assert elapsed < 1.0, f"warm scan took {elapsed:.3f} s"
