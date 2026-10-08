"""Make QA's golden reference (`tests/golden/`) importable from the engine's unit tests."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_TESTS = Path(__file__).resolve().parents[2] / "tests"
if str(_REPO_TESTS) not in sys.path:
    sys.path.append(str(_REPO_TESTS))
