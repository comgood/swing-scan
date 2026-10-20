"""Runtime settings read from environment variables (spec 0001, Configuration required)."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

DATA_MODES = ("synthetic", "live")
LOOPBACK = "127.0.0.1"

DEFAULT_ORIGINS = "http://127.0.0.1:3000,http://localhost:3000"
"""Both spellings of the dev server, on purpose (spec 0015).

The session cookie is `SameSite=Lax`, and a browser compares hostnames while ignoring ports:
`localhost` and `127.0.0.1` are different sites, so a page served from `localhost:3000` never
sends the cookie to the API on `127.0.0.1:8000`. **Sign in works only from
`http://127.0.0.1:3000`.** `localhost` stays allowed because dropping it would break scanning
and backtesting for anyone who opens the old address, which has nothing to do with accounts.
"""


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


AUTH_SECRET_ENV = "AUTH_SECRET"  # noqa: S105  # the variable's name, not a secret
AUTH_SECRET_MIN = 32
"""Shortest `AUTH_SECRET` worth having, in characters: `openssl rand -hex 32` gives 64."""


def saved_rules_problems(argv: Sequence[str], env: Mapping[str, str]) -> list[str]:
    """Why saved rules and accounts may not run here; empty only on your own machine.

    Three gates now, not two (spec 0014, then spec 0015). Without a database there is nothing
    to write to. Without a signing key nobody can be signed in, and a rule now belongs to an
    account, so the two surfaces share one gate rather than drifting apart; a key too short to
    be worth signing with counts as absent, because a weak key is worse than no feature. And
    the same host rules that keep live prices off the public API keep the write surface off it
    too, so a `DATABASE_URL` set on Lambda by accident cannot open a write endpoint.

    Every reason is collected rather than the first one returned, so the 501 body can name the
    thing you actually have to fix.
    """
    problems = []
    if not env.get("DATABASE_URL"):
        problems.append("no DATABASE_URL is configured")
    secret = env.get(AUTH_SECRET_ENV, "")
    if not secret:
        problems.append(f"no {AUTH_SECRET_ENV} is configured")
    elif len(secret) < AUTH_SECRET_MIN:
        problems.append(
            f"{AUTH_SECRET_ENV} is shorter than {AUTH_SECRET_MIN} characters, so it is treated "
            "as absent"
        )
    # Host checks only once the configuration is there, so the message names one thing at a time.
    return problems or live_mode_problems(argv, env)


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
            allowed_origins=_split(env.get("ALLOWED_ORIGINS", DEFAULT_ORIGINS)),
            allowed_origin_regex=env.get("ALLOWED_ORIGIN_REGEX") or None,
        )
