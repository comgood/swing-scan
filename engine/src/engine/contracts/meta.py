"""`GET /meta`: the contract version and the loaded dataset (null until scope feature 7)."""

from __future__ import annotations

from ._errors import ContractModel, IsoDate
from .market import DataMeta


class MetaResponse(ContractModel):
    contract_version: str
    data: DataMeta | None
    oos_start: IsoDate | None


class NotImplementedBody(ContractModel):
    """The 501 body while a use case's scope feature has not landed."""

    detail: str
