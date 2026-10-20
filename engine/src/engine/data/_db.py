"""The one place this package opens a Postgres connection (specs 0014, 0015).

Extracted when accounts arrived and a second repository needed the same two careful details:
a connection that lives exactly as long as one request, and `prepare_threshold=0`. Both are
easy to get wrong in a way that only shows up later, so they live here once rather than twice.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

DATABASE_URL_ENV = "DATABASE_URL"


def configured() -> bool:
    """Whether a database is configured at all. Absent means the routes answer 501."""
    return bool(os.environ.get(DATABASE_URL_ENV))


@contextmanager
def connect() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """A connection for one request, opened and closed inside it.

    Never a module level connection: on Lambda the execution environment is frozen between
    invocations, so a socket held across one does not reliably survive, and the failure shows
    up as a mystery error after an idle period rather than at the point of the mistake.

    `prepare_threshold=0` because `DATABASE_URL` is the pooled endpoint, which is PgBouncer in
    transaction mode: a prepared statement cannot outlive its checkout, and reusing one fails
    with `prepared statement "_pg3_0" already exists`.
    """
    url = os.environ.get(DATABASE_URL_ENV)
    if not url:
        raise RuntimeError(f"{DATABASE_URL_ENV} is not set; this feature is not available here.")
    with psycopg.connect(url, prepare_threshold=0) as conn:
        yield conn
