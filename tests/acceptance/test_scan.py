"""Scan criteria S-1 to S-4 (doc 01 section 6.3), through `engine.api.scan` and `/scan`."""

from __future__ import annotations

import time

import pytest

from acceptance.support import (
    Frame,
    bar_date,
    build_market,
    config,
    flat,
    ind,
    make_rule,
    random_walk_frames,
    run_scan,
    trade_lab,
    val,
)
from engine.contracts import TEMPLATES, Market
from golden.reference import entry_signals


def _rising(start_bar: int, n: int, base: float = 10.0) -> Frame:
    close = [base + 0.1 * i for i in range(n)]
    return Frame(start_bar, list(close), list(close), list(close), close)


def _falling(start_bar: int, n: int, base: float = 20.0) -> Frame:
    close = [base - 0.1 * i for i in range(n)]
    return Frame(start_bar, list(close), list(close), list(close), close)


@pytest.mark.ac("S-1")
def test_scan_returns_exactly_the_alive_valid_true_tickers() -> None:
    frames = {
        "HIT": _rising(1, 40),  # valid and true on bar 40
        "MISS": _falling(1, 40),  # valid and false
        "YOUNG": _rising(39, 2),  # listed on bar 39: sma(3) not computable yet, so not a hit
        "LATE": _rising(30, 11),  # listed on bar 30, valid and true by bar 40
    }
    market = build_market(frames)
    rule = make_rule((ind("close"), ">", ind("sma", n=3)))
    result = run_scan(rule, market, bar_date(40))
    assert result.as_of == bar_date(40)
    assert sorted(r.ticker for r in result.rows) == ["HIT", "LATE"]


@pytest.mark.ac("S-1")
def test_scan_defaults_to_the_last_session() -> None:
    market = build_market({"HIT": _rising(1, 25)})
    result = run_scan(make_rule((ind("close"), ">", val(5))), market)
    assert result.as_of == bar_date(25)
    assert [r.ticker for r in result.rows] == ["HIT"]


@pytest.mark.ac("S-2")
def test_a_delisted_ticker_never_appears_after_delisting() -> None:
    frames = {"GONE": _rising(1, 20), "ALIVE": _rising(1, 40)}
    market = build_market(frames)
    rule = make_rule((ind("close"), ">", val(5)))
    # Alive on bar 15, so it shows; delisted after bar 20, so it never shows again.
    assert "GONE" in {r.ticker for r in run_scan(rule, market, bar_date(15)).rows}
    for bar in range(21, 41):
        assert "GONE" not in {r.ticker for r in run_scan(rule, market, bar_date(bar)).rows}


@pytest.mark.ac("S-2")
def test_the_benchmark_is_not_in_the_scan_universe() -> None:
    market = build_market({"AAA": flat(1, 20)})
    rule = make_rule((ind("close"), ">", val(5)))  # FIXTURE-INDEX closes at 100
    assert [r.ticker for r in run_scan(rule, market, bar_date(20)).rows] == ["AAA"]


@pytest.mark.ac("S-3")
def test_new_today_equals_the_backtest_entry_signals() -> None:
    """Spec 0002 ruling (ac-questions S-3): `new_today` includes the cooldown and ignores only
    the last bar term, so it matches the backtest signals on every bar but the last."""
    frames = random_walk_frames(n_tickers=20, n_bars=120, seed=11)
    market = build_market(frames)
    rule = make_rule((ind("close"), "crosses_above", ind("sma", n=5)), (ind("close"), ">", val(5)))
    rule_dict = rule.model_dump(mode="json")
    golden_signals: dict[int, set[str]] = {}
    for ticker, frame in frames.items():
        for i in entry_signals(frame.golden(ticker), rule_dict, ignore_last_bar=True):
            golden_signals.setdefault(frame.start_bar + i, set()).add(ticker)

    configs = [config("a", {"type": "time", "bars": 3}), config("b", {"type": "time", "bars": 5})]
    lab = trade_lab(rule, configs, market)
    last_bar = {t: f.last_bar for t, f in frames.items()}
    trades_by_entry: dict[str, set[str]] = {}
    for trade in lab.baseline_trades:
        trades_by_entry.setdefault(trade.entry_date.isoformat(), set()).add(trade.ticker)
    assert not lab.baseline_trades_truncated

    for bar in range(10, 121):
        scan = run_scan(rule, market, bar_date(bar))
        new_today = {r.ticker for r in scan.rows if r.new_today}
        assert new_today == golden_signals.get(bar, set()), f"scan vs golden, bar {bar}"
        if bar < 120:
            # A signal on D fills at the next open, so the backtest's entry date is bar D + 1.
            # A ticker on its own last bar has no next open, so only the scan shows it (B-15).
            fillable = {t for t in new_today if last_bar[t] != bar}
            from_backtest = trades_by_entry.get(bar_date(bar + 1).isoformat(), set())
            assert fillable == from_backtest, f"scan vs backtest, bar {bar}"


def _big_market() -> Market:
    return build_market(random_walk_frames(n_tickers=500, n_bars=1260, seed=3, churn=False))


@pytest.mark.ac("S-4")
def test_warm_scan_of_500_tickers_answers_under_a_second() -> None:
    """In process timing on a 500 ticker, 5 year market. The deployed check is in the verify
    steps (`make smoke`), because CI never calls the deployed API."""
    # Fail fast while the scan is still a stub, before building the big market.
    run_scan(TEMPLATES[0].rule, build_market({"AAA": flat(1, 5)}))
    market = _big_market()
    rule = TEMPLATES[0].rule
    run_scan(rule, market)  # warm the indicator cache
    started = time.perf_counter()
    run_scan(rule, market)
    assert time.perf_counter() - started < 1.0
