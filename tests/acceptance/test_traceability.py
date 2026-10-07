"""Meta tests: the gate inputs agree with each other and cover every MUST criterion.

These carry `harness`, not an ID, so they always block CI.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from acceptance.gate import (
    MUST_IDS,
    STATUS_PATH,
    STRETCH_IDS,
    StatusFileError,
    ac_ids_in_source,
    load_status,
    parse_status,
)

HERE = Path(__file__).parent
MATRIX = HERE.parents[1] / "docs" / "qa" / "traceability.md"
ROW = re.compile(r"^\|\s*(?P<id>[A-Z]-\d+[A-Z]?)\s*\|")

pytestmark = pytest.mark.harness


def _matrix_rows() -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        if ROW.match(line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            assert cells[0] not in rows, f"{cells[0]} has two matrix rows"
            rows[cells[0]] = cells
    return rows


def _ids_by_file() -> dict[str, set[str]]:
    return {p.name: ac_ids_in_source(p) for p in sorted(HERE.glob("test_*.py"))}


def test_must_list_matches_doc_01() -> None:
    assert len(MUST_IDS) == len(set(MUST_IDS)) == 52
    assert not set(MUST_IDS) & set(STRETCH_IDS)


def test_status_file_lists_exactly_the_must_ids() -> None:
    status = load_status()
    assert list(status) == list(MUST_IDS)


def test_every_must_id_has_an_acceptance_test() -> None:
    covered = set().union(*_ids_by_file().values())
    missing = [i for i in MUST_IDS if i not in covered]
    assert not missing, f"no acceptance test for {missing}"
    unknown = sorted(covered - set(MUST_IDS))
    assert not unknown, f"tests name IDs outside the MUST list: {unknown}"


def test_matrix_has_one_row_per_must_id_with_the_gate_status() -> None:
    rows = _matrix_rows()
    assert list(rows) == list(MUST_IDS)
    status = load_status()
    for crit, cells in rows.items():
        assert cells[6] == status[crit], (
            f"{crit}: matrix says {cells[6]}, status.yaml {status[crit]}"
        )


def test_matrix_test_files_carry_the_id() -> None:
    by_file = _ids_by_file()
    for crit, cells in _matrix_rows().items():
        files = re.findall(r"`(test_[a-z_]+\.py)`", cells[3])
        assert files, f"{crit}: no test file in the matrix"
        for name in files:
            assert name in by_file, f"{crit}: {name} does not exist"
            assert crit in by_file[name], f"{crit}: {name} has no test marked with it"


def test_matrix_totals_line_matches_status() -> None:
    status = load_status()
    required = sum(1 for s in status.values() if s == "required")
    text = MATRIX.read_text(encoding="utf-8")
    expected = f"{len(status)} MUST criteria, {required} required, {len(status) - required} pending"
    assert expected in text


@pytest.mark.parametrize(
    "text",
    [
        "D-1 pending",  # no colon
        "D-1: done",  # unknown status
        "D-1: pending\nD-1: required",  # duplicate
    ],
)
def test_status_parser_rejects_bad_lines(text: str) -> None:
    with pytest.raises(StatusFileError):
        parse_status(text)


def test_status_parser_ignores_comments_and_blanks() -> None:
    assert parse_status("# head\n\nR-6: required  # flipped\n") == {"R-6": "required"}


def test_status_path_is_the_committed_file() -> None:
    assert STATUS_PATH.name == "status.yaml" and STATUS_PATH.parent == HERE
