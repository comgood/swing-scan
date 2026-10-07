"""The indicator registry: one table drives both rule validation and `GET /indicators` (AC-7)."""

from __future__ import annotations

from typing import Literal

from ._errors import ContractModel

IndName = Literal[
    "open",
    "high",
    "low",
    "close",
    "volume",
    "sma",
    "ema",
    "rsi",
    "atr",
    "highest",
    "lowest",
    "avg_volume",
    "ret",
    "rs",
]


class IndicatorSpec(ContractModel):
    """One registry row. Non windowed indicators (price fields) take no `n`."""

    name: IndName
    label: str
    windowed: bool
    n_min: int | None
    n_max: int | None
    n_default: int | None


def _price(name: IndName, label: str) -> IndicatorSpec:
    return IndicatorSpec(
        name=name, label=label, windowed=False, n_min=None, n_max=None, n_default=None
    )


def _windowed(
    name: IndName, label: str, n_max: int = 252, n_default: int | None = None
) -> IndicatorSpec:
    return IndicatorSpec(
        name=name, label=label, windowed=True, n_min=2, n_max=n_max, n_default=n_default
    )


INDICATOR_SPECS: dict[IndName, IndicatorSpec] = {
    spec.name: spec
    for spec in (
        _price("open", "Open"),
        _price("high", "High"),
        _price("low", "Low"),
        _price("close", "Close"),
        _price("volume", "Volume"),
        _windowed("sma", "Simple moving average"),
        _windowed("ema", "Exponential moving average"),
        _windowed("rsi", "Relative strength index", n_max=50),
        _windowed("atr", "Average true range"),
        _windowed("highest", "Highest high"),
        _windowed("lowest", "Lowest low"),
        _windowed("avg_volume", "Average volume"),
        _windowed("ret", "Return over n bars (%)"),
        _windowed("rs", "Relative strength vs the benchmark", n_default=126),
    )
}
"""Every indicator, in display order. `rs` alone has a default `n` (126)."""
