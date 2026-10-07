"""The rule JSON: operands, conditions, rules and the two built in templates (doc 02 §5.2)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

from ._errors import ContractModel, Name, bounded, out_of_range
from .indicators import INDICATOR_SPECS, IndName

Op = Literal[">", "<", ">=", "<=", "crosses_above", "crosses_below"]


class IndOperand(ContractModel):
    """An indicator value, optionally shifted back `offset` bars and scaled by `mult`."""

    kind: Literal["ind"]
    ind: IndName
    # Declared after `ind` so the validator can read it; validated even when omitted so
    # `rs` gets its default and a missing required `n` is reported at `n`.
    n: int | None = Field(default=None, validate_default=True)
    offset: Annotated[int, bounded(0, 20)] = 0
    mult: Annotated[float, bounded(0.1, 10)] = 1.0

    @field_validator("n")
    @classmethod
    def _check_n(cls, n: int | None, info: ValidationInfo) -> int | None:
        ind = info.data.get("ind")
        if ind is None:
            return n  # `ind` itself failed; that error is already reported
        spec = INDICATOR_SPECS[ind]
        if not spec.windowed:
            if n is not None:
                raise PydanticCustomError(
                    "n_not_allowed", "{ind} takes no n (it is a price field)", {"ind": ind}
                )
            return None
        if n is None:
            if spec.n_default is not None:
                return spec.n_default
            raise PydanticCustomError(
                "n_required",
                "{ind} needs n between {min} and {max}",
                {"ind": ind, "min": spec.n_min, "max": spec.n_max},
            )
        if (
            spec.n_min is not None
            and spec.n_max is not None
            and not (spec.n_min <= n <= spec.n_max)
        ):
            raise out_of_range(spec.n_min, spec.n_max)
        return n


class ValueOperand(ContractModel):
    """A fixed number, such as the 5 in `close > 5`."""

    kind: Literal["value"]
    value: float


Operand = Annotated[IndOperand | ValueOperand, Field(discriminator="kind")]


class Condition(ContractModel):
    left: IndOperand
    op: Op
    right: Operand


class Rule(ContractModel):
    """An entry rule: 1 to 8 conditions joined by AND. No hidden price filter (ADR-013)."""

    name: Name
    conditions: Annotated[list[Condition], bounded(1, 8)]


class TemplateOut(ContractModel):
    id: str
    name: str
    description: str
    rule: Rule


def _ind(ind: IndName, n: int | None = None, offset: int = 0, mult: float = 1.0) -> IndOperand:
    return IndOperand(kind="ind", ind=ind, n=n, offset=offset, mult=mult)


def _value(value: float) -> ValueOperand:
    return ValueOperand(kind="value", value=value)


TEMPLATES: list[TemplateOut] = [
    TemplateOut(
        id="breakout_52w",
        name="52 week high breakout on volume",
        description=(
            "Close breaks above the highest high of the prior 252 bars, on volume at least "
            "1.5 times its 50 bar average, with a visible price filter."
        ),
        rule=Rule(
            name="52w breakout on volume",
            conditions=[
                Condition(left=_ind("close"), op=">", right=_ind("highest", 252, offset=1)),
                Condition(left=_ind("volume"), op=">", right=_ind("avg_volume", 50, mult=1.5)),
                Condition(left=_ind("close"), op=">", right=_value(5)),
            ],
        ),
    ),
    TemplateOut(
        id="pullback_ema21",
        name="Pullback to a rising 21 EMA",
        description=(
            "The 21 EMA is rising, price is above the 50 SMA, and the low dips to within 1% "
            "of the 21 EMA while the close holds above it, with a visible price filter."
        ),
        rule=Rule(
            name="Pullback to rising 21 EMA",
            conditions=[
                Condition(left=_ind("ema", 21), op=">", right=_ind("ema", 21, offset=5)),
                Condition(left=_ind("close"), op=">", right=_ind("sma", 50)),
                Condition(left=_ind("low"), op="<=", right=_ind("ema", 21, mult=1.01)),
                Condition(left=_ind("close"), op=">", right=_ind("ema", 21)),
                Condition(left=_ind("close"), op=">", right=_value(5)),
            ],
        ),
    ),
]
"""The two MUST templates from doc 02 §5.2, each with a visible `close > 5` (R-10)."""
