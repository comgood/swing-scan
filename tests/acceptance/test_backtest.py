"""Backtest and exit criteria B-1 to B-11 and B-13 to B-16 (doc 01 section 6.4).

These go through `engine.api.backtest` with tiny bar numbered fixtures. They do not replace the
owner's oracles in `tests/oracle/` (B-1 to B-10, B-14 to B-16); they are QA's independent check
of the same criteria through the public use case. Expected values are written as arithmetic.

Shared setup unless a test says otherwise: one ticker `AAA` at a flat 10 with a 0.5 band, a
volume spike on the signal bar `s` (rule `volume > 1,500,000`), so the entry is bar `s + 1` at
`open x 1.001 = 10.01`, and every exit fill is `x 0.999`.
"""

from __future__ import annotations

import time
from functools import cache
from typing import Any

import pytest

from acceptance.support import (
    VOLUME_SPIKE,
    Frame,
    bar_date,
    build_market,
    config,
    flat,
    ind,
    make_rule,
    portfolio,
    random_walk_frames,
    run_scan,
    set_bar,
    trade_lab,
    val,
)
from engine.contracts import TEMPLATES, Market, Rule, TemplateOut, Trade, entries_hash
from engine.synthetic import generate

FILL = 10.0 * 1.001  # 10.01
OUT = 0.999
TOL = 1e-9


def spiked(n_bars: int, signal_bar: int, *, spread: float = 0.5) -> Frame:
    frame = flat(1, n_bars, 10.0, spread)
    frame.volume[frame.bar(signal_bar)] = 2_000_000.0
    return frame


def only_trade(frame: Frame, exits: list[dict[str, Any]], end_bar: int | None = None) -> Trade:
    result = portfolio(VOLUME_SPIKE, exits, build_market({"AAA": frame}, end_bar=end_bar))
    assert len(result.trades) == 1, [t.model_dump() for t in result.trades]
    return result.trades[0]


def assert_trade(
    trade: Trade, *, entry_bar: int, entry: float, exit_bar: int, exit_: float, reason: str
) -> None:
    assert trade.ticker == "AAA"
    assert trade.entry_date == bar_date(entry_bar)
    assert trade.entry_price == pytest.approx(entry, abs=TOL)
    assert trade.exit_date == bar_date(exit_bar)
    assert trade.exit_price == pytest.approx(exit_, abs=TOL)
    assert trade.exit_reason == reason
    assert trade.return_pct == pytest.approx((exit_ / entry - 1) * 100, abs=1e-7)


STOP_PCT = {"type": "stop_pct", "pct": 8}
STOP_LEVEL = FILL * (1 - 0.08)  # 9.2092


# ---------------------------------------------------------------- B-1, B-2 percent stop


@pytest.mark.ac("B-1")
def test_percent_stop_fills_at_the_stop_level() -> None:
    frame = spiked(10, signal_bar=3)
    set_bar(frame, 5, 9.8, 9.9, 9.0, 9.5)  # low 9.0 <= 9.2092, open above it
    trade = only_trade(frame, [STOP_PCT])
    expected_exit = min(9.8, STOP_LEVEL) * OUT
    assert_trade(trade, entry_bar=4, entry=FILL, exit_bar=5, exit_=expected_exit, reason="stop_pct")


@pytest.mark.ac("B-2")
def test_gap_through_the_stop_fills_at_the_open() -> None:
    frame = spiked(10, signal_bar=3)
    set_bar(frame, 5, 9.0, 9.1, 8.8, 9.0)  # opens below 9.2092
    trade = only_trade(frame, [STOP_PCT])
    assert_trade(trade, entry_bar=4, entry=FILL, exit_bar=5, exit_=9.0 * OUT, reason="stop_pct")


# ---------------------------------------------------------------- B-3 ATR stop


@pytest.mark.ac("B-3")
def test_atr_stop_is_fill_minus_k_times_atr_at_the_signal_bar() -> None:
    # A flat 10 with high 11 and low 9 has a true range of 2.0 on every bar, so ATR(14) = 2.0
    # at the signal bar 20 whatever the seeding. Stop = 10.01 - 2 x 2.0 = 6.01.
    frame = spiked(40, signal_bar=20, spread=1.0)
    set_bar(frame, 23, 10.0, 11.0, 5.5, 7.0)
    trade = only_trade(frame, [{"type": "stop_atr", "k": 2, "n": 14}])
    assert_trade(
        trade, entry_bar=21, entry=FILL, exit_bar=23, exit_=(FILL - 4.0) * OUT, reason="stop_atr"
    )


