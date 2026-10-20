"""The D-5 guard: live mode starts only on your machine, bound to 127.0.0.1 (spec 0001)."""

from __future__ import annotations

import pytest

from api.settings import Settings, bound_host, saved_rules_problems

UVICORN = ["uvicorn", "api.main:app"]


def test_synthetic_is_the_default_anywhere() -> None:
    env = {"AWS_LAMBDA_FUNCTION_NAME": "swing-scan-api", "CI": "true"}
    assert Settings.from_env(env, [*UVICORN, "--host", "0.0.0.0"]).data_mode == "synthetic"  # noqa: S104


def test_live_starts_on_localhost() -> None:
    settings = Settings.from_env({"DATA_MODE": "live"}, [*UVICORN, "--host", "127.0.0.1"])
    assert settings.data_mode == "live"


@pytest.mark.parametrize(
    ("env", "argv", "reason"),
    [
        ({"AWS_LAMBDA_FUNCTION_NAME": "swing-scan-api"}, UVICORN, "AWS Lambda"),
        ({"CI": "true"}, UVICORN, "in CI"),
        ({}, [*UVICORN, "--host", "0.0.0.0"], "bound to '0.0.0.0'"),  # noqa: S104
        ({}, [*UVICORN, "--host=192.168.1.5"], "bound to '192.168.1.5'"),
        ({"UVICORN_HOST": "localhost"}, UVICORN, "bound to 'localhost'"),
    ],
)
def test_live_refuses_to_start_off_your_machine(
    env: dict[str, str], argv: list[str], reason: str
) -> None:
    with pytest.raises(RuntimeError, match="DATA_MODE=live") as exc:
        Settings.from_env({"DATA_MODE": "live", **env}, argv)
    assert reason in str(exc.value)


def test_unknown_mode_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="not one of"):
        Settings.from_env({"DATA_MODE": "demo"}, UVICORN)


def test_bound_host_follows_uvicorn_precedence() -> None:
    assert bound_host(UVICORN, {}) == "127.0.0.1"
    assert bound_host(UVICORN, {"UVICORN_HOST": "10.0.0.1"}) == "10.0.0.1"
    assert bound_host([*UVICORN, "--host", "::1"], {"UVICORN_HOST": "10.0.0.1"}) == "::1"


# ---- Saved rules and accounts: three gates, not one (spec 0014 AC-6/AC-7, spec 0015 AC-4/AC-5) --

SECRET = {"AUTH_SECRET": "x" * 32}
DB = {"DATABASE_URL": "postgresql://user:pw@host/db", **SECRET}


def test_saved_rules_run_on_your_machine_with_a_database() -> None:
    assert saved_rules_problems(UVICORN, DB) == []


def test_saved_rules_need_a_database() -> None:
    assert saved_rules_problems(UVICORN, SECRET) == ["no DATABASE_URL is configured"]


def test_accounts_need_a_signing_key() -> None:
    """spec 0015 AC-4: a rule belongs to an account now, so no key means no rules surface
    either. The two share one gate rather than drifting apart."""
    db_only = {"DATABASE_URL": DB["DATABASE_URL"]}
    assert saved_rules_problems(UVICORN, db_only) == ["no AUTH_SECRET is configured"]


def test_a_short_signing_key_counts_as_absent() -> None:
    """A weak key is worse than no feature, so it refuses rather than signing with it."""
    problems = saved_rules_problems(UVICORN, {**DB, "AUTH_SECRET": "x" * 31})
    assert len(problems) == 1
    assert "shorter than 32 characters" in problems[0]


def test_every_missing_piece_is_named_at_once() -> None:
    """The 501 body should name what you actually have to fix, not just the first thing."""
    assert saved_rules_problems(UVICORN, {}) == [
        "no DATABASE_URL is configured",
        "no AUTH_SECRET is configured",
    ]


@pytest.mark.parametrize(
    ("env", "argv", "reason"),
    [
        ({"AWS_LAMBDA_FUNCTION_NAME": "swing-scan-api"}, UVICORN, "AWS Lambda"),
        ({"CI": "true"}, UVICORN, "in CI"),
        ({}, [*UVICORN, "--host", "0.0.0.0"], "bound to '0.0.0.0'"),  # noqa: S104
    ],
)
def test_a_database_url_off_your_machine_does_not_open_saved_rules(
    env: dict[str, str], argv: list[str], reason: str
) -> None:
    """AC-7: configuring a database on the deployed function cannot open an unauthenticated
    write endpoint, because the D-5 host rules gate this too."""
    problems = saved_rules_problems(argv, {**DB, **env})
    assert any(reason in problem for problem in problems)
