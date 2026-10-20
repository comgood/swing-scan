"""`python -m engine.synthetic.tick`: publish one more session of the master (spec 0012).

The master is never stored. The tick regenerates it from the published `meta.seed` on every
run, which doubles as the integrity check on what is already published: a tick that cannot
match the published prefix to the master writes nothing at all. Nothing is computed at publish
time, only filtered, and `write_market` puts meta last, so a tick interrupted halfway leaves
readers on the previous dataset and the next tick finishes the job.

The simulated clock is not tied to the wall clock: one tick advances one session, so a missed
day is caught up by the next tick rather than skipped.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date

import polars as pl

from engine.data import market_uri, read_market, session_dates, truncate_market, write_market

from .generator import generate


def tick(root: str, target: date | None = None) -> int:
    """Publish the next session of the master into the dataset at `root`; returns an exit code.

    `target` names the session to publish, so a retry of the same tick is a no op rather than
    a second step forward. Left out, the target is the session after the published end.
    """
    published = read_market(root)
    end = published.meta.end
    if published.meta.seed is None:
        print(
            f"aborted: {root} carries no seed, so its master cannot be regenerated",
            file=sys.stderr,
        )
        return 1

    master = generate(published.meta.seed)
    sessions = session_dates(master)
    if end not in sessions:
        print(f"aborted: published end {end} is not a session of the master", file=sys.stderr)
        return 1
    if sessions[-1] == end:
        print(f"runway exhausted at {end}: the master has no session after it")
        return 0
    next_session = sessions[sessions.index(end) + 1]

    if target is not None:
        if target <= end:
            print(f"already current: {root} is published to {end}")
            return 0
        if target != next_session:
            print(
                f"aborted: {target} is not the next session ({next_session}); "
                "one tick advances one session",
                file=sys.stderr,
            )
            return 1

    # A prefix comparison, not an equality: a tick interrupted after bars but before meta
    # leaves bars one session ahead of meta, and the next tick must be able to finish it.
    at_cursor = truncate_market(master, end)
    if not published.bars.filter(pl.col("date") <= end).equals(at_cursor.bars):
        print(
            f"aborted: the bars published up to {end} do not match the master for seed "
            f"{published.meta.seed}; nothing written",
            file=sys.stderr,
        )
        return 1

    write_market(truncate_market(master, next_session), root)
    print(f"advanced {root} from {end} to {next_session}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m engine.synthetic.tick", description=__doc__)
    parser.add_argument(
        "--to",
        type=date.fromisoformat,
        default=None,
        help="the session to publish (default: the one after the published end); "
        "a session already published is a no op",
    )
    args = parser.parse_args(argv)
    return tick(market_uri(), args.to)


if __name__ == "__main__":
    raise SystemExit(main())
