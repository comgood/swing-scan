"""Oracle guard: block commits that touch tests/oracle/ unless the owner opts in.

The oracles are owner approved and agents never edit them (doc 02 section 15.4). The owner
commits oracle changes with `ORACLE_EDIT_OK=1 git commit ...`. CI enforces the real gate:
a PR that touches tests/oracle/ needs the `oracle-approved` label.
"""

from __future__ import annotations

import os
import sys

ORACLE_DIR = "tests/oracle/"


def main(argv: list[str]) -> int:
    touched = [path for path in argv if path.startswith(ORACLE_DIR)]
    if not touched or os.environ.get("ORACLE_EDIT_OK") == "1":
        return 0
    print("Oracle guard blocked this commit. These files are owner only:")
    print("\n".join(f"  {path}" for path in touched))
    print("Agents never edit tests/oracle/. If you are the owner: ORACLE_EDIT_OK=1 git commit ...")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
