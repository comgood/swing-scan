"""Alpaca daily bars over HTTPS, keys from the environment only (doc 02 A3, spec 0010).

The feed defaults to `iex`, the only historical feed the free Basic plan serves; `sip` answers
HTTP 403 there. Never called in CI or tests: tests inject a fake `Transport`, so no request
and no cassette.
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
FEED_ENV = "ALPACA_FEED"
FEEDS = ("iex", "sip")
DEFAULT_FEED = "iex"
"""The free Basic plan's feed. `sip` (the full consolidated tape) needs a paid plan."""
SYMBOLS_PER_REQUEST = 100
PAGE_LIMIT = 10_000
SUBSCRIPTION_HINTS = ("subscription", "not permitted", "not entitled")
"""What Alpaca says when the plan may not read this feed, whatever status code carries it."""
VOLUME_CAVEAT = (
    "caveat: iex is one exchange and a small share of consolidated volume, so vol_ratio, "
    "avg_volume and any comparison of volume across tickers are not comparable to a full tape"
)

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


def resolve_feed(flag: str | None, env: Mapping[str, str]) -> str:
    """The data feed: `--feed`, else `ALPACA_FEED`, else `iex` (what the free plan allows)."""
    feed = (flag or env.get(FEED_ENV) or DEFAULT_FEED).strip().lower()
    if feed not in FEEDS:
        raise LiveLoadError(
            f"feed {feed!r} is not one of {', '.join(FEEDS)}; "
            f"the free Basic plan allows only {DEFAULT_FEED!r} (the default)"
        )
    return feed


def feed_of(url: str) -> str:
    """The feed a request URL asks for, for error messages."""
    asked = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("feed")
    return asked[0] if asked else DEFAULT_FEED


def vendor_error(code: int, body: str, feed: str) -> LiveLoadError:
    """A failed Alpaca response as an error that says what to do about it."""
    detail = " ".join(body.split())[:200]
    if code == 403 or any(hint in body.lower() for hint in SUBSCRIPTION_HINTS):
        return LiveLoadError(
            f"Alpaca refused the {feed!r} feed with HTTP {code}"
            f"{f': {detail}' if detail else ''}. The free Basic plan has no SIP history, "
            f"so feed=sip answers 403; retry with the default feed {DEFAULT_FEED!r} "
            f"(drop --feed and unset {FEED_ENV}). Already on {DEFAULT_FEED!r}? Then check "
            f"{KEY_ENV} and {SECRET_ENV} and your plan."
        )
    return LiveLoadError(f"Alpaca answered HTTP {code}{f': {detail}' if detail else ''}")


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
                raise vendor_error(exc.code, _read(exc), feed_of(url)) from exc
            time.sleep(2**attempt)
    raise LiveLoadError("Alpaca kept rate limiting")  # pragma: no cover


def _read(exc: urllib.error.HTTPError) -> str:
    """The error body, if the vendor sent one and it can still be read."""
    try:
        return exc.read().decode("utf-8", "replace")
    except OSError:  # pragma: no cover (the body is already consumed or gone)
        return ""


def fetch_bars(
    symbols: Iterable[str],
    start: date,
    end: date,
    headers: Mapping[str, str],
    get: Transport,
    feed: str = DEFAULT_FEED,
) -> RawBars:
    """Every daily bar for `symbols` (`adjustment=all`) from `feed`, batched and paged."""
    wanted = list(symbols)
    out: RawBars = {}
    for i in range(0, len(wanted), SYMBOLS_PER_REQUEST):
        params = {
            "symbols": ",".join(wanted[i : i + SYMBOLS_PER_REQUEST]),
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "adjustment": "all",
            "feed": feed,
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
