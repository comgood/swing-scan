"""The pending or required gate for the acceptance suite (doc 02 section 15.4).

`status.yaml` maps every MUST criterion ID from doc 01 to `pending` or `required`. The
conftest turns every test whose IDs are all `pending` into a non strict xfail, so it runs and
reports but never fails CI. A test that carries at least one `required` ID runs normally and
blocks CI when it fails. QA flips an ID to `required` once its tests pass on `main`.

The file format is a flat `ID: status` mapping with `#` comments. It is parsed here with a
small strict reader so the suite needs no YAML dependency.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Literal, cast

Status = Literal["pending", "required"]

STATUS_PATH = Path(__file__).with_name("status.yaml")

# Every MUST criterion in doc 01 section 6, in document order.
MUST_IDS: tuple[str, ...] = (
    *(f"D-{i}" for i in range(1, 7)),
    *(f"R-{i}" for i in range(1, 11)),
    *(f"S-{i}" for i in range(1, 5)),
    *(f"B-{i}" for i in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16)),
    *(f"X-{i}" for i in (1, 2, 3, 4, 5, 7, 8, 9, 10)),
    *(f"U-{i}" for i in range(1, 9)),
)

# Stretch criteria (doc 01 section 5.3). They get no row and no test until picked up.
STRETCH_IDS: tuple[str, ...] = ("S-5", "B-4R", "B-12", "X-5S", "X-6")

_LINE = re.compile(r"^(?P<id>[A-Z]-\d+[A-Z]?)\s*:\s*(?P<status>[a-z]+)\s*$")


class StatusFileError(ValueError):
    """`status.yaml` is malformed, has duplicates, or does not match the MUST list."""


def parse_status(text: str) -> dict[str, Status]:
    """Parse the flat `ID: status` mapping. Raises on any line it does not understand."""
    out: dict[str, Status] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = _LINE.match(line)
        if match is None:
            raise StatusFileError(f"status.yaml line {number}: cannot parse {raw!r}")
        crit, status = match["id"], match["status"]
        if status not in ("pending", "required"):
            raise StatusFileError(
                f"status.yaml line {number}: {crit} has status {status!r}, "
                "expected 'pending' or 'required'"
            )
        if crit in out:
            raise StatusFileError(f"status.yaml line {number}: {crit} is listed twice")
        out[crit] = cast(Status, status)
    return out


def load_status(path: Path = STATUS_PATH) -> dict[str, Status]:
    """Read `status.yaml` and check that it lists exactly the MUST IDs."""
    status = parse_status(path.read_text(encoding="utf-8"))
    missing = [i for i in MUST_IDS if i not in status]
    extra = [i for i in status if i not in MUST_IDS]
    if missing or extra:
        raise StatusFileError(
            f"status.yaml must list exactly the MUST IDs. Missing: {missing}. Unknown: {extra}."
        )
    return status


def ac_ids_in_source(path: Path) -> set[str]:
    """Every ID passed to `pytest.mark.ac(...)` in a test file, found statically.

    Reading the source (not the collected items) keeps the coverage check independent of
    `-k` selections and of which files a run happens to collect.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "ac":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    found.add(arg.value)
    return found