# ---------------------------------------------------------------- B-4 percent target

TARGET = {"type": "target", "pct": 15}
TARGET_LEVEL = FILL * 1.15  # 11.5115


@pytest.mark.ac("B-4")
def test_target_fills_at_the_target_level() -> None:
    frame = spiked(10, signal_bar=3)
    set_bar(frame, 6, 10.5, 12.0, 10.4, 11.8)
    trade = only_trade(frame, [TARGET])
    expected = max(10.5, TARGET_LEVEL) * OUT
    assert_trade(trade, entry_bar=4, entry=FILL, exit_bar=6, exit_=expected, reason="target")


@pytest.mark.ac("B-4")
def test_gap_through_the_target_fills_at_the_open() -> None:
    frame = spiked(10, signal_bar=3)
    set_bar(frame, 6, 12.0, 12.5, 11.9, 12.2)
    trade = only_trade(frame, [TARGET])
    assert_trade(trade, entry_bar=4, entry=FILL, exit_bar=6, exit_=12.0 * OUT, reason="target")


@pytest.mark.ac("B-4")
def test_stop_wins_when_stop_and_target_touch_the_same_bar() -> None:
    frame = spiked(10, signal_bar=3)
    set_bar(frame, 6, 10.0, 12.0, 9.0, 10.0)  # high >= 11.5115 and low <= 9.2092
    trade = only_trade(frame, [STOP_PCT, TARGET])
    assert_trade(
        trade, entry_bar=4, entry=FILL, exit_bar=6, exit_=STOP_LEVEL * OUT, reason="stop_pct"
    )


# ---------------------------------------------------------------- B-5 trailing stop


@pytest.mark.ac("B-5")
def test_trailing_stop_levels_rise_with_the_high() -> None:
    # Entry fill exactly 10: open(4) = 10 / 1.001. Highs after entry 10, 12, 11.
    # Level bar 1 = 10 x 0.9 = 9.0; bar 2 = 10 x 0.9 = 9.0; bar 3 = 12 x 0.9 = 10.8.
    frame = spiked(12, signal_bar=3)
    set_bar(frame, 4, 10.0 / 1.001, 10.0, 9.5, 9.8)
    set_bar(frame, 5, 10.5, 12.0, 10.5, 11.5)
    set_bar(frame, 6, 10.9, 11.0, 10.7, 10.8)  # low 10.7 <= 10.8, open 10.9 above it
    trade = only_trade(frame, [{"type": "trail_pct", "pct": 10}])
    assert_trade(trade, entry_bar=4, entry=10.0, exit_bar=6, exit_=10.8 * OUT, reason="trail_pct")


# ---------------------------------------------------------------- B-6 close below MA


@pytest.mark.ac("B-6")
def test_close_below_sma_exits_at_the_next_open() -> None:
    frame = spiked(40, signal_bar=25)
    # Bar 27 closes at 9.0 < SMA(21) = (20 x 10 + 9) / 21 = 9.952: exit at open(28).
    set_bar(frame, 27, 10.0, 10.2, 8.9, 9.0)
    set_bar(frame, 28, 9.3, 9.6, 9.2, 9.5)
    trade = only_trade(frame, [{"type": "close_below_ma", "ma": "sma", "n": 21}])
    assert_trade(trade, entry_bar=26, entry=FILL, exit_bar=28, exit_=9.3 * OUT, reason="ma")


# ---------------------------------------------------------------- B-7 time exit


@pytest.mark.ac("B-7")
def test_time_exit_fills_at_the_close_of_bar_n() -> None:
    frame = spiked(12, signal_bar=3)
    set_bar(frame, 6, 10.2, 10.9, 10.1, 10.7)  # entry bar 4 is bar 1, so bar N = 3 is bar 6
    trade = only_trade(frame, [{"type": "time", "bars": 3}])
    assert_trade(trade, entry_bar=4, entry=FILL, exit_bar=6, exit_=10.7 * OUT, reason="time")


# ---------------------------------------------------------------- B-8 delisting


