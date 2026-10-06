"""Runtime settings read from environment variables (spec 0001, Configuration required)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    data_mode: str
    allowed_origins: list[str]
    allowed_origin_regex: str | None

    @classmethod
    def from_env(cls) -> Settings:
        data_mode = os.environ.get("DATA_MODE", "synthetic")
        if data_mode != "synthetic":
            # Live mode (and its localhost only guard) arrives with scope feature 14.
            raise RuntimeError(f"DATA_MODE={data_mode!r} is not supported yet; use 'synthetic'.")
        return cls(
            data_mode=data_mode,
            allowed_origins=_split(os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")),
            allowed_origin_regex=os.environ.get("ALLOWED_ORIGIN_REGEX") or None,
        )
