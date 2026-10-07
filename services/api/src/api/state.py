"""The one `Market` the routes serve. It is loaded at import once scope feature 7 exists."""

from __future__ import annotations

from engine.contracts import Market

market: Market | None = None
"""Null until scope feature 7 adds the synthetic data loader."""