@pytest.mark.ac("B-8")
def test_delisting_exits_at_the_last_close() -> None:
    frame = spiked(8, signal_bar=3)  # AAA's last bar is 8; the dataset runs to bar 20
    set_bar(frame, 8, 10.2, 10.5, 10.0, 10.3)
    trade = only_trade(frame, [{"type": "time", "bars": 10}], end_bar=20)
    assert_trade(trade, entry_bar=4, entry=FILL, exit_bar=8, exit_=10.3 * OUT, reason="delisted")


# ---------------------------------------------------------------- B-9 MAE and MFE


def _pct(price: float) -> float:
    return (price / FILL - 1) * 100


@pytest.mark.ac("B-9")
def test_mae_mfe_on_a_stop_exit_caps_the_exit_bar_at_the_stop() -> None:
    frame = spiked(12, signal_bar=3)
    set_bar(frame, 4, 10.0, 10.4, 9.6, 10.0)
    set_bar(frame, 5, 10.0, 10.6, 9.5, 10.2)
    set_bar(frame, 6, 10.0, 10.8, 8.5, 9.0)  # intraday stop: contributes MAE 9.2092, MFE open 10
    trade = only_trade(frame, [STOP_PCT, {"type": "time", "bars": 10}])
    risk = FILL - STOP_LEVEL  # 0.8008
    assert trade.exit_reason == "stop_pct"
    assert trade.mae_pct == pytest.approx(_pct(STOP_LEVEL), abs=TOL)  # -8.0
    assert trade.mfe_pct == pytest.approx(_pct(10.6), abs=TOL)  # bar 6's 10.8 is excluded
    assert trade.mae_r == pytest.approx((STOP_LEVEL - FILL) / risk, abs=TOL)  # -1.0
    assert trade.mfe_r == pytest.approx((10.6 - FILL) / risk, abs=TOL)


@pytest.mark.ac("B-9")
def test_mae_mfe_on_a_target_exit_caps_the_exit_bar_at_the_target() -> None:
    frame = spiked(12, signal_bar=3)
    set_bar(frame, 4, 10.0, 10.4, 9.6, 10.0)
    set_bar(frame, 5, 10.5, 11.0, 9.4, 10.8)
    set_bar(frame, 6, 11.0, 12.0, 9.3, 11.6)  # intraday target: MFE 11.5115, MAE open 11
    trade = only_trade(frame, [TARGET, {"type": "time", "bars": 10}])
    assert trade.exit_reason == "target"
    assert trade.mfe_pct == pytest.approx(_pct(TARGET_LEVEL), abs=TOL)  # +15.0
    assert trade.mae_pct == pytest.approx(_pct(9.4), abs=TOL)  # bar 6's 9.3 is excluded
    assert trade.mae_r is None and trade.mfe_r is None  # no stop, so no R


@pytest.mark.ac("B-9")
def test_mae_mfe_on_a_time_exit_use_the_full_exit_bar() -> None:
    frame = spiked(12, signal_bar=3)
    set_bar(frame, 4, 10.0, 10.4, 9.6, 10.0)
    set_bar(frame, 5, 10.5, 11.0, 9.4, 10.8)
    set_bar(frame, 6, 10.5, 10.9, 9.3, 10.6)
    trade = only_trade(frame, [{"type": "time", "bars": 3}])
    assert trade.exit_reason == "time"
    assert trade.mae_pct == pytest.approx(_pct(9.3), abs=TOL)
    assert trade.mfe_pct == pytest.approx(_pct(11.0), abs=TOL)


# ---------------------------------------------------------------- B-10 look ahead

ALL_EXITS: list[dict[str, Any]] = [
    {"type": "stop_pct", "pct": 8},
    {"type": "stop_atr", "k": 2, "n": 14},
    {"type": "target", "pct": 15},
    {"type": "trail_pct", "pct": 10},
    {"type": "close_below_ma", "ma": "ema", "n": 21},
    {"type": "time", "bars": 30},
]


def _poison(frames: dict[str, Frame], after_bar: int) -> dict[str, Frame]:
    """Replace every bar after `after_bar` with wild but internally sane garbage."""
    out: dict[str, Frame] = {}
    for n, (ticker, f) in enumerate(frames.items()):
        g = Frame(
            f.start_bar, list(f.open), list(f.high), list(f.low), list(f.close), list(f.volume)
        )
        for k in range(max(after_bar + 1, f.start_bar), f.last_bar + 1):
            i = g.bar(k)
            level = 1.0 + ((k * 37 + n * 11) % 97)  # 1 to 97, unrelated to the real path
            g.open[i], g.close[i] = level, level * 1.3
            g.high[i], g.low[i] = level * 1.5, level * 0.5
            g.volume[i] = 1e9
        out[ticker] = g
    return out


