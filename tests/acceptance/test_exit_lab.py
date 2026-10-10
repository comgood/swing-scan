"""Exit lab criteria X-1 to X-5 and X-7 to X-10 (doc 01 section 6.5), trade mode.

Metric definitions come from spec 0002 (*Metric definitions*, *Value sourcing*), so expected
values are recomputed here from the returned baseline trade list, never read from engine code.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Sequence
from functools import cache
from typing import Any

import pytest
from fastapi.testclient import TestClient

from acceptance.support import (
    VOLUME_SPIKE,
    Frame,
    bar_date,
    build_market,
    config,
    random_walk_frames,
    run_backtest,
    trade_lab,
    ui_owed,
)
from engine.contracts import (
    TEMPLATES,
    Market,
    TemplateOut,
    Trade,
    TradeLabResult,
    TradeMetrics,
    entries_hash,
)
from engine.synthetic import generate
from golden.reference import entry_signals

STRATEGY = TEMPLATES[1].rule  # pullback to a rising 21 EMA: plenty of signals on a random walk

FIVE_CONFIGS = [
    config("Baseline", {"type": "time", "bars": 10}),
    config("Stop and time", {"type": "stop_pct", "pct": 8}, {"type": "time", "bars": 10}),
    config(
        "ATR, target, time",
        {"type": "stop_atr", "k": 2, "n": 14},
        {"type": "target", "pct": 15},
        {"type": "time", "bars": 20},
    ),
    config("Trail", {"type": "trail_pct", "pct": 10}, {"type": "time", "bars": 30}),
    config(
        "MA exit", {"type": "close_below_ma", "ma": "ema", "n": 21}, {"type": "stop_pct", "pct": 8}
    ),
]


def _lab_market() -> tuple[dict[str, Frame], Any]:
    frames = random_walk_frames(n_tickers=30, n_bars=500, seed=21)
    return frames, build_market(frames)


# ---------------------------------------------------------------- X-1 identical entries


@pytest.mark.ac("X-1")
def test_entries_are_identical_across_configs_and_follow_the_entry_rules() -> None:
    frames, market = _lab_market()
    rule_dict = STRATEGY.model_dump(mode="json")
    expected: list[tuple[str, Any]] = []
    for ticker, frame in frames.items():
        for i in entry_signals(frame.golden(ticker), rule_dict):
            expected.append((ticker, bar_date(frame.start_bar + i + 1)))  # fills next open

    first = trade_lab(STRATEGY, FIVE_CONFIGS[:3], market)
    reordered = trade_lab(STRATEGY, [FIVE_CONFIGS[2], FIVE_CONFIGS[0], FIVE_CONFIGS[1]], market)
    assert first.entries.count == len(expected) > 0
    assert first.entries.hash == entries_hash(expected)
    assert reordered.entries == first.entries
    for lab in (first, reordered):
        for row in lab.rows:
            n = row.strategy.is_.n_trades + row.strategy.oos.n_trades
            assert n == lab.entries.count, row.name

    # Entry prices are the same next open fill whatever the exits.
    if not first.baseline_trades_truncated:
        prices = {(t.ticker, t.entry_date): t.entry_price for t in first.baseline_trades}
        other = {(t.ticker, t.entry_date): t.entry_price for t in reordered.baseline_trades}
        assert set(prices) == set(other)


# ---------------------------------------------------------------- X-2 config count


@pytest.mark.ac("X-2")
def test_seven_configs_return_422(client: TestClient) -> None:
    rule = STRATEGY.model_dump(mode="json")
    configs = [config(f"c{i}", {"type": "time", "bars": 10}) for i in range(7)]
    response = client.post("/api/v1/backtest", json={"rule": rule, "configs": configs})
    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "configs"]
    assert error["ctx"] == {"min": 1, "max": 6}


@pytest.mark.ac("X-2")
def test_one_config_runs_as_a_portfolio_backtest() -> None:
    _, market = _lab_market()
    result = run_backtest(STRATEGY, [config("solo", {"type": "time", "bars": 10})], market)
    assert result.mode == "portfolio"


# ---------------------------------------------------------------- X-3 IS and OOS, best IS only

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
LOWER_IS_BETTER = ("horizon_exit_pct",)


def _best(values: Sequence[float | None], higher: bool) -> int | None:
    best: int | None = None
    for i, v in enumerate(values):
        if v is None:
            continue
        current = values[best] if best is not None else None
        if current is None or (v > current if higher else v < current):
            best = i
    return best


@pytest.mark.ac("X-3")
def test_every_metric_has_is_and_oos_and_only_is_is_ranked() -> None:
    _, market = _lab_market()
    lab = trade_lab(STRATEGY, FIVE_CONFIGS, market)
    for row in lab.rows:
        for split in (row.strategy, row.random):
            assert isinstance(split.is_, TradeMetrics) and isinstance(split.oos, TradeMetrics)
        assert row.edge.is_ is not None and row.edge.oos is not None
    best = lab.best_is.model_dump()
    assert not any("oos" in key for key in best)  # nothing exists to highlight an OOS cell
    for metric in (*HIGHER_IS_BETTER, *LOWER_IS_BETTER):
        values = [getattr(row.strategy.is_, metric) for row in lab.rows]
        assert best[metric] == _best(values, metric in HIGHER_IS_BETTER), metric


@pytest.mark.ac("X-3")
def test_report_highlights_best_is_and_never_oos() -> None:
    ui_owed("X-3 (highlight rendering)")


# ---------------------------------------------------------------- X-4 no stop means no R


@pytest.mark.ac("X-4")
def test_config_without_a_stop_reports_percent_and_null_r() -> None:
    _, market = _lab_market()
    lab = trade_lab(STRATEGY, FIVE_CONFIGS[:2], market)  # Baseline has no stop
    no_stop, with_stop = lab.rows
    for seg in (no_stop.strategy.is_, no_stop.strategy.oos):
        if seg.n_trades:
            assert seg.expectancy_pct is not None
        assert seg.expectancy_r is None
    assert all(t.r_multiple is None and t.mae_r is None for t in lab.baseline_trades)
    assert with_stop.strategy.is_.expectancy_r is not None


@pytest.mark.ac("X-4")
def test_r_columns_show_na_with_a_footnote() -> None:
    ui_owed("X-4 (n/a cells and footnote)")


# ---------------------------------------------------------------- X-5 IS only guides


def _percentile(xs: list[float], q: float) -> float:
    """NumPy's default linear interpolation, written out."""
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _guides(trades: list[Trade]) -> tuple[float, float, float]:
    """Spec 0002 `guides_is` (owner ruling 2026-10-09): winner percentiles on adverse
    depth (`-mae_pct`), reported back as signed `mae_pct`, so p90 <= p75 <= 0."""
    depth = [-t.mae_pct for t in trades if t.return_pct > 0]
    return (
        -_percentile(depth, 0.75),
        -_percentile(depth, 0.90),
        statistics.median(t.mfe_pct for t in trades),
    )


