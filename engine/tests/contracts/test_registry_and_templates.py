"""AC-7, AC-8 and the scan column label grammar."""

from __future__ import annotations

import pytest

from engine.contracts import (
    INDICATOR_SPECS,
    TEMPLATES,
    IndOperand,
    Rule,
    ValueOperand,
    column_label,
)


def test_registry_lists_all_14_indicators() -> None:
    assert len(INDICATOR_SPECS) == 14
    price = {"open", "high", "low", "close", "volume"}
    for name, spec in INDICATOR_SPECS.items():
        assert spec.name == name
        if name in price:
            assert not spec.windowed and spec.n_min is None and spec.n_max is None
        else:
            assert spec.windowed and spec.n_min == 2
            assert spec.n_max == (50 if name == "rsi" else 252)
            assert spec.n_default == (126 if name == "rs" else None)


def test_templates_are_the_two_from_doc_02() -> None:
    assert [t.id for t in TEMPLATES] == ["breakout_52w", "pullback_ema21"]


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.id)
def test_each_template_validates_and_has_a_visible_price_filter(template: object) -> None:
    rule = Rule.model_validate(template.rule.model_dump())  # type: ignore[attr-defined]
    price_filters = [
        c
        for c in rule.conditions
        if c.left.ind == "close"
        and c.op == ">"
        and isinstance(c.right, ValueOperand)
        and c.right.value == 5
    ]
    assert len(price_filters) == 1


@pytest.mark.parametrize(
    ("operand", "label"),
    [
        ({"ind": "close"}, "close"),
        ({"ind": "highest", "n": 252, "offset": 1}, "highest(252)[1]"),
        ({"ind": "avg_volume", "n": 50, "mult": 1.5}, "1.5×avg_volume(50)"),
        ({"ind": "ema", "n": 21, "offset": 5}, "ema(21)[5]"),
        ({"ind": "ema", "n": 21, "mult": 1.01}, "1.01×ema(21)"),
        ({"ind": "rs"}, "rs(126)"),
        ({"ind": "sma", "n": 50, "mult": 0.25, "offset": 2}, "0.25×sma(50)[2]"),
    ],
)
def test_column_label_golden_cases(operand: dict[str, object], label: str) -> None:
    assert column_label(IndOperand.model_validate({"kind": "ind", **operand})) == label
