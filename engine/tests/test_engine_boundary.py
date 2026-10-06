"""The engine must stay free of web frameworks so QA can test it directly (spec 0001)."""

import subprocess
import sys


def test_engine_imports_without_web_frameworks() -> None:
    code = (
        "import sys, engine; "
        "bad = [m for m in ('fastapi', 'starlette', 'uvicorn') if m in sys.modules]; "
        "print(','.join(bad))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == ""