@pytest.mark.ac("X-5")
def test_guides_use_baseline_is_trades_only() -> None:
    _, market = _lab_market()
    lab = trade_lab(STRATEGY, FIVE_CONFIGS, market)
    assert not lab.baseline_trades_truncated
    is_trades = [t for t in lab.baseline_trades if t.segment == "is"]
    expected = _guides(is_trades)
    with_oos = _guides(lab.baseline_trades)
    assert expected != with_oos, "fixture must be one where OOS trades would move the guides"
    got = lab.guides_is
    assert got.winner_mae_p90_pct is not None and got.winner_mae_p75_pct is not None
    assert got.winner_mae_p90_pct <= got.winner_mae_p75_pct <= 0
    assert got.winner_mae_p75_pct == pytest.approx(expected[0], abs=1e-6)
    assert got.winner_mae_p90_pct == pytest.approx(expected[1], abs=1e-6)
    assert got.mfe_median_pct == pytest.approx(expected[2], abs=1e-6)


# ---------------------------------------------------------------- X-7 budget


@pytest.mark.ac("X-7")
@pytest.mark.slow
def test_six_configs_and_baseline_finish_under_10_seconds_and_6_mb() -> None:
    """In process on a 500 ticker, 5 year market. The deployed number is a verify step."""
    tiny = build_market(random_walk_frames(n_tickers=3, n_bars=60, seed=1))
    six = [*FIVE_CONFIGS, config("Target", {"type": "target", "pct": 15})]
    trade_lab(STRATEGY, six, tiny)  # fail fast while the engine is a stub
    market = build_market(random_walk_frames(n_tickers=500, n_bars=1260, seed=3, churn=False))
    trade_lab(STRATEGY, six, market)  # warm
    started = time.perf_counter()
    result = trade_lab(STRATEGY, six, market)
    assert time.perf_counter() - started < 10.0
    assert len(result.model_dump_json(by_alias=True)) < 6_000_000