@pytest.mark.ac("B-10")
@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.id)
def test_a_poisoned_future_changes_nothing_up_to_t(template: Any) -> None:
    frames = random_walk_frames(n_tickers=30, n_bars=460, seed=5)
    cut = 400
    clean = build_market(frames)
    dirty = build_market(_poison(frames, cut))
    end = bar_date(cut)
    rule = template.rule

    clean_p = portfolio(rule, ALL_EXITS, clean, end=end)
    dirty_p = portfolio(rule, ALL_EXITS, dirty, end=end)
    assert dirty_p.model_dump() == clean_p.model_dump()

    configs = [config("time only", {"type": "time", "bars": 10}), config("everything", *ALL_EXITS)]
    clean_t = trade_lab(rule, configs, clean, end=end)
    dirty_t = trade_lab(rule, configs, dirty, end=end)
    assert dirty_t.model_dump() == clean_t.model_dump()  # entries, random baseline and exits

    for bar in (cut - 20, cut):
        assert run_scan(rule, dirty, bar_date(bar)) == run_scan(rule, clean, bar_date(bar))
    assert clean_t.entries.count > 0, "the fixture must produce entries to mean anything"


# ---------------------------------------------------------------- B-11 slots and ranking


@pytest.mark.ac("B-11")
def test_top_ten_by_rs_fill_ten_slots_at_equity_over_ten() -> None:
    names = "ABCDEFGHIJKLMNO"  # alphabetical order is the reverse of the rs order on purpose
    frames: dict[str, Frame] = {}
    signal, n_bars = 200, 230
    for i, letter in enumerate(names):
        slope = 0.01 * (i + 1)  # higher i -> higher ret(126) -> higher rs(126)
        close = [10.0 + slope * t for t in range(1, signal + 1)]
        entry_open = close[-1]
        entry_close = entry_open * (1 + 0.001 * (i + 1))
        tail = [entry_close] * (n_bars - signal - 1)
        frame = Frame(
            1,
            [*close, entry_open, *tail],
            [*close, entry_close, *tail],
            [*close, entry_open, *tail],
            [*close, entry_close, *tail],
        )
        frame.volume[frame.bar(signal)] = 2_000_000.0
        frames[f"{letter}X"] = frame
    market = build_market(frames)
    result = portfolio(VOLUME_SPIKE, [{"type": "time", "bars": 20}], market, max_positions=10)

    entered = sorted(t.ticker for t in result.trades)
    assert entered == sorted(f"{names[i]}X" for i in range(5, 15))
    assert all(t.entry_date == bar_date(signal + 1) for t in result.trades)

    # Each slot is 100 / 10 = 10 of equity, so equity at the entry bar's close is
    # sum over the ten of 10 x close / fill, with fill = open x 1.001.
    expected = sum(10.0 * (1 + 0.001 * (i + 1)) / 1.001 for i in range(5, 15))
    point = next(p for p in result.equity if p.date == bar_date(signal + 1))
    assert point.value == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------- B-13 determinism and budget


@pytest.mark.ac("B-13")
def test_identical_inputs_give_identical_results() -> None:
    market = build_market(random_walk_frames(n_tickers=20, n_bars=320, seed=9))
    rule = TEMPLATES[1].rule
    exits = [{"type": "stop_pct", "pct": 8}, {"type": "time", "bars": 10}]
    assert portfolio(rule, exits, market) == portfolio(rule, exits, market)


@pytest.mark.ac("X-7")
def test_identical_inputs_give_identical_trade_lab_results() -> None:
    """B-13's determinism in trade mode. Spec 0007 AC-7 scopes B-13 to portfolio mode; spec 0009
    owns the trade mode run ("run twice equal" in its budget test), so this gates with X-7."""
    market = build_market(random_walk_frames(n_tickers=20, n_bars=320, seed=9))
    rule = TEMPLATES[1].rule
    exits = [{"type": "stop_pct", "pct": 8}, {"type": "time", "bars": 10}]
    configs = [config("a", *exits), config("b", {"type": "trail_pct", "pct": 10})]
    assert trade_lab(rule, configs, market) == trade_lab(rule, configs, market)


@cache
def _seed_42() -> Market:
    """The full history synthetic market (spec 0006) that spec 0007 AC-7 names."""
    return generate(42)


