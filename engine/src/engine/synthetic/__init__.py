"""The seeded synthetic market (DI lane, scope feature 7, spec 0006).

Public entry point: `generate(seed: int = 42, config: SyntheticConfig | None = None) -> Market`.
The CLI `python -m engine.synthetic --seed 42 --out DIR` writes it as Parquet plus `meta.json`.
"""

from .config import BENCHMARK, DEFAULT_SEED, GENERATOR_VERSION, SyntheticConfig
from .generator import generate, sessions

__all__ = [
    "BENCHMARK",
    "DEFAULT_SEED",
    "GENERATOR_VERSION",
    "SyntheticConfig",
    "generate",
    "sessions",
]
