"""Alpaca free daily bars over HTTPS, keys from the environment only (doc 02 A3, spec 0010).

Never called in CI or tests: tests inject a fake `Transport`, so no request and no cassette.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from datetime import date
from typing import Any

BARS_URL = "https://data.alpaca.markets/v2/stocks/bars"
KEY_ENV = "ALPACA_API_KEY_ID"
SECRET_ENV = "ALPACA_API_SECRET_KEY"  # noqa: S105 (the variable name, not a secret)
SYMBOLS_PER_REQUEST = 100
PAGE_LIMIT = 10_000

RawBars = dict[str, list[dict[str, Any]]]
"""Alpaca's `bars` object: symbol to a list of `{t, o, h, l, c, v, ...}`."""

Transport = Callable[[str, Mapping[str, str]], dict[str, Any]]
"""GET `url` with `headers` and return the decoded JSON body."""


class LiveLoadError(RuntimeError):
    """The live load cannot run, or produced nothing usable."""


def keys_from_env(env: Mapping[str, str]) -> dict[str, str]:
    """Alpaca auth headers from the environment; a missing key is a clear error."""
    missing = [name for name in (KEY_ENV, SECRET_ENV) if not env.get(name)]
    if missing:
        raise LiveLoadError(
            f"set {' and '.join(missing)} in your shell or .env (never commit them)"
        )
    return {"APCA-API-KEY-ID": env[KEY_ENV], "APCA-API-SECRET-KEY": env[SECRET_ENV]}


def urllib_transport(url: str, headers: Mapping[str, str]) -> dict[str, Any]:
    """The real transport: a stdlib HTTPS GET that backs off on 429 (the free rate limit)."""
    if not url.startswith(BARS_URL):
        raise LiveLoadError(f"refusing to call an unexpected URL: {url}")
    for attempt in range(5):
        request = urllib.request.Request(url, headers=dict(headers))  # noqa: S310
        try:
            with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
                body: dict[str, Any] = json.load(response)
                return body
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 4:
                raise LiveLoadError(f"Alpaca answered HTTP {exc.code}") from exc
            time.sleep(2**attempt)
    raise LiveLoadError("Alpaca kept rate limiting")  # pragma: no cover


def fetch_bars(
    symbols: Iterable[str],
    start: date,
    end: date,
    headers: Mapping[str, str],
    get: Transport,
) -> RawBars:
    """Every daily bar for `symbols` (`feed=sip`, `adjustment=all`), batched and paged."""
    wanted = list(symbols)
    out: RawBars = {}
    for i in range(0, len(wanted), SYMBOLS_PER_REQUEST):
        params = {
            "symbols": ",".join(wanted[i : i + SYMBOLS_PER_REQUEST]),
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "adjustment": "all",
            "feed": "sip",
            "sort": "asc",
            "limit": str(PAGE_LIMIT),
        }
        token: str | None = None
        while True:
            query = params | ({"page_token": token} if token else {})
            page = get(f"{BARS_URL}?{urllib.parse.urlencode(query)}", headers)
            for symbol, bars in (page.get("bars") or {}).items():
                out.setdefault(symbol, []).extend(bars)
            token = page.get("next_page_token")
            if not token:
                break
    return out
