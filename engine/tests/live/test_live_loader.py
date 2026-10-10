"""Live loader (D-4, spec 0010) against fake in memory Alpaca responses; no network, ever."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import polars as pl
import pytest

from engine.data import read_market
from engine.live import (
    DEFAULT_FEED,
    LiveLoadError,
    build_market,
    fetch_bars,
    keys_from_env,
    read_universe,
    resolve_feed,
    vendor_error,
)
from engine.live.__main__ import main
from engine.live.alpaca import feed_of

KEYS = {"ALPACA_API_KEY_ID": "fake-id", "ALPACA_API_SECRET_KEY": "fake-secret"}


def bar(day: str, close: float = 10.0, **over: float) -> dict[str, Any]:
    return {
        "t": f"{day}T05:00:00Z",
        "o": close,
        "h": close + 1,
        "l": close - 1,
        "c": close,
        "v": 1000.0,
        "n": 5,
        "vw": close,
    } | over


RAW = {
    "SPY": [bar("2016-01-04", 200.0), bar("2016-01-05", 201.0)],
    "AAA": [bar("2015-12-31"), bar("2016-01-04"), bar("2016-01-05", 11.0)],
    "BBB": [bar("2016-01-05"), bar("2016-01-06", v=0.0)],
}


class FakeAlpaca:
    """Answers each request page by page from `RAW` and records every URL it saw."""

    def __init__(self, raw: Mapping[str, list[dict[str, Any]]], page_size: int = 2) -> None:
        self.raw, self.page_size = raw, page_size
        self.urls: list[str] = []

    def __call__(self, url: str, headers: Mapping[str, str]) -> dict[str, Any]:
        assert headers["APCA-API-KEY-ID"] == "fake-id"
        self.urls.append(url)
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        flat = [(s, b) for s in q["symbols"].split(",") for b in self.raw.get(s, [])]
        at = int(q.get("page_token", "0"))
        page: dict[str, list[dict[str, Any]]] = {}
        for s, b in flat[at : at + self.page_size]:
            page.setdefault(s, []).append(b)
        more = at + self.page_size < len(flat)
        return {"bars": page, "next_page_token": str(at + self.page_size) if more else None}


class DeniedAlpaca:
    """A plan that may not read this feed: the transport raises what the real one would."""

    MESSAGE = '{"message": "subscription does not permit querying recent SIP data"}'

    def __call__(self, url: str, headers: Mapping[str, str]) -> dict[str, Any]:
        raise vendor_error(403, self.MESSAGE, feed_of(url))


UNIVERSE = "ticker,name,sector\naaa,Alpha,Tech\nBBB,Beta,Energy\nCCC,Gone,Utilities\nSPY,dup,x\n"


def universe_csv(tmp_path: Path, body: str = UNIVERSE) -> Path:
    path = tmp_path / "sp500.csv"
    path.write_text(body, "utf-8")
    return path


def test_fetch_pages_and_defaults_to_the_free_iex_feed() -> None:
    fake = FakeAlpaca(RAW)
    raw = fetch_bars(
        ["AAA", "BBB", "SPY"],
        date(2016, 1, 4),
        date(2016, 1, 6),
        {"APCA-API-KEY-ID": "fake-id"},
        fake,
    )
    assert {s: len(b) for s, b in raw.items()} == {"AAA": 3, "BBB": 2, "SPY": 2}
    assert len(fake.urls) == 4  # 7 bars, 2 per page
    q = parse_qs(urlparse(fake.urls[0]).query)
    assert q["feed"] == ["iex"] and q["adjustment"] == ["all"] and q["timeframe"] == ["1Day"]
    assert q["start"] == ["2016-01-04"]


def test_fetch_sends_the_feed_it_is_given() -> None:
    fake = FakeAlpaca(RAW, page_size=99)
    headers = {"APCA-API-KEY-ID": "fake-id"}
    fetch_bars(["SPY"], date(2016, 1, 4), date(2016, 1, 6), headers, fake, "sip")
    assert parse_qs(urlparse(fake.urls[0]).query)["feed"] == ["sip"]


def test_resolve_feed_prefers_the_flag_then_the_env_then_iex() -> None:
    assert DEFAULT_FEED == "iex"
    assert resolve_feed(None, {}) == "iex"
    assert resolve_feed(None, {"ALPACA_FEED": "SIP"}) == "sip"
    assert resolve_feed("iex", {"ALPACA_FEED": "sip"}) == "iex"
    with pytest.raises(LiveLoadError, match="not one of iex, sip"):
        resolve_feed("nasdaq", {})
    with pytest.raises(LiveLoadError, match="not one of iex, sip"):
        resolve_feed(None, {"ALPACA_FEED": "delayed_sip"})


def test_a_403_names_the_feed_and_points_back_at_iex() -> None:
    message = str(vendor_error(403, DeniedAlpaca.MESSAGE, "sip"))
    assert "'sip'" in message and "403" in message
    assert "free Basic plan has no SIP history" in message and "'iex'" in message
    assert "subscription does not permit" in message
    # A subscription complaint under another status code reads the same way.
    assert "free Basic plan" in str(vendor_error(422, DeniedAlpaca.MESSAGE, "sip"))
    # Anything else stays a plain HTTP error, without the misleading advice.
    assert str(vendor_error(500, "boom", "iex")) == "Alpaca answered HTTP 500: boom"


def test_build_market_matches_the_schema_and_reports_missing(tmp_path: Path) -> None:
    universe = read_universe(universe_csv(tmp_path))
    assert universe["ticker"].to_list() == ["AAA", "BBB", "CCC"]
    market, summary = build_market(universe, RAW, date(2016, 1, 4), date(2016, 1, 6))
    assert market.bars["date"].min() == date(2016, 1, 4)  # the 2015 bar is cut (D-4)
    assert market.bars.filter(pl.col("ticker") == "BBB").height == 1  # zero volume bar dropped
    assert market.meta.data_mode == "live" and market.meta.survivors_only
    assert market.meta.data_version == "alpaca-iex-all:2016-01-05"
    assert market.meta.benchmark == "SPY" and market.meta.n_tickers == 2
    assert market.securities.filter(pl.col("ticker") == "BBB")["listed_from"].item() == date(
        2016, 1, 5
    )
    assert summary.missing == ["CCC"] and summary.dropped_bars == 1 and summary.tickers == 2
    assert summary.feed == "iex" and summary.data_version == market.meta.data_version


def test_the_feed_names_the_data_version_and_the_caveat_is_iex_only(tmp_path: Path) -> None:
    universe = read_universe(universe_csv(tmp_path))
    market, summary = build_market(universe, RAW, date(2016, 1, 4), date(2016, 1, 6), "sip")
    assert market.meta.data_version == "alpaca-sip-all:2016-01-05"
    assert summary.feed == "sip"
    assert not [line for line in summary.lines() if "caveat" in line]


def test_build_market_needs_spy(tmp_path: Path) -> None:
    universe = read_universe(universe_csv(tmp_path))
    with pytest.raises(LiveLoadError, match="SPY"):
        build_market(universe, {"AAA": RAW["AAA"]}, date(2016, 1, 4), date(2016, 1, 6))


def test_keys_come_only_from_the_environment() -> None:
    with pytest.raises(LiveLoadError, match="ALPACA_API_SECRET_KEY"):
        keys_from_env({"ALPACA_API_KEY_ID": "x"})
    assert keys_from_env(KEYS)["APCA-API-SECRET-KEY"] == "fake-secret"


def test_bad_universe_header(tmp_path: Path) -> None:
    with pytest.raises(LiveLoadError, match="header"):
        read_universe(universe_csv(tmp_path, "symbol\nAAA\n"))


def test_cli_writes_a_readable_dataset(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "live"
    argv = ["--universe", str(universe_csv(tmp_path)), "--out", str(out), "--end", "2016-01-06"]
    assert main(argv, get=FakeAlpaca(RAW), env=KEYS) == 0
    market = read_market(out)
    assert market.meta.data_mode == "live"
    assert market.meta.data_version == "alpaca-iex-all:2016-01-05"
    assert json.loads((out / "meta.json").read_text())["seed"] is None
    printed = capsys.readouterr().out
    assert "loaded 2 tickers plus SPY" in printed and "missing symbols (1): CCC" in printed
    assert "feed iex, data_version alpaca-iex-all:2016-01-05" in printed
    assert "vol_ratio" in printed and "not comparable to a full tape" in printed


def test_cli_without_keys_fails_before_any_request(tmp_path: Path) -> None:
    fake = FakeAlpaca(RAW)
    argv = ["--universe", str(universe_csv(tmp_path)), "--out", str(tmp_path / "live")]
    assert main(argv, get=fake, env={}) == 1
    assert fake.urls == []


def test_cli_rejects_an_unknown_feed_before_any_request(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeAlpaca(RAW)
    argv = ["--universe", str(universe_csv(tmp_path)), "--out", str(tmp_path / "live")]
    assert main([*argv, "--feed", "nasdaq"], get=fake, env=KEYS) == 1
    assert fake.urls == []
    assert "not one of iex, sip" in capsys.readouterr().err


def test_cli_reports_a_subscription_refusal_clearly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A 403 on the sip feed reaches the user naming the feed, never as a traceback."""
    argv = ["--universe", str(universe_csv(tmp_path)), "--out", str(tmp_path / "live")]
    assert main([*argv, "--feed", "sip"], get=DeniedAlpaca(), env=KEYS) == 1
    err = capsys.readouterr().err
    assert "load-live failed" in err and "'sip'" in err
    assert "free Basic plan has no SIP history" in err and "'iex'" in err


def test_the_env_var_picks_the_feed(tmp_path: Path) -> None:
    """`ALPACA_FEED=sip` is honoured, so the same 403 arrives without a flag."""
    argv = ["--universe", str(universe_csv(tmp_path)), "--out", str(tmp_path / "live")]
    assert main(argv, get=DeniedAlpaca(), env=KEYS | {"ALPACA_FEED": "sip"}) == 1
