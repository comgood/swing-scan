"""Write `contracts/openapi.json` from the FastAPI app (`make openapi`, spec 0002 AC-1).

Sorted keys and no server URL, so the file only changes when a contract changes.
"""

from __future__ import annotations

import json
from pathlib import Path

from api.main import app

OUT = Path(__file__).resolve().parents[1] / "contracts" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    schema.pop("servers", None)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(Path.cwd()) if OUT.is_relative_to(Path.cwd()) else OUT}")


if __name__ == "__main__":
    main()
