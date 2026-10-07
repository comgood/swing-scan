"""The seeded synthetic market (spec 0006, doc 02 A2): pure, no I/O, no clock.

One `numpy.random.default_rng(seed)` is drawn in a fixed order, so the same seed and config
always give the same `Market`. The model, per session t and ticker i:

    r[i, t] = beta_i * market[t] + sector[s_i, t] + idio_vol_i * t4 + momentum[i, t]

`market` follows a seeded schedule of regimes holding exactly one planted bear segment.
`momentum` is the documented planted edge: `coef * clip(L, -c, c) / lookback`, where L is the
ticker's own log return over the previous `lookback` sessions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import polars as pl
from numpy.typing import NDArray

from engine.contracts import BARS_SCHEMA, SECURITIES_SCHEMA, DataMeta, Market
from engine.data.sanity import check_market

from .config import (
    BEAR,
    BENCHMARK,
    BULL,
    CHOP,
    DEFAULT_SEED,
    GENERATOR_VERSION,
    NAME_SUFFIXES,
    RECOVERY,
    REGIMES,
    SECTORS,
    SyntheticConfig,
)

Floats = NDArray[np.float64]
Ints = NDArray[np.int64]

CONSONANTS = "BCDFGHJKLMNPRSTVWZ"
VOWELS = "AEIOU"


def sessions(start: date, n: int) -> list[date]:
    """`n` weekdays from `start` (inclusive), with no holidays."""
    days: list[date] = []
    day = start
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


@dataclass(frozen=True)
class Schedule:
    """The market regime of every session, and where the planted bear segment sits."""

    regime: Ints
    bear_start: int
    bear_end: int
    """Exclusive."""


def _schedule(rng: np.random.Generator, cfg: SyntheticConfig) -> Schedule:
    n = cfg.n_sessions
    length = int(
        rng.integers(round(cfg.bear_length_range[0] * n), round(cfg.bear_length_range[1] * n) + 1)
    )
    start = int(
        rng.integers(round(cfg.bear_start_range[0] * n), round(cfg.bear_start_range[1] * n) + 1)
    )
    start = max(1, min(start, n - length - 1))
    regime = np.zeros(n, dtype=np.int64)
    calm = [REGIMES.index(BULL), REGIMES.index(CHOP), REGIMES.index(RECOVERY)]
    weights = np.array([0.55, 0.25, 0.20])

    def fill(lo: int, hi: int, first: int | None) -> None:
        t, forced = lo, first
        while t < hi:
            run = int(rng.integers(cfg.regime_run_range[0], cfg.regime_run_range[1] + 1))
            pick = forced if forced is not None else calm[int(rng.choice(3, p=weights))]
            regime[t : min(hi, t + run)] = pick
            t, forced = t + run, None

    fill(0, start, None)
    regime[start : start + length] = REGIMES.index(BEAR)
    fill(start + length, n, REGIMES.index(RECOVERY))  # a recovery always follows the bear
    return Schedule(regime=regime, bear_start=start, bear_end=start + length)


def _market_returns(rng: np.random.Generator, cfg: SyntheticConfig, sched: Schedule) -> Floats:
    drift = np.array([r.drift for r in REGIMES])[sched.regime]
    vol = np.array([r.vol for r in REGIMES])[sched.regime]
    returns: Floats = drift + vol * rng.standard_normal(cfg.n_sessions)
    # Plant the bear exactly: keep its noise, demeaned, and set its total log return.
    a, b = sched.bear_start, sched.bear_end
    target = float(rng.uniform(*cfg.bear_log_return_range))
    noise = vol[a:b] * rng.standard_normal(b - a)
    returns[a:b] = target / (b - a) + (noise - noise.mean())
    returns[0] = 0.0
    return returns


def _tickers(rng: np.random.Generator, n: int) -> list[str]:
    space = len(CONSONANTS) * len(VOWELS) * len(CONSONANTS) * len(VOWELS)
    picks = rng.choice(space, size=n, replace=False)
    out: list[str] = []
    for k in picks.tolist():
        k, v2 = divmod(k, len(VOWELS))
        k, c2 = divmod(k, len(CONSONANTS))
        c1, v1 = divmod(k, len(VOWELS))
        out.append(CONSONANTS[c1] + VOWELS[v1] + CONSONANTS[c2] + VOWELS[v2])
    return out


def _ohlcv(
    rng: np.random.Generator,
    cfg: SyntheticConfig,
    close: Floats,
    returns: Floats,
    sigma: Floats,
    volume_base: Floats,
) -> tuple[Floats, Floats, Floats, Floats, Floats]:
    """Open, high, low, close and volume for a (rows, sessions) block of closes."""
    shape = close.shape
    sig = sigma[:, None]
    prev = np.concatenate([close[:, :1], close[:, :-1]], axis=1)
    gap = 0.3 * returns + 0.25 * sig * rng.standard_normal(shape)
    open_ = prev * np.exp(gap)
    top = np.maximum(open_, close) * np.exp(np.abs(0.5 * sig * rng.standard_normal(shape)))
    bottom = np.minimum(open_, close) * np.exp(-np.abs(0.5 * sig * rng.standard_normal(shape)))
    spike = 1.0 + 3.0 * np.abs(returns) / sig
    volume = volume_base[:, None] * np.exp(0.35 * rng.standard_normal(shape)) * spike

    d = cfg.price_decimals
    o, c = (np.maximum(np.round(x, d), cfg.price_floor) for x in (open_, close))
    h = np.maximum(np.maximum(np.round(top, d), cfg.price_floor), np.maximum(o, c))
    lo = np.minimum(np.maximum(np.round(bottom, d), cfg.price_floor), np.minimum(o, c))
    v = np.maximum(np.round(volume), 1.0)
    return o, h, lo, c, v


def generate(seed: int = DEFAULT_SEED, config: SyntheticConfig | None = None) -> Market:
    """The synthetic market for `seed`, checked by `engine.data.check_market` (D-1 to D-3).

    Pure and deterministic: the same seed and config always give equal frames and meta.
    """
    cfg = config or SyntheticConfig()
    rng = np.random.default_rng(seed)
    n, m = cfg.n_sessions, cfg.n_tickers
    days = sessions(cfg.start, n)

    sched = _schedule(rng, cfg)
    market = _market_returns(rng, cfg, sched)

    # Per ticker attributes, in draw order.
    tickers = _tickers(rng, m)
    sector = rng.permutation(np.arange(m) % len(SECTORS))
    beta = rng.uniform(*cfg.beta_range, size=m)
    idio_vol = rng.uniform(*cfg.idio_vol_range, size=m)
    lo_price, hi_price = cfg.start_price_range
    p0 = np.clip(cfg.start_price_median * np.exp(0.9 * rng.standard_normal(m)), lo_price, hi_price)
    volume_base = cfg.volume_median * np.exp(0.8 * rng.standard_normal(m))
    suffix = rng.integers(0, len(NAME_SUFFIXES), size=m)

    # Mid sample listings and planted delistings, disjoint.
    order = rng.permutation(m)
    listed_ix, delisted_ix = (
        order[: cfg.n_listed],
        order[cfg.n_listed : cfg.n_listed + cfg.n_delisted],
    )
    first = np.zeros(m, dtype=np.int64)
    first[listed_ix] = rng.integers(round(0.2 * n), round(0.8 * n) + 1, size=len(listed_ix))
    last = np.full(m, n - 1, dtype=np.int64)
    last[delisted_ix] = rng.integers(round(0.16 * n), n - 20, size=len(delisted_ix))
    bankrupt = np.zeros(m, dtype=bool)
    bankrupt[delisted_ix] = rng.random(len(delisted_ix)) < cfg.bankruptcy_share
    premium = np.zeros(m)
    premium[delisted_ix] = rng.uniform(*cfg.acquisition_premium_range, size=len(delisted_ix))

    # Every random shock, drawn up front in a fixed order.
    sector_returns = cfg.sector_vol * rng.standard_normal((len(SECTORS), n))
    t_scale = np.sqrt(cfg.t_degrees_of_freedom / (cfg.t_degrees_of_freedom - 2.0))
    idio = idio_vol[:, None] * rng.standard_t(cfg.t_degrees_of_freedom, size=(m, n)) / t_scale
    pinned_noise = 0.002 * rng.standard_normal((m, n))

    base = beta[:, None] * market[None, :] + sector_returns[sector] + idio
    t_index = np.arange(n)[None, :]
    is_delisted = np.zeros(m, dtype=bool)
    is_delisted[delisted_ix] = True
    slide = (
        is_delisted[:, None]
        & bankrupt[:, None]
        & (t_index > (last - cfg.bankruptcy_slide_sessions)[:, None])
    )
    base = base + np.where(slide, cfg.bankruptcy_slide_drift, 0.0)
    acquired = is_delisted & ~bankrupt
    announce = last - cfg.acquisition_lead_sessions
    jump = acquired[:, None] & (t_index == announce[:, None])
    pinned = acquired[:, None] & (t_index > announce[:, None])
    base = np.where(jump, np.log1p(premium)[:, None], base)
    base = np.where(pinned, pinned_noise, base)

    # Walk forward: the planted momentum term needs each ticker's own trailing return.
    lookback = cfg.momentum_lookback
    log_price = np.zeros((m, n))
    returns = np.zeros((m, n))
    for t in range(1, n):
        active = t > first
        momentum = np.zeros(m)
        if t - 1 - lookback >= 0:
            has_history = (t - 1 - lookback) >= first
            trailing = log_price[:, t - 1] - log_price[:, t - 1 - lookback]
            momentum = np.where(
                has_history & ~pinned[:, t],
                cfg.momentum_coef
                * np.clip(trailing, -cfg.momentum_clip, cfg.momentum_clip)
                / lookback,
                0.0,
            )
        step = np.where(active, base[:, t] + momentum, 0.0)
        returns[:, t] = step
        log_price[:, t] = log_price[:, t - 1] + step
    close = p0[:, None] * np.exp(log_price)

    sigma = np.sqrt((beta * 0.011) ** 2 + cfg.sector_vol**2 + idio_vol**2)
    o, h, lo, c, v = _ohlcv(rng, cfg, close, returns, sigma, volume_base)

    index_close = cfg.index_start_level * np.exp(np.cumsum(market))[None, :]
    index_sigma = np.array([0.011])
    io, ih, il, ic, iv = _ohlcv(
        rng, cfg, index_close, market[None, :], index_sigma, np.array([cfg.index_volume_median])
    )

    bars = _bars_frame(days, tickers, first, last, (o, h, lo, c, v), (io, ih, il, ic, iv))
    securities = _securities_frame(
        days, tickers, sector, suffix, first, last, is_delisted, bankrupt
    )
    meta = DataMeta(
        data_mode="synthetic",
        seed=seed,
        data_version=GENERATOR_VERSION,
        start=days[0],
        end=days[-1],
        n_tickers=m,
        survivors_only=False,
        benchmark=BENCHMARK,
    )
    result = Market(bars=bars, securities=securities, meta=meta)
    check_market(result)
    return result


def _bars_frame(
    days: list[date],
    tickers: list[str],
    first: Ints,
    last: Ints,
    stock: tuple[Floats, Floats, Floats, Floats, Floats],
    index: tuple[Floats, Floats, Floats, Floats, Floats],
) -> pl.DataFrame:
    n = len(days)
    t_index = np.arange(n)[None, :]
    visible = (t_index >= first[:, None]) & (t_index <= last[:, None])
    rows, cols = np.nonzero(visible)
    day_array = np.array(days, dtype="datetime64[D]")
    frames = [
        pl.DataFrame(
            {
                "ticker": np.array(tickers, dtype=object)[rows],
                "date": day_array[cols],
                **{
                    name: values[rows, cols]
                    for name, values in zip(
                        ("open", "high", "low", "close", "volume"), stock, strict=True
                    )
                },
            }
        ),
        pl.DataFrame(
            {
                "ticker": [BENCHMARK] * n,
                "date": day_array,
                **{
                    name: values[0]
                    for name, values in zip(
                        ("open", "high", "low", "close", "volume"), index, strict=True
                    )
                },
            }
        ),
    ]
    return pl.concat(frames).cast(BARS_SCHEMA).sort("ticker", "date")  # type: ignore[arg-type]


def _securities_frame(
    days: list[date],
    tickers: list[str],
    sector: Ints,
    suffix: Ints,
    first: Ints,
    last: Ints,
    is_delisted: NDArray[np.bool_],
    bankrupt: NDArray[np.bool_],
) -> pl.DataFrame:
    rows: list[dict[str, object]] = [
        {
            "ticker": BENCHMARK,
            "name": "Demo Index",
            "sector": "Index",
            "listed_from": days[0],
            "delisted_on": None,
            "delist_reason": None,
        }
    ]
    for i, ticker in enumerate(tickers):
        delisted = bool(is_delisted[i])
        rows.append(
            {
                "ticker": ticker,
                "name": f"{ticker.capitalize()} {NAME_SUFFIXES[int(suffix[i])]}",
                "sector": SECTORS[int(sector[i])],
                "listed_from": days[int(first[i])],
                "delisted_on": days[int(last[i])] if delisted else None,
                "delist_reason": ("bankruptcy" if bankrupt[i] else "acquired")
                if delisted
                else None,
            }
        )
    return pl.DataFrame(rows, schema=SECURITIES_SCHEMA).sort("ticker")
