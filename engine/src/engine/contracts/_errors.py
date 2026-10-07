"""Shared base model, the `bounded()` range helper and the custom 422 error types (spec 0002).

Every ranged number, bounded list and bounded string goes through `bounded()` instead of
Pydantic's `ge`/`le`, because those report only the side that failed. `bounded()` reports
both ends in `ctx` (`min`, `max`) so the web app can show the allowed range (U-7).
"""

from __future__ import annotations

import re
from collections.abc import Sized
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    StringConstraints,
    ValidationError,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import InitErrorDetails, PydanticCustomError, core_schema


class ContractModel(BaseModel):
    """Base for every contract model: unknown keys are a 422 and floats must be finite."""

    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )


Number = int | float


@dataclass(frozen=True)
class bounded:
    """Inclusive range check for a number, or a length check for a list or string.

    Puts `minimum`/`maximum` (numbers), `minItems`/`maxItems` (lists) or
    `minLength`/`maxLength` (strings) into the JSON Schema. On failure raises the custom
    `out_of_range` error with `ctx` `{"min": .., "max": ..}`. Either side may be `None`
    for a one sided bound, in which case `ctx` carries only the other side.
    """

    min: Number | None
    max: Number | None

    def __get_pydantic_core_schema__(
        self, source: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(self._check, handler(source))

    def __get_pydantic_json_schema__(
        self, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(schema)
        kind = json_schema.get("type")
        keys = (
            {
                "integer": ("minimum", "maximum"),
                "number": ("minimum", "maximum"),
                "array": ("minItems", "maxItems"),
                "string": ("minLength", "maxLength"),
            }.get(kind)
            if isinstance(kind, str)
            else None
        )
        if keys is not None:
            if self.min is not None:
                json_schema[keys[0]] = self.min
            if self.max is not None:
                json_schema[keys[1]] = self.max
        return json_schema

    def _check(self, value: Any) -> Any:
        measured = len(value) if isinstance(value, Sized) else value
        too_low = self.min is not None and measured < self.min
        too_high = self.max is not None and measured > self.max
        if too_low or too_high:
            raise out_of_range(self.min, self.max)
        return value


def out_of_range(lo: Number | None, hi: Number | None) -> PydanticCustomError:
    """The `out_of_range` error, also used by the per indicator `n` check."""
    if lo is not None and hi is not None:
        return PydanticCustomError(
            "out_of_range", "must be between {min} and {max}", {"min": lo, "max": hi}
        )
    if lo is not None:
        return PydanticCustomError("out_of_range", "must be at least {min}", {"min": lo})
    return PydanticCustomError("out_of_range", "must be at most {max}", {"max": hi})


def error_at(loc: tuple[int | str, ...], error: PydanticCustomError, value: Any) -> ValidationError:
    """A validation error placed at `loc`, relative to the field being validated.

    Raised from a wrap validator on a list so a duplicate's error points at its own index.
    """
    return ValidationError.from_exception_data(
        "contract", [InitErrorDetails(type=error, loc=loc, input=value)]
    )


_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _iso_date_only(value: Any) -> Any:
    if isinstance(value, date) or (isinstance(value, str) and _ISO_DATE.match(value)):
        return value
    raise PydanticCustomError("date_format", "must be a date in YYYY-MM-DD format")


IsoDate = Annotated[date, BeforeValidator(_iso_date_only)]
"""A calendar date that only accepts `YYYY-MM-DD` on the wire (no timestamps)."""

Name = Annotated[str, StringConstraints(strip_whitespace=True), bounded(1, 40)]
"""A rule or exit config name: 1 to 40 characters after trimming."""
