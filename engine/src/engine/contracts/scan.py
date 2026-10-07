"""`POST /scan` request and response, plus the frozen column label grammar (spec 0002)."""

from __future__ import annotations

from typing import Annotated

from ._errors import ContractModel, IsoDate, bounded
from .rule import IndOperand, Rule


class ScanRequest(ContractModel):
    rule: Rule
    as_of: IsoDate | None = None
    """The session to scan. Null means the last session in the data."""


class ScanRow(ContractModel):
    ticker: str
    close: float
    chg_pct: float | None
    vol_ratio: float | None
    operands: list[float]
    """Operand values aligned to `ScanResponse.columns`. Never null: a hit row is valid."""
    new_today: bool


class ScanResponse(ContractModel):
    as_of: IsoDate
    columns: list[str]
    rows: Annotated[list[ScanRow], bounded(0, 500)]


def column_label(operand: IndOperand) -> str:
    """The scan column label for one operand: `[{mult}×]{ind}[({n})][[{offset}]]`.

    Golden cases: `close`, `highest(252)[1]`, `1.5×avg_volume(50)`, `ema(21)[5]`,
    `1.01×ema(21)`, `rs(126)`.
    """
    label: str = operand.ind
    if operand.n is not None:
        label += f"({operand.n})"
    if operand.offset > 0:
        label += f"[{operand.offset}]"
    if operand.mult != 1:
        label = f"{operand.mult!r}×{label}"
    return label


def scan_columns(rule: Rule) -> list[str]:
    """One label per distinct indicator operand, in order of first appearance."""
    seen: dict[tuple[str, int | None, int, float], str] = {}
    for condition in rule.conditions:
        for operand in (condition.left, condition.right):
            if isinstance(operand, IndOperand):
                key = (operand.ind, operand.n, operand.offset, operand.mult)
                seen.setdefault(key, column_label(operand))
    return list(seen.values())
