"""Scan criteria S-1 to S-4 (doc 01 section 6.3), through `engine.api.scan` and `/scan`.

The later tests in this file come from spec 0005 (feature 8, template scan) acceptance criteria:
row order and value sourcing (AC-5), the `as_of` default and 422 (AC-6), the chained cooldown
(AC-4), the 8 condition timing (AC-7) and the route on the generated market (AC-8).
"""

from __future__ import annotations

import json
import time
from datetime import date, timedelta
from typing import Any

import pytest

from acceptance.support import (
    Frame,
    GeneratedApi,
    bar_date,
    build_market,
    config,
    flat,
    ind,
    make_rule,
    portfolio,
    random_walk_frames,
    rule_json,
    run_scan,
    set_bar,
    trade_lab,
    val,
)
from engine.contracts import TEMPLATES, Market, Rule, Trade
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


S3_FRAMES = random_walk_frames(n_tickers=20, n_bars=120, seed=11)
S3_RULE = make_rule((ind("close"), "crosses_above", ind("sma", n=5)), (ind("close"), ">", val(5)))


def _golden_new_today() -> dict[int, set[str]]:
    rule_dict = S3_RULE.model_dump(mode="json")
    signals: dict[int, set[str]] = {}
    for ticker, frame in S3_FRAMES.items():
        for i in entry_signals(frame.golden(ticker), rule_dict, ignore_last_bar=True):
            signals.setdefault(frame.start_bar + i, set()).add(ticker)
    return signals


def _assert_scan_matches(trades: list[Trade], market: Market) -> None:
    """Spec 0002 ruling (ac-questions S-3): `new_today` includes the cooldown and ignores only
    the last bar term, so it equals the backtest's signals on every bar but a ticker's last."""
    golden_signals = _golden_new_today()
    last_bar = {t: f.last_bar for t, f in S3_FRAMES.items()}
    trades_by_entry: dict[str, set[str]] = {}
    for trade in trades:
        trades_by_entry.setdefault(trade.entry_date.isoformat(), set()).add(trade.ticker)

    for bar in range(10, 121):
        scan = run_scan(S3_RULE, market, bar_date(bar))
        new_today = {r.ticker for r in scan.rows if r.new_today}
        assert new_today == golden_signals.get(bar, set()), f"scan vs golden, bar {bar}"
        if bar < 120:
            # A signal on D fills at the next open, so the backtest's entry date is bar D + 1.
            # A ticker on its own last bar has no next open, so only the scan shows it (B-15).
            fillable = {t for t in new_today if last_bar[t] != bar}
            from_backtest = trades_by_entry.get(bar_date(bar + 1).isoformat(), set())
            assert fillable == from_backtest, f"scan vs backtest, bar {bar}"


@pytest.mark.ac("S-3")
def test_new_today_equals_the_backtest_entry_signals() -> None:
    """Portfolio mode enters every signal when nothing competes for a slot: 20 slots for 20
    tickers, and a 1 bar time exit frees each one at the entry bar's close, long before the
    ticker's 10 bar cooldown ends (spec 0007 AC-8: entries come only from the shared signals)."""
    market = build_market(S3_FRAMES)
    result = portfolio(S3_RULE, [{"type": "time", "bars": 1}], market, max_positions=20)
    assert not result.trades_truncated
    assert result.trades, "the parity check must see signals"
    _assert_scan_matches(result.trades, market)


@pytest.mark.ac("X-1")
def test_new_today_equals_the_trade_lab_entries() -> None:
    """S-3 against the exit lab's entry list (X-1, spec 0009 AC-1; the parity oracle of spec
    0007's test plan turns green with feature 12)."""
    market = build_market(S3_FRAMES)
    configs = [config("a", {"type": "time", "bars": 3}), config("b", {"type": "time", "bars": 5})]
    lab = trade_lab(S3_RULE, configs, market)
    assert not lab.baseline_trades_truncated
    _assert_scan_matches(lab.baseline_trades, market)


def _big_market() -> Market:
    return build_market(random_walk_frames(n_tickers=500, n_bars=1260, seed=3, churn=False))


@pytest.mark.ac("S-4")
@pytest.mark.slow
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


# ---------------------------------------------------------------- spec 0005 (feature 8)


@pytest.mark.ac("S-2")
def test_a_ticker_listed_after_as_of_never_appears_and_one_delisted_on_as_of_can() -> None:
    frames = {"EARLY": _rising(1, 40), "LATER": _rising(25, 16), "ENDS": _rising(1, 20)}
    market = build_market(frames)
    rule = make_rule((ind("close"), ">", val(5)))
    assert sorted(r.ticker for r in run_scan(rule, market, bar_date(20)).rows) == [
        "EARLY",
        "ENDS",  # its last bar is bar 20, so it is alive on bar 20
    ]


def _edges_frame(n: int, edges: list[int]) -> Frame:
    """Closes at 9 (high 9.5, low 8.5), and a one bar close of 11 on each edge bar."""
    frame = flat(1, n, price=9.0)
    for bar in edges:
        set_bar(frame, bar, 11.0, 11.5, 10.5, 11.0)
    return frame