@pytest.mark.ac("B-13")
@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.id)
def test_seed_42_full_history_run_is_deterministic_under_3_seconds_and_6_mb(
    template: TemplateOut,
) -> None:
    """Spec 0007 AC-7 on the generated seed 42 market, both templates. The in process run is
    the CI gate; the deployed number is a verify step (ac-questions#perf)."""
    exits = [{"type": "stop_pct", "pct": 8}, {"type": "time", "bars": 20}]
    portfolio(VOLUME_SPIKE, exits, build_market({"AAA": spiked(10, 3)}))  # fail fast on a stub
    market = _seed_42()
    first = portfolio(template.rule, exits, market)  # also warms the caches
    started = time.perf_counter()
    result = portfolio(template.rule, exits, market)
    assert time.perf_counter() - started < 3.0
    assert result == first
    assert result.trades_total > 0, "the budget must be measured on a run that trades"
    assert len(result.model_dump_json(by_alias=True)) < 6_000_000


@pytest.mark.ac("B-13")
def test_500_ticker_random_walk_run_is_under_3_seconds_and_6_mb() -> None:
    exits = [{"type": "stop_pct", "pct": 8}, {"type": "time", "bars": 10}]
    portfolio(VOLUME_SPIKE, exits, build_market({"AAA": spiked(10, 3)}))  # fail fast on a stub
    market: Market = build_market(
        random_walk_frames(n_tickers=500, n_bars=1260, seed=3, churn=False)
    )
    rule = TEMPLATES[1].rule
    portfolio(rule, exits, market)  # warm
    started = time.perf_counter()
    result = portfolio(rule, exits, market)
    assert time.perf_counter() - started < 3.0
    assert len(result.model_dump_json(by_alias=True)) < 6_000_000


# ---------------------------------------------------------------- B-14 to B-16 entry rules

# Portfolio mode is feature 9 (spec 0007 AC-8); the trade mode halves gate with feature 12. B-14's
# trade mode check is X-1's (spec 0009 AC-1); B-15's and B-16's trade mode halves are their own,
# named in both specs' test plans, so those two IDs stay pending until feature 12 lands.

TIME_3 = [{"type": "time", "bars": 3}]
TIME_CONFIGS = [
    config("t3", {"type": "time", "bars": 3}),
    config("t5", {"type": "time", "bars": 5}),
]
BAR_OF = {bar_date(k): k for k in range(1, 400)}
CLOSE_ABOVE_5 = make_rule((ind("close"), ">", val(5)))
BREAKOUT_252 = make_rule((ind("close"), ">", ind("highest", n=252, offset=1)))


def _portfolio_entry_bars(market: Market, rule: Rule) -> list[tuple[str, int]]:
    return sorted((t.ticker, BAR_OF[t.entry_date]) for t in portfolio(rule, TIME_3, market).trades)


def _lab_entry_bars(market: Market, rule: Rule) -> list[tuple[str, int]]:
    lab = trade_lab(rule, TIME_CONFIGS, market)
    return sorted((t.ticker, BAR_OF[t.entry_date]) for t in lab.baseline_trades)


def _first_valid_market() -> Market:
    close = [10.0 + 0.01 * i for i in range(259)]  # bars 1..259 rising: true from bar 253
    close.append(5.0)  # bar 260: valid and false
    close += [20.0 + 0.01 * i for i in range(10)]  # bars 261..270: true again
    return build_market({"AAA": Frame(1, list(close), list(close), list(close), close)})


def _listing_day_market() -> Market:
    always = flat(50, 30)  # listed on bar 50, true from its first bar
    later = flat(50, 30)
    for k in range(50, 53):
        set_bar(later, k, 4.0, 4.2, 3.8, 4.0)  # false for 3 bars, then true from bar 53
    return build_market({"ALWAYS": always, "LATER": later}, end_bar=90)


@pytest.mark.ac("B-14")
def test_no_signal_on_the_first_valid_bar() -> None:
    # Only bar 261 is a signal, so the only entry fills on bar 262.
    assert _portfolio_entry_bars(_first_valid_market(), BREAKOUT_252) == [("AAA", 262)]


@pytest.mark.ac("B-14")
def test_no_signal_on_a_listing_day() -> None:
    assert _portfolio_entry_bars(_listing_day_market(), CLOSE_ABOVE_5) == [("LATER", 54)]


