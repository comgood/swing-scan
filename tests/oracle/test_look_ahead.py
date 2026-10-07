"""Look ahead oracle B-10, the poisoned future (doc 01 section 6.4, doc 02 section 7.6).

Every bar after T is replaced with valid garbage. Backtesting to T must give exactly the
same result as on the clean market: both templates, every exit type in one config, both
loops, entry signals with edge validity and cooldown, and the seeded random baseline.
"""

from __future__ import annotations

from typing import Any

import pytest

from engine.contracts import TEMPLATES

from ._oracle import bar_date, config, lab, portfolio, random_walk_market

SEED = 20260507
TICKERS = 30
BARS = 500
T = 400

ALL_EXITS: list[dict[str, Any]] = [
    {"type": "stop_pct", "pct": 8},
    {"type": "stop_atr", "k": 2, "n": 14},
    {"type": "target", "pct": 15},
    {"type": "trail_pct", "pct": 10},
    {"type": "close_below_ma", "ma": "sma", "n": 21},
    {"type": "time", "bars": 10},
]
LAB_CONFIGS = [
    config("every exit", *ALL_EXITS),
    config("stop and time", {"type": "stop_pct", "pct": 5}, {"type": "time", "bars": 5}),
]

CLEAN = random_walk_market(seed=SEED, tickers=TICKERS, bars=BARS)
POISONED = random_walk_market(seed=SEED, tickers=TICKERS, bars=BARS, poison_after=T)
TEMPLATE_RULES = {t.id: t.rule.model_dump(mode="json") for t in TEMPLATES}


@pytest.mark.parametrize("template", sorted(TEMPLATE_RULES))
def test_b10_portfolio_mode_ignores_everything_after_t(template: str) -> None:
    rule_json = TEMPLATE_RULES[template]

    clean = portfolio(rule_json, ALL_EXITS, CLEAN, end=bar_date(T).isoformat())
    poisoned = portfolio(rule_json, ALL_EXITS, POISONED, end=bar_date(T).isoformat())

    assert clean.trades_total > 0, "the fixture must produce trades, or the test proves nothing"
    assert poisoned.model_dump(mode="json") == clean.model_dump(mode="json")


@pytest.mark.parametrize("template", sorted(TEMPLATE_RULES))
def test_b10_trade_mode_and_random_baseline_ignore_everything_after_t(template: str) -> None:
    rule_json = TEMPLATE_RULES[template]

    clean = lab(rule_json, LAB_CONFIGS, CLEAN, end=bar_date(T).isoformat(), seed=42)
    poisoned = lab(rule_json, LAB_CONFIGS, POISONED, end=bar_date(T).isoformat(), seed=42)

    assert clean.entries.count > 0, "the fixture must produce entries, or the test proves nothing"
    assert poisoned.model_dump(mode="json") == clean.model_dump(mode="json")


def test_b10_the_poison_really_changes_the_data_after_t() -> None:
    clean = CLEAN.bars.filter(CLEAN.bars["date"] > bar_date(T))
    poisoned = POISONED.bars.filter(POISONED.bars["date"] > bar_date(T))
    same_up_to_t = CLEAN.bars.filter(CLEAN.bars["date"] <= bar_date(T)).equals(
        POISONED.bars.filter(POISONED.bars["date"] <= bar_date(T))
    )

    assert same_up_to_t
    assert clean.height == poisoned.height > 0
    assert not clean.equals(poisoned)
