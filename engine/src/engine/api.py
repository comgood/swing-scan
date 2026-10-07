"""Public use cases, the application layer. Acceptance tests call only these (spec 0002).

Both are stubs until their scope features land; they raise `NotYetImplemented`, which the
API maps to 501. A stray `NotImplementedError` from a real bug stays a 500.
"""

from __future__ import annotations

from .contracts import BacktestRequest, BacktestResponse, Market, ScanRequest, ScanResponse

FEATURE_NAMES = {8: "Template scan", 9: "Portfolio backtest core"}


class NotYetImplemented(Exception):
    """A use case whose scope feature has not landed yet."""

    def __init__(self, feature: int, what: str) -> None:
        self.feature = feature
        name = FEATURE_NAMES.get(feature, "a later feature")
        super().__init__(
            f"{what} is not implemented yet; it arrives with scope feature {feature} ({name})."
        )


def scan(request: ScanRequest, market: Market) -> ScanResponse:
    """Run a rule over one session and return the matching tickers (scope feature 8)."""
    raise NotYetImplemented(8, "scan")


def backtest(request: BacktestRequest, market: Market) -> BacktestResponse:
    """Backtest a rule with 1 config (portfolio) or 2 to 6 configs (exit lab) (feature 9)."""
    raise NotYetImplemented(9, "backtest")