@cache
def _seed_42() -> Market:
    """The full history synthetic market (spec 0006) that spec 0009 AC-11 names."""
    return generate(42)


@pytest.mark.ac("X-7")
@pytest.mark.slow
@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.id)
def test_seed_42_six_configs_run_twice_equal_under_10_seconds_and_6_mb(
    template: TemplateOut,
) -> None:
    """Spec 0009 AC-11 on the generated seed 42 market, both templates, timed warm. The in
    process run is the CI gate; the deployed number is a verify step (ac-questions#perf)."""
    six = [*FIVE_CONFIGS, config("Target", {"type": "target", "pct": 15})]
    tiny = build_market(random_walk_frames(n_tickers=3, n_bars=60, seed=1))
    trade_lab(STRATEGY, six, tiny)  # fail fast on a stub
    market = _seed_42()
    first = trade_lab(template.rule, six, market)  # also warms the caches
    started = time.perf_counter()
    result = trade_lab(template.rule, six, market)
    assert time.perf_counter() - started < 10.0
    assert result == first
    assert result.entries.count > 0, "the budget must be measured on a run that trades"
    assert len(result.model_dump_json(by_alias=True)) < 6_000_000


# ---------------------------------------------------------------- X-8 per trade metrics only


def _metrics(trades: list[Trade]) -> dict[str, float | int | None]:
    n = len(trades)
    weeks = {t.entry_date.isocalendar()[:2] for t in trades}
    return {
        "n_trades": n,
        "distinct_weeks": len(weeks),
        "expectancy_per_bar_pct": (
            sum(t.return_pct for t in trades) / sum(t.bars_held for t in trades) if n else None
        ),
        "horizon_exit_pct": (
            sum(1 for t in trades if t.exit_reason == "horizon") / n * 100 if n else None
        ),
    }


def _walk(obj: Any) -> list[str]:
    if isinstance(obj, dict):
        return [k for key, v in obj.items() for k in (key, *_walk(v))]
    if isinstance(obj, list):
        return [k for v in obj for k in _walk(v)]
    return []


@pytest.mark.ac("X-8")
def test_trade_mode_has_no_portfolio_metrics() -> None:
    _, market = _lab_market()
    lab = trade_lab(STRATEGY, FIVE_CONFIGS, market)
    keys = set(_walk(lab.model_dump(mode="json", by_alias=True)))
    assert not keys & {"cagr_pct", "max_dd_pct", "sharpe", "equity", "benchmark"}


