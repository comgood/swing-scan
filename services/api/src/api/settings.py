"""Runtime settings read from environment variables (spec 0001, Configuration required)."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

DATA_MODES = ("synthetic", "live")
LOOPBACK = "127.0.0.1"


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def bound_host(argv: Sequence[str], env: Mapping[str, str]) -> str:
    """The address uvicorn binds, resolved the way uvicorn does: `--host`, then
    `UVICORN_HOST`, then its own default `127.0.0.1`."""
    for i, arg in enumerate(argv):
        if arg == "--host" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--host="):
            return arg.split("=", 1)[1]
    return env.get("UVICORN_HOST", LOOPBACK)


def live_mode_problems(argv: Sequence[str], env: Mapping[str, str]) -> list[str]:
    """Why live mode may not start here; empty only on your own machine (D-5, spec 0001)."""
    problems = []
    if env.get("AWS_LAMBDA_FUNCTION_NAME"):
        problems.append("running on AWS Lambda")
    if env.get("CI"):
        problems.append("running in CI")
    host = bound_host(argv, env)
    if host != LOOPBACK:
        problems.append(f"bound to {host!r}, not {LOOPBACK}")
    return problems


@dataclass(frozen=True)
class Settings:
    data_mode: str
    allowed_origins: list[str]
    allowed_origin_regex: str | None

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, argv: Sequence[str] | None = None
    ) -> Settings:
        env = os.environ if env is None else env
        argv = sys.argv if argv is None else argv
        data_mode = env.get("DATA_MODE", "synthetic")
        if data_mode not in DATA_MODES:
            raise RuntimeError(f"DATA_MODE={data_mode!r} is not one of {DATA_MODES}.")
        if data_mode == "live" and (problems := live_mode_problems(argv, env)):
            raise RuntimeError(
                "DATA_MODE=live runs only on your machine with the API bound to "
                f"{LOOPBACK} (D-5); refusing to start: {'; '.join(problems)}."
            )
        return cls(
            data_mode=data_mode,
            allowed_origins=_split(env.get("ALLOWED_ORIGINS", "http://localhost:3000")),
            allowed_origin_regex=env.get("ALLOWED_ORIGIN_REGEX") or None,
        )
