"""UI and honesty criteria U-1 to U-8 (doc 01 section 6.6).

The rendering half of each criterion belongs in `apps/web/tests/acceptance/` (Vitest against
the mocks, doc 02 section 15.4). The shell parts are written there (U-1 banner, U-2, U-5, U-6
structure, U-7 helpers), and so are the honesty components (U-4 counter, U-8 note; see
docs/qa/ac-questions.md#ui-tests); the rest waits for the pages.
Each ID keeps a pending placeholder here until every part of it is covered. Where a criterion
also depends on the contract (the data the page renders), that half is checked here through the
API and the OpenAPI document.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from acceptance.support import (
    build_market,
    config,
    random_walk_frames,
    trade_lab,
    ui_covered_by,
    ui_owed,
)
from engine.contracts import TEMPLATES, ExitConfig, Rule, pair_key, structure_key

OPENAPI = Path(__file__).resolve().parents[2] / "contracts" / "openapi.json"


def _schema(name: str) -> dict[str, Any]:
    doc = json.loads(OPENAPI.read_text(encoding="utf-8"))
    schema: dict[str, Any] = doc["components"]["schemas"][name]
    return schema


# ---------------------------------------------------------------- U-1 first visit


@pytest.mark.ac("U-1")
def test_first_visit_data_is_the_synthetic_market(client: TestClient) -> None:
    meta = client.get("/api/v1/meta").json()
    assert meta["data"] is not None, "no market loaded yet (scope feature 7)"
    assert meta["data"]["data_mode"] == "synthetic"
    assert client.get("/api/v1/templates").json()[0]["id"] == "breakout_52w"


@pytest.mark.ac("U-1")
def test_first_visit_opens_breakout_with_results_and_banner() -> None:
    ui_owed("U-1")


# ---------------------------------------------------------------- U-2 live badge


@pytest.mark.ac("U-2")
def test_live_mode_shows_the_survivors_badge_on_every_page() -> None:
    # Spec 0004 AC-8: the badge is the shell's data mode banner, checked on every page.
    ui_covered_by("U-2", "data-mode-banner.test.tsx")


# ---------------------------------------------------------------- U-3 assumptions header

U3_FIELDS = {
    "fill_model",
    "slippage_bps",
    "sizing",
    "max_positions",
    "entry_rising_edge",
    "cooldown_bars",
    "no_last_bar_entry",
    "configs",
    "horizon_bars",
    "seed",
    "delisting_rule",
    "oos_start",
    "data_mode",
    "data_version",
    "data_seed",
}


@pytest.mark.ac("U-3")
def test_assumptions_carry_every_header_field() -> None:
    schema = _schema("Assumptions")
    assert set(schema["properties"]) >= U3_FIELDS
    for mode in ("PortfolioResult", "TradeLabResult"):
        assert "assumptions" in _schema(mode)["required"], mode


@pytest.mark.ac("U-3")
def test_report_renders_the_assumptions_header() -> None:
    ui_owed("U-3")


# ---------------------------------------------------------------- U-4 trial counter


@pytest.mark.ac("U-4")
def test_backtest_returns_the_trial_keys_for_the_counter() -> None:
    market = build_market(random_walk_frames(n_tickers=10, n_bars=300, seed=4))
    rule = TEMPLATES[1].rule
    configs = [
        config("a", {"type": "time", "bars": 10}),
        config("b", {"type": "time", "bars": 5}, {"type": "stop_pct", "pct": 8}),
    ]
    lab = trade_lab(rule, configs, market)
    assert lab.trial.structure_key == structure_key(rule)
    assert lab.trial.pair_keys == [pair_key(rule, ExitConfig.model_validate(c)) for c in configs]
    # A numbers only tweak keeps the structure key but makes a new pair (a new trial).
    tweaked = Rule.model_validate(
        {
            **rule.model_dump(mode="json"),
            "conditions": [
                {**c, "right": {**c["right"], "mult": 1.02}} if c["right"]["kind"] == "ind" else c
                for c in rule.model_dump(mode="json")["conditions"]
            ],
        }
    )
    lab2 = trade_lab(tweaked, configs, market)
    assert lab2.trial.structure_key == lab.trial.structure_key
    assert set(lab2.trial.pair_keys).isdisjoint(lab.trial.pair_keys)


@pytest.mark.ac("U-4")
def test_counter_counts_new_pairs_and_warns_at_ten() -> None:
    # Counting, storage layout, the warning at 10 and the fallback are covered in Vitest
    # (`honesty.test.tsx`, spec 0004 AC-1 to AC-6); the counter inside the reports is owed.
    ui_owed("U-4 (counter in the portfolio and exit lab reports, features 9 and 12)")


# ---------------------------------------------------------------- U-5 to U-8


@pytest.mark.ac("U-5")
def test_slow_request_shows_warming_up_state() -> None:
    # Any request held past 1.5 s (the shell's first request and the WarmupNotice threshold on
    # fake timers) in `warmup.test.tsx`; the slow scan on `/` in `template-scan.test.tsx`.
    ui_covered_by("U-5", "warmup.test.tsx")


@pytest.mark.ac("U-6")
def test_layout_holds_at_375_px() -> None:
    ui_owed("U-6")


@pytest.mark.ac("U-7")
def test_422_paths_point_at_the_row_or_exit_field(client: TestClient) -> None:
    rule = TEMPLATES[0].rule.model_dump(mode="json")
    rule["conditions"][1]["right"]["n"] = 300  # row 2, right operand
    response = client.post("/api/v1/scan", json={"rule": rule})
    assert response.status_code == 422
    locs = [e["loc"] for e in response.json()["detail"]]
    assert ["body", "rule", "conditions", 1, "right", "ind", "n"] in locs

    good_rule = TEMPLATES[0].rule.model_dump(mode="json")
    configs = [
        config("ok", {"type": "time", "bars": 10}),
        config("bad", {"type": "time", "bars": 10}, {"type": "stop_pct", "pct": 40}),
    ]
    response = client.post("/api/v1/backtest", json={"rule": good_rule, "configs": configs})
    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"][:5] == ["body", "configs", 1, "exits", 1]
    assert error["loc"][-1] == "pct"
    assert error["ctx"] == {"min": 1, "max": 30}


@pytest.mark.ac("U-7")
def test_inline_error_shows_on_the_offending_row() -> None:
    ui_owed("U-7")


@pytest.mark.ac("U-8")
def test_procedure_note_renders_under_the_exit_lab_table() -> None:
    # The note's words are covered in Vitest (`honesty.test.tsx`, spec 0004 AC-7); its place
    # under the exit lab table is owed.
    ui_owed("U-8 (note directly under the exit lab table, feature 12)")