@pytest.mark.ac("X-8")
def test_trade_mode_metrics_match_a_hand_check() -> None:
    _, market = _lab_market()
    lab = trade_lab(STRATEGY, FIVE_CONFIGS, market)
    assert not lab.baseline_trades_truncated
    baseline = lab.rows[0].strategy
    for segment, got in (("is", baseline.is_), ("oos", baseline.oos)):
        expected = _metrics([t for t in lab.baseline_trades if t.segment == segment])
        assert got.n_trades == expected["n_trades"]
        assert got.distinct_weeks == expected["distinct_weeks"]
        for key in ("expectancy_per_bar_pct", "horizon_exit_pct"):
            want = expected[key]
            have = getattr(got, key)
            assert (have is None) == (want is None), key
            if want is not None:
                assert have == pytest.approx(want, abs=1e-6), key
    for row in lab.rows:
        for seg in (row.strategy.is_, row.strategy.oos):
            if seg.n_trades:
                assert seg.expectancy_per_bar_pct is not None
                assert seg.horizon_exit_pct is not None


# ---------------------------------------------------------------- X-9 horizon


@pytest.mark.ac("X-9")
def test_open_trade_exits_at_the_horizon_and_warns() -> None:
    # A steady climb never touches a 10% trail, so the trade is still open after 60 bars.
    n_bars, signal = 120, 3
    close = [10.0 * 1.002**k for k in range(n_bars)]
    frame = Frame(1, list(close), [c * 1.001 for c in close], [c * 0.999 for c in close], close)
    frame.volume[frame.bar(signal)] = 2_000_000.0
    market = build_market({"AAA": frame})
    configs = [
        config("Trail", {"type": "trail_pct", "pct": 10}),
        config("Time", {"type": "time", "bars": 5}),
    ]
    lab = trade_lab(VOLUME_SPIKE, configs, market, horizon_bars=60)
    (trade,) = lab.baseline_trades
    entry_bar = signal + 1
    exit_bar = entry_bar + 59  # the entry bar is bar 1, so bar 60 is entry + 59
    assert trade.exit_reason == "horizon"
    assert trade.exit_date == bar_date(exit_bar)
    assert trade.exit_price == pytest.approx(close[exit_bar - 1] * 0.999, abs=1e-9)
    assert trade.segment == "is"
    assert lab.rows[0].strategy.is_.horizon_exit_pct == pytest.approx(100.0)
    warned = [w.config_index for w in lab.warnings if w.code == "horizon_exits_over_10pct"]
    assert warned == [0]


@pytest.mark.ac("X-9")
def test_horizon_warning_badge_renders() -> None:
    ui_owed("X-9 (warning badge on the config row)")


# ---------------------------------------------------------------- X-10 random baseline


@pytest.mark.ac("X-10")
def test_random_baseline_matches_counts_is_seeded_and_edge_is_a_difference() -> None:
    _, market = _lab_market()
    lab = trade_lab(STRATEGY, FIVE_CONFIGS, market, seed=42)
    e = lab.entries
    assert e.random_is_count == e.is_count > 0
    assert e.random_oos_count == e.oos_count > 0
    for row in lab.rows:
        for seg in ("is_", "oos"):
            random_side = getattr(row.random, seg)
            strategy_side = getattr(row.strategy, seg)
            assert random_side.n_trades == strategy_side.n_trades, (row.name, seg)
            edge = getattr(row.edge, seg)
            for key in ("expectancy_pct", "expectancy_per_bar_pct", "win_rate_pct"):
                s, r, d = getattr(strategy_side, key), getattr(random_side, key), getattr(edge, key)
                if s is None or r is None:
                    assert d is None
                else:
                    assert d == pytest.approx(s - r, abs=1e-6), (row.name, seg, key)
    again: TradeLabResult = trade_lab(STRATEGY, FIVE_CONFIGS, market, seed=42)
    assert [r.random for r in again.rows] == [r.random for r in lab.rows]
    other = trade_lab(STRATEGY, FIVE_CONFIGS, market, seed=7)
    assert [r.random for r in other.rows] != [r.random for r in lab.rows]