@pytest.mark.ac("S-3")
def test_the_cooldown_is_a_chain_of_accepted_signals() -> None:
    """Spec 0005 AC-4: edges on bars 100, 108 and 115. 108 falls in 100's cooldown and is
    dropped; 115 has no accepted signal in 105 to 114, so it is kept."""
    frames = {"CHN": _edges_frame(120, [100, 108, 115])}
    market = build_market(frames)
    rule = make_rule((ind("close"), ">", val(10)))
    golden = {
        frames["CHN"].start_bar + i
        for i in entry_signals(
            frames["CHN"].golden("CHN"), rule.model_dump(mode="json"), ignore_last_bar=True
        )
    }
    assert golden == {100, 115}
    for bar, expected in ((100, True), (108, False), (115, True)):
        rows = run_scan(rule, market, bar_date(bar)).rows
        assert [(r.ticker, r.new_today) for r in rows] == [("CHN", expected)], f"bar {bar}"


@pytest.mark.ac("S-3")
def test_new_today_shows_on_a_tickers_real_last_bar() -> None:
    """The scan ignores only the last bar term, even when as_of is the ticker's last bar."""
    market = build_market({"END": _edges_frame(115, [115]), "LONG": flat(1, 120, price=9.0)})
    rule = make_rule((ind("close"), ">", val(10)))
    rows = run_scan(rule, market, bar_date(115)).rows
    assert [(r.ticker, r.new_today) for r in rows] == [("END", True)]


@pytest.mark.ac("S-1")
def test_rows_sort_new_today_first_then_ticker() -> None:
    frames = {
        "ZED": _edges_frame(30, [30]),
        "MID": _edges_frame(30, [30]),
        "AAA": flat(1, 30, price=11.0),  # true on every bar, so no edge on bar 30
    }
    market = build_market(frames)
    result = run_scan(make_rule((ind("close"), ">", val(10))), market, bar_date(30))
    assert [(r.ticker, r.new_today) for r in result.rows] == [
        ("MID", True),
        ("ZED", True),
        ("AAA", False),
    ]


@pytest.mark.ac("S-1")
def test_columns_operands_and_row_values_follow_spec_0002() -> None:
    """Spec 0005 AC-5 on a hand computed breakout. 60 bars at 10 (high 10.5, volume 1M), then
    bar 60 closes at 12 on 3M volume."""
    frame = flat(1, 60, price=10.0)
    set_bar(frame, 60, 11.9, 12.2, 11.8, 12.0)
    frame.volume[frame.bar(60)] = 3_000_000.0
    market = build_market({"BRK": frame})
    rule = make_rule(
        (ind("close"), ">", ind("highest", n=5, offset=1)),
        (ind("volume"), ">", ind("avg_volume", n=3, mult=1.5)),
        (ind("close"), ">", val(5)),
    )
    result = run_scan(rule, market, bar_date(60))
    assert result.columns == ["close", "highest(5)[1]", "volume", "1.5×avg_volume(3)"]
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.ticker == "BRK" and row.new_today
    assert row.close == pytest.approx(12.0)
    # highest(5)[1] = max high of bars 55 to 59; 1.5 x mean volume of bars 58 to 60.
    assert row.operands == pytest.approx([12.0, 10.5, 3_000_000.0, 2_500_000.0])
    assert row.chg_pct == pytest.approx(20.0)
    # avg_volume(50) on bar 60 = (49 x 1M + 3M) / 50 = 1.04M.
    assert row.vol_ratio == pytest.approx(3_000_000.0 / 1_040_000.0)


@pytest.mark.ac("S-1")
def test_chg_pct_and_vol_ratio_are_null_without_history() -> None:
    zero_volume = flat(1, 60, price=10.0)
    zero_volume.volume = [0.0] * 60
    market = build_market(
        {"NEW": flat(30, 1, price=10.0), "SHORT": flat(1, 30), "ZERO": zero_volume}
    )
    rule = make_rule((ind("close"), ">", val(5)))
    rows = {r.ticker: r for r in run_scan(rule, market, bar_date(30)).rows}
    assert rows["NEW"].chg_pct is None  # its first bar
    assert rows["SHORT"].chg_pct == pytest.approx(0.0)
    assert rows["SHORT"].vol_ratio is None  # avg_volume(50) still in warm up
    zero = {r.ticker: r for r in run_scan(rule, market, bar_date(60)).rows}["ZERO"]
    assert zero.vol_ratio is None  # avg_volume(50) is 0: null, never infinite


@pytest.mark.ac("S-1")
def test_a_scan_is_the_same_cold_or_warm() -> None:
    market = build_market(random_walk_frames(n_tickers=12, n_bars=300, seed=8))
    for template in TEMPLATES:
        cold = run_scan(template.rule, market).model_dump(mode="json")
        warm = run_scan(template.rule, market).model_dump(mode="json")
        assert cold == warm, template.id


def _saturday_after(day: date) -> date:
    return day + timedelta(days=(5 - day.weekday()) % 7 or 7)


