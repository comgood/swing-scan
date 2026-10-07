"""Data leak guard (D-6): block market data files and API keys from being committed.

Real market data and private research must never reach the public repo (vendor terms,
spec 0001). Pre-commit passes the staged file paths; `--all` checks every tracked file.
gitleaks covers generic secrets; this adds the project specific paths and Alpaca keys.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

BLOCKED_DIRS = ("data", "research")
BLOCKED_SUFFIXES = (".parquet",)
DATA_SUFFIXES_UNDER_BLOCKED_DIRS = (".parquet", ".csv")

KEY_PATTERNS = (
    # Alpaca key IDs: PK (paper), AK (live) or CK, then 18 uppercase letters or digits.
    re.compile(r"\b[PAC]K[A-Z0-9]{18}\b"),
    # Any Alpaca variable assigned a non empty value (empty placeholders are fine).
    re.compile(r"ALPACA_API_(?:KEY_ID|SECRET_KEY)\s*[=:]\s*['\"]?[A-Za-z0-9/+]{16,}"),
)


def path_problem(path: str) -> str | None:
    parts = PurePosixPath(path).parts
    if parts and parts[0] in BLOCKED_DIRS:
        return f"files under {parts[0]}/ must never be committed"
    if path.endswith(BLOCKED_SUFFIXES):
        return "parquet files must never be committed"
    if any(p in BLOCKED_DIRS for p in parts) and path.endswith(DATA_SUFFIXES_UNDER_BLOCKED_DIRS):
        return "market data files must never be committed"
    return None


def content_problem(path: str) -> str | None:
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return None  # deleted or unreadable; nothing to scan
    if b"\0" in raw[:8192]:
        return None  # binary
    text = raw.decode("utf-8", errors="ignore")
    for pattern in KEY_PATTERNS:
        if pattern.search(text):
            return "looks like it contains an Alpaca API key"
    return None


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


def main(argv: list[str]) -> int:
    paths = tracked_files() if argv == ["--all"] else argv
    problems = [
        f"  {path}: {problem}"
        for path in paths
        if (problem := path_problem(path) or content_problem(path))
    ]
    if problems:
        print("Data leak guard (D-6) blocked this commit:")
        print("\n".join(problems))
        print("Keep market data in data/ (gitignored) and keys in .env only.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
