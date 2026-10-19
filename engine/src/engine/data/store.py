"""Read and write one dataset: `bars.parquet`, `securities.parquet`, `meta.parquet`
(doc 02 §5.1, spec 0002), in a local directory or an object store prefix (spec 0011).

The dataset this process serves lives at `$MARKET_STORE_URI/$DATA_MODE/`. A local path and
an `s3://` prefix are read by the same code: Polars reads Parquet from either, so nothing
here knows about S3 and no object store client enters the engine.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import polars as pl

from engine.contracts import BARS_SCHEMA, SECURITIES_SCHEMA, DataMeta, Market

from .sanity import check_market

BARS_FILE = "bars.parquet"
SECURITIES_FILE = "securities.parquet"
META_FILE = "meta.parquet"
# Meta is written last: it carries the change key, so a reader that sees new meta is
# guaranteed to have the new bars behind it (spec 0011).
DATASET_FILES = (BARS_FILE, SECURITIES_FILE, META_FILE)

STORE_URI_ENV = "MARKET_STORE_URI"
DEFAULT_STORE_URI = "data"
DATA_MODE_ENV = "DATA_MODE"
DEFAULT_DATA_MODE = "synthetic"

LAYOUT_VERSION_COLUMN = "layout_version"
META_JSON_COLUMN = "meta_json"
META_SCHEMA: dict[str, pl.DataType] = {
    LAYOUT_VERSION_COLUMN: pl.Int32(),
    META_JSON_COLUMN: pl.String(),
}
SUPPORTED_LAYOUT_VERSION = 1

# Absent or transient failures mean "no dataset here" (the routes answer 501); everything
# else, access denied included, must fail loudly. Polars surfaces cloud failures as one
# `ComputeError` carrying the object store's message, so the only thing to match on is text.
# shortcut: substring matching on that message, until Polars exposes typed cloud errors.
_ABSENT_MARKERS = ("not found", "404", "nosuchkey", "nosuchbucket")
_TRANSIENT_MARKERS = ("error sending request", "timed out", "timeout", "dns error")


def market_uri() -> str:
    """The dataset this process serves: `$MARKET_STORE_URI/$DATA_MODE`, else `data/synthetic`.

    Joined as a string, never through `pathlib`: `Path("s3://b/x")` collapses to `s3:/b/x`,
    which is not a valid URI. `DATA_MODE` is read here rather than through the API's
    `Settings`, because `api.state` loads the market at import, before `Settings` exists.
    """
    root = os.environ.get(STORE_URI_ENV) or DEFAULT_STORE_URI
    mode = os.environ.get(DATA_MODE_ENV) or DEFAULT_DATA_MODE
    return f"{root.rstrip('/')}/{mode}"


def dataset_key(root: str | Path, name: str) -> str:
    """One object's full path under a dataset root, for a directory or an `s3://` prefix."""
    return f"{str(root).rstrip('/')}/{name}"


def change_key(meta: DataMeta) -> str:
    """The dataset's identity, as stored in `meta.parquet` and compared by the change check."""
    return meta.model_dump_json()


def session_dates(market: Market) -> list[date]:
    """Every session in the market, in order. The clock's cursor is a position in this list."""
    return list(market.bars["date"].unique().sort().to_list())


def truncate_market(market: Market, cursor: date) -> Market:
    """The published prefix of `market` at `cursor`: nothing in it is dated after that day.

    Only filtering and nulling, never computing, so the prefix inherits the master's
    correctness (spec 0012). `check_market` runs here, so a cursor that would publish a broken
    dataset raises before anything is written.
    """
    bars = market.bars.filter(pl.col("date") <= cursor)
    future_delist = pl.col("delisted_on") > cursor
    securities = market.securities.with_columns(
        pl.when(pl.col("listed_from") > cursor)
        .then(None)
        .otherwise(pl.col("listed_from"))
        .alias("listed_from"),
        # The delist pair is nulled together: check_market refuses one without the other.
        pl.when(future_delist).then(None).otherwise(pl.col("delisted_on")).alias("delisted_on"),
        pl.when(future_delist).then(None).otherwise(pl.col("delist_reason")).alias("delist_reason"),
    )
    prefix = Market(
        bars=bars, securities=securities, meta=market.meta.model_copy(update={"end": cursor})
    )
    check_market(prefix)
    return prefix


def write_market(market: Market, out_dir: str | Path) -> str:
    """Check the market, then write its three objects under `out_dir`, meta last.

    Output is byte for byte reproducible for the same market and library versions.
    """
    check_market(market)
    out = str(out_dir)
    frames = (
        market.bars,
        market.securities,
        pl.DataFrame(
            {
                LAYOUT_VERSION_COLUMN: [SUPPORTED_LAYOUT_VERSION],
                META_JSON_COLUMN: [change_key(market.meta)],
            },
            schema=META_SCHEMA,
        ),
    )
    for name, frame in zip(DATASET_FILES, frames, strict=True):
        frame.write_parquet(
            dataset_key(out, name), compression="zstd", statistics=False, mkdir=True
        )
    return out


def _read_parquet(key: str) -> pl.DataFrame:
    """Read one object, turning "absent" and transient failures into `FileNotFoundError`."""
    try:
        return pl.read_parquet(key)
    except FileNotFoundError:
        raise
    except Exception as exc:
        message = str(exc).lower()
        if any(m in message for m in (*_ABSENT_MARKERS, *_TRANSIENT_MARKERS)):
            raise FileNotFoundError(f"no object at {key}: {exc}") from exc
        raise


def read_meta(data_dir: str | Path | None = None) -> tuple[int, str]:
    """`meta.parquet`'s layout version and its `meta_json`, the change check's key.

    Raises `FileNotFoundError` when the dataset is absent or the store is unreachable.
    """
    root = str(data_dir) if data_dir is not None else market_uri()
    frame = _read_parquet(dataset_key(root, META_FILE))
    row = frame.row(0, named=True)
    return int(row[LAYOUT_VERSION_COLUMN]), str(row[META_JSON_COLUMN])


def read_market(data_dir: str | Path | None = None) -> Market:
    """Load and check the dataset under `data_dir` (default: `market_uri()`).

    `FileNotFoundError` means no dataset is there yet, which callers may tolerate. Every
    other failure, an unsupported layout version and a market that fails `check_market`
    included, raises: a broken dataset must never serve.
    """
    root = str(data_dir) if data_dir is not None else market_uri()
    try:
        layout_version, meta_json = read_meta(root)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"no dataset in {root}: {exc}. Run `make data` to generate one, "
            f"or `make push-market` to seed the store."
        ) from exc
    if layout_version != SUPPORTED_LAYOUT_VERSION:
        raise ValueError(
            f"dataset in {root} has layout_version {layout_version}; "
            f"this build supports layout_version {SUPPORTED_LAYOUT_VERSION}"
        )
    bars = _read_parquet(dataset_key(root, BARS_FILE)).cast(BARS_SCHEMA)  # type: ignore[arg-type]
    securities = _read_parquet(dataset_key(root, SECURITIES_FILE)).cast(SECURITIES_SCHEMA)  # type: ignore[arg-type]
    market = Market(bars=bars, securities=securities, meta=DataMeta.model_validate_json(meta_json))
    check_market(market)
    return market