@pytest.mark.ac("S-1")
def test_an_as_of_that_is_not_a_session_is_rejected() -> None:
    market = build_market({"AAA": flat(1, 30)})
    rule = make_rule((ind("close"), ">", val(5)))
    for bad in (_saturday_after(bar_date(10)), bar_date(1) - timedelta(days=1), bar_date(31)):
        # The exception type is not frozen (spec 0005 names only the error type).
        with pytest.raises(Exception) as caught:
            run_scan(rule, market, bad)
        error = caught.value
        detail = getattr(error, "errors", None)
        text = f"{error} {detail() if callable(detail) else ''}"
        assert "as_of_not_session" in text, f"{bad}: {text}"


def _eight_condition_rule() -> Rule:
    conditions = [c.model_dump(mode="json") for c in TEMPLATES[0].rule.conditions]
    extra = rule_json(
        (ind("close"), ">", ind("sma", n=50)),
        (ind("ema", n=21), ">", ind("ema", n=21, offset=5)),
        (ind("rsi", n=14), ">", val(0)),
        (ind("atr", n=14), ">", val(0)),
        (ind("rs", n=126), ">=", val(0)),
    )["conditions"]
    rule = Rule.model_validate({"name": "eight", "conditions": conditions + extra})
    assert len(rule.conditions) == 8
    return rule


@pytest.mark.ac("S-4")
@pytest.mark.slow
def test_warm_scan_of_8_conditions_on_500_tickers_answers_under_a_second() -> None:
    """Spec 0005 AC-7: 8 conditions, 500 tickers by 1,260 bars, warm, in process."""
    rule = _eight_condition_rule()
    run_scan(rule, build_market({"AAA": flat(1, 5)}))  # fail fast while the scan is a stub
    market = _big_market()
    run_scan(rule, market)
    started = time.perf_counter()
    run_scan(rule, market)
    assert time.perf_counter() - started < 1.0


# ---------------------------------------------------------------- /scan on the generated market


def _scan_lines(stdout: str) -> list[dict[str, Any]]:
    lines = []
    for raw in stdout.splitlines():
        try:
            parsed = json.loads(raw)
        except ValueError:
            continue
        if isinstance(parsed, dict) and "duration_ms" in parsed:
            lines.append(parsed)
    return lines


@pytest.mark.ac("S-1")
def test_scan_route_answers_on_the_generated_market(generated_api: GeneratedApi) -> None:
    rules = [t.rule.model_dump(mode="json") for t in TEMPLATES]
    results, _ = generated_api.run(*(("POST", "/api/v1/scan", {"rule": r}) for r in rules))
    for template, result in zip(TEMPLATES, results, strict=True):
        assert result["status"] == 200, (template.id, result)
        body = result["body"]
        assert body["as_of"] == generated_api.last.isoformat()  # AC-6 default
        tickers = [row["ticker"] for row in body["rows"]]
        assert "DEMO-INDEX" not in tickers
        assert len(tickers) == len(set(tickers)) <= 500
        for row in body["rows"]:
            assert len(row["operands"]) == len(body["columns"])


@pytest.mark.ac("S-1")
def test_scan_route_rejects_an_as_of_outside_the_sessions(generated_api: GeneratedApi) -> None:
    rule = TEMPLATES[0].rule.model_dump(mode="json")
    weekend = _saturday_after(generated_api.first + timedelta(days=30))
    assert weekend not in generated_api.sessions
    bad_dates = [
        weekend,
        generated_api.first - timedelta(days=1),
        generated_api.last + timedelta(days=7),
    ]
    calls = [("POST", "/api/v1/scan", {"rule": rule, "as_of": d.isoformat()}) for d in bad_dates]
    results, stdout = generated_api.run(*calls)
    for bad, result in zip(bad_dates, results, strict=True):
        assert result["status"] == 422, (bad, result)
        error = result["body"]["detail"][0]
        assert error["type"] == "as_of_not_session"
        assert error["loc"] == ["body", "as_of"]
        assert error["ctx"] == {
            "min": generated_api.first.isoformat(),
            "max": generated_api.last.isoformat(),
        }
    assert _scan_lines(stdout) == []  # a 422 writes no scan line (AC-8)


@pytest.mark.ac("S-4")
def test_each_scan_writes_one_json_log_line(generated_api: GeneratedApi) -> None:
    """Spec 0005 AC-8: one line per successful scan, with the fields the timing budget needs.
    The template columns are warmed at start, so a template scan is `warm`."""
    rule = TEMPLATES[0].rule.model_dump(mode="json")
    results, stdout = generated_api.run(("POST", "/api/v1/scan", {"rule": rule}))
    assert results[0]["status"] == 200
    lines = _scan_lines(stdout)
    assert len(lines) == 1, stdout[-2000:]
    line = lines[0]
    assert set(line) >= {"duration_ms", "n_conditions", "n_rows", "cache", "as_of"}
    assert line["n_conditions"] == 3
    assert line["n_rows"] == len(results[0]["body"]["rows"])
    assert line["cache"] == "warm"
    assert line["as_of"] == generated_api.last.isoformat()
