"""UI and honesty criteria U-1 to U-8 (doc 01 section 6.6).

The rendering half of each criterion belongs in `apps/web/tests/acceptance/` (Vitest against
the mocks, doc 02 section 15.4): the shell parts (U-1 banner, U-2, U-5, U-6 structure, U-7
helpers), the honesty components (U-4 counter, U-8 note) and the two reports (U-3, U-4, U-7 and
U-8 on `/backtest`; see docs/qa/ac-questions.md#ui-tests). Each ID keeps a pointer here, or a
pending placeholder while a part of it is still owed (U-6 needs a browser). Where a criterion
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
    GeneratedApi,
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
def test_first_visit_data_is_the_synthetic_market(generated_api: GeneratedApi) -> None:
    # The API as deployed: a seed 42 synthetic market loaded at start (the session `client`
    # runs without data in CI). First visit: synthetic meta, Breakout first, and its scan answers.
    meta, templates = generated_api.run(
        ("GET", "/api/v1/meta", None), ("GET", "/api/v1/templates", None)
    )[0]
    assert meta["status"] == 200
    assert meta["body"]["data"] is not None, "no market loaded"
    assert meta["body"]["data"]["data_mode"] == "synthetic"
    assert templates["body"][0]["id"] == "breakout_52w"
    breakout = templates["body"][0]["rule"]
    scan = generated_api.run(("POST", "/api/v1/scan", {"rule": breakout}))[0][0]
    assert scan["status"] == 200, scan


@pytest.mark.ac("U-1")
def test_first_visit_opens_breakout_with_results_and_banner() -> None:
    # The banner on every page; the workspace opening on Breakout with its results, no sign up;
    # the builder's rows holding Breakout's rule (spec 0003 AC-3, spec 0005 AC-9, spec 0008).
    ui_covered_by(
        "U-1", "data-mode-banner.test.tsx", "template-scan.test.tsx", "rule-builder.test.tsx"
    )


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
def test_a_real_run_fills_every_header_field() -> None:
    """The schema names the fields; the header is only honest if a response carries values."""
    market = build_market(random_walk_frames(n_tickers=10, n_bars=300, seed=4))
    configs = [
        config("a", {"type": "time", "bars": 10}),
        config("b", {"type": "stop_pct", "pct": 8}),
    ]
    header = trade_lab(TEMPLATES[1].rule, configs, market).assumptions.model_dump()
    assert set(header) >= U3_FIELDS
    # Null by contract: trade mode sizes one unit per entry, and a market with no seed names its
    # version instead ("data version or seed"). Every other field carries a value.
    optional = {"max_positions", "data_seed"}
    assert [f for f in sorted(U3_FIELDS - optional) if header[f] is None] == []
    assert header["data_version"]


@pytest.mark.ac("U-3")
def test_report_renders_the_assumptions_header() -> None:
    # Both reports: the portfolio one (feature 9, spec 0007 AC-12) and the exit lab's, with the
    # horizon, the seed, the overlap rule and one exit line per config (feature 12, AC-19).
    ui_covered_by("U-3", "backtest-report.test.tsx", "exit-lab-report.test.tsx")


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
    # (`honesty.test.tsx`, spec 0004 AC-1 to AC-6); the counter inside each report, one pair per
    # config and no count on a failed run, in the two page files.
    ui_covered_by("U-4", "honesty.test.tsx", "backtest-report.test.tsx", "exit-lab-report.test.tsx")


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
    # Written in Vitest: the builder rows and the one config exit form (`rule-builder.test.tsx`,
    # left and tagged right side paths after the U-7-loc ruling (a)), the shared helpers
    # (`errors-422.test.tsx`), and the exit lab's config editor, where a 422 lands on the config
    # and the exit field its `loc` names (`exit-lab-report.test.tsx`, spec 0009 AC-20).
    ui_covered_by("U-7", "rule-builder.test.tsx", "errors-422.test.tsx", "exit-lab-report.test.tsx")


@pytest.mark.ac("U-8")
def test_procedure_note_renders_under_the_exit_lab_table() -> None:
    # The note's words are covered in Vitest (`honesty.test.tsx`, spec 0004 AC-7); its place
    # directly under the exit lab table in `exit-lab-report.test.tsx` (spec 0009 AC-18).
    ui_covered_by("U-8", "honesty.test.tsx", "exit-lab-report.test.tsx")