@pytest.mark.ac("X-1")
def test_trade_mode_has_no_signal_on_the_first_valid_bar_or_a_listing_day() -> None:
    """B-14 in the exit lab's entry list (X-1, spec 0009 AC-1)."""
    assert _lab_entry_bars(_first_valid_market(), BREAKOUT_252) == [("AAA", 262)]
    assert _lab_entry_bars(_listing_day_market(), CLOSE_ABOVE_5) == [("LATER", 54)]


def _last_bar_market() -> Market:
    gone = Frame(1, [4.0] * 10, [4.0] * 10, [4.0] * 10, [4.0] * 9 + [6.0])  # delists on bar 10
    gone.open[-1] = gone.high[-1] = 6.0
    end = Frame(1, [4.0] * 20, [4.0] * 20, [4.0] * 20, [4.0] * 19 + [6.0])  # data ends on bar 20
    end.open[-1] = end.high[-1] = 6.0
    return build_market({"GONE": gone, "END": end})


@pytest.mark.ac("B-15")
def test_no_portfolio_entry_on_a_last_bar() -> None:
    result = portfolio(CLOSE_ABOVE_5, TIME_3, _last_bar_market())
    assert result.trades == []
    assert [w.code for w in result.warnings] == ["no_entries"]


@pytest.mark.ac("B-15")
def test_no_entry_on_a_last_bar() -> None:
    """The trade mode half (spec 0007 and 0009 test plans), green with feature 12."""
    lab = trade_lab(CLOSE_ABOVE_5, TIME_CONFIGS, _last_bar_market())
    assert lab.entries.count == 0
    assert lab.baseline_trades == []
    assert [w.code for w in lab.warnings] == ["no_entries"]


def _cooldown_market() -> Market:
    close = [4.0] * 130
    for bar in (100, 105, 112):
        close[bar - 1] = 6.0
    return build_market({"AAA": Frame(1, list(close), list(close), list(close), close)})


@pytest.mark.ac("B-16")
def test_cooldown_accepts_100_and_112_in_every_config() -> None:
    """The trade mode half (spec 0007 and 0009 test plans), green with feature 12."""
    market = _cooldown_market()
    configs = [
        config("time 1", {"type": "time", "bars": 1}),
        config("stop and time", {"type": "stop_pct", "pct": 8}, {"type": "time", "bars": 20}),
        config("trail", {"type": "trail_pct", "pct": 10}),
    ]
    lab = trade_lab(CLOSE_ABOVE_5, configs, market)
    expected = [("AAA", bar_date(101)), ("AAA", bar_date(113))]
    assert [(t.ticker, t.entry_date) for t in lab.baseline_trades] == expected
    assert lab.entries.count == 2
    assert lab.entries.hash == entries_hash(expected)
    for row in lab.rows:
        assert row.strategy.is_.n_trades + row.strategy.oos.n_trades == 2, row.name


# One exit set per exit type, each closing the bar 101 trade well before bar 112: a held ticker's
# signal is skipped (spec 0007 AC-8), which would hide what the cooldown does. The fill is
# open(101) x 1.001 = 4.004 and every later bar is a flat 4.0.
PORTFOLIO_EXIT_SETS: dict[str, list[dict[str, Any]]] = {
    "time 1": [{"type": "time", "bars": 1}],
    "stop_pct and time": [{"type": "stop_pct", "pct": 8}, {"type": "time", "bars": 5}],
    "stop_atr and time": [{"type": "stop_atr", "k": 2, "n": 14}, {"type": "time", "bars": 5}],
    "target and time": [{"type": "target", "pct": 15}, {"type": "time", "bars": 5}],
    "trail_pct and time": [{"type": "trail_pct", "pct": 10}, {"type": "time", "bars": 5}],
    # sma(5) on bar 101 still holds bar 100's 6.0, so close 4.0 is below it
    "close_below_ma": [{"type": "close_below_ma", "ma": "sma", "n": 5}],
}


@pytest.mark.ac("B-16")
@pytest.mark.parametrize("exits", list(PORTFOLIO_EXIT_SETS.values()), ids=list(PORTFOLIO_EXIT_SETS))
def test_cooldown_applies_in_portfolio_mode(exits: list[dict[str, Any]]) -> None:
    result = portfolio(CLOSE_ABOVE_5, exits, _cooldown_market())
    assert [t.entry_date for t in result.trades] == [bar_date(101), bar_date(113)]
    assert BAR_OF[result.trades[0].exit_date] < 112
