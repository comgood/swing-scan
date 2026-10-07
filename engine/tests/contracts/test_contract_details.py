"""Gaps the first pass left: frozen hash formulas, one sided bounds, column dedupe, meta rules.

Each test names the acceptance criterion or Value sourcing row it locks (spec 0002).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from engine.contracts import (
    DataMeta,
    ExitConfig,
    Rule,
    ScanRequest,
    Trade,
    entries_hash,
    pair_key,
    scan_columns,
    structure_key,
)
from engine.data.fixtures import FrameSpec, make_market

from .conftest import cond, ind, only_error


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ---- Frozen hash formulas (Value sourcing: trial keys, entries hash) ---------------------


def test_structure_key_is_sha256_of_the_canonical_shape_array() -> None:  # covers: AC-9
    rule = Rule.model_validate(
        {
            "name": "R",
            "conditions": [
                cond(ind("close"), ind("highest", 252, offset=1)),
                cond(ind("close"), {"kind": "value", "value": 5}),
            ],
        }
    )
    assert structure_key(rule) == sha('[["close",">","highest"],["close",">","value"]]')


def test_pair_key_is_sha256_of_sorted_compact_json_without_names() -> None:  # covers: AC-9
    rule = Rule.model_validate({"name": "R", "conditions": [cond(ind("close"))]})
    config = ExitConfig.model_validate(
        {"name": "C", "exits": [{"type": "time", "bars": 5}, {"type": "stop_pct", "pct": 8}]}
    )
    payload = {
        "rule": [c.model_dump(mode="json") for c in rule.conditions],
        "config": [
            {"type": "stop_pct", "pct": 8.0},
            {"type": "time", "bars": 5},
        ],
    }
    expected = sha(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    assert pair_key(rule, config) == expected


def test_entries_hash_is_sha256_of_sorted_ticker_date_lines() -> None:
    entries = [("BBB", date(2024, 1, 3)), ("AAA", date(2024, 1, 2))]
    assert entries_hash(entries) == sha("AAA|2024-01-02\nBBB|2024-01-03")


def test_entries_hash_of_no_entries_is_the_empty_string_hash() -> None:
    assert entries_hash([]) == sha("")


# ---- Scan columns (Value sourcing: columns) --------------------------------------------


def test_scan_columns_dedupe_operands_and_skip_values_in_first_appearance_order() -> None:
    rule = Rule.model_validate(
        {
            "name": "R",
            "conditions": [
                cond(ind("ema", 21), ind("ema", 21, offset=5)),
                cond(ind("close"), ind("ema", 21)),
                cond(ind("close"), {"kind": "value", "value": 5}),
            ],
        }
    )
    assert scan_columns(rule) == ["ema(21)", "ema(21)[5]", "close"]


def test_scan_columns_keep_operands_that_differ_only_in_mult() -> None:
    rule = Rule.model_validate(
        {"name": "R", "conditions": [cond(ind("ema", 21), ind("ema", 21, mult=1.01))]}
    )
    assert scan_columns(rule) == ["ema(21)", "1.01×ema(21)"]


# ---- Requests -------------------------------------------------------------------------


def test_scan_as_of_defaults_to_null_meaning_the_last_session() -> None:  # covers: AC-5
    request = ScanRequest.model_validate(
        {"rule": {"name": "R", "conditions": [cond(ind("close"))]}}
    )
    assert request.as_of is None


def test_scan_as_of_accepts_an_iso_date() -> None:  # covers: AC-4
    request = ScanRequest.model_validate(
        {"rule": {"name": "R", "conditions": [cond(ind("close"))]}, "as_of": "2025-06-30"}
    )
    assert request.as_of == date(2025, 6, 30)


@pytest.mark.parametrize("op", ["==", "crosses", ""])
def test_unknown_operator_lists_the_allowed_ones(op: str) -> None:  # covers: AC-2
    data = {"name": "R", "conditions": [{**cond(ind("close")), "op": op}]}
    error = only_error(Rule, data)
    assert error["type"] == "literal_error"
    assert error["loc"] == ("conditions", 0, "op")
    assert "'crosses_above'" in error["ctx"]["expected"]


# ---- One sided bounds on responses ---------------------------------------------------


def trade(**overrides: Any) -> dict[str, Any]:
    base = {
        "ticker": "AAA",
        "entry_date": "2024-01-02",
        "entry_price": 10.0,
        "exit_date": "2024-01-05",
        "exit_price": 11.0,
        "return_pct": 10.0,
        "bars_held": 3,
        "exit_reason": "target",
        "r_multiple": None,
        "mae_pct": -2.0,
        "mfe_pct": 12.0,
        "mae_r": None,
        "mfe_r": None,
        "segment": "is",
    }
    return {**base, **overrides}


def test_a_valid_trade_builds() -> None:
    assert Trade.model_validate(trade()).segment == "is"


def test_mae_above_zero_reports_only_the_max() -> None:  # covers: AC-14
    error = only_error(Trade, trade(mae_pct=0.5))
    assert error["type"] == "out_of_range"
    assert error["ctx"] == {"max": 0}


def test_mfe_below_zero_reports_only_the_min() -> None:  # covers: AC-14
    error = only_error(Trade, trade(mfe_pct=-0.5))
    assert error["ctx"] == {"min": 0}


def test_zero_mae_and_mfe_are_allowed() -> None:
    assert Trade.model_validate(trade(mae_pct=0.0, mfe_pct=0.0)).mae_pct == 0.0


def test_unknown_exit_reason_is_rejected() -> None:
    assert only_error(Trade, trade(exit_reason="stop"))["type"] == "literal_error"


# ---- Dataset meta ---------------------------------------------------------------------


def meta(**overrides: Any) -> dict[str, Any]:
    base = {
        "data_mode": "synthetic",
        "seed": 42,
        "data_version": "synthetic:v1",
        "start": "2021-01-04",
        "end": "2025-12-31",
        "n_tickers": 500,
        "survivors_only": False,
        "benchmark": "SYN-INDEX",
    }
    return {**base, **overrides}


def test_a_synthetic_dataset_needs_its_seed() -> None:  # covers: AC-10
    with pytest.raises(ValidationError, match="seed"):
        DataMeta.model_validate(meta(seed=None))


def test_a_fixture_dataset_may_be_unseeded() -> None:  # covers: AC-11
    assert DataMeta.model_validate(meta(seed=None, data_version="fixture:x")).seed is None


def test_a_live_dataset_needs_no_seed() -> None:
    assert DataMeta.model_validate(meta(data_mode="live", seed=None)).data_mode == "live"


def test_market_is_immutable() -> None:
    market = make_market({"AAA": FrameSpec(1, [1.0, 2.0])})
    with pytest.raises(FrozenInstanceError):
        market.meta = market.meta  # type: ignore[misc]
