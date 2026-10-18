"""Alembic environment: the direct (unpooled) URL, read from the environment.

Migrations run over `DATABASE_URL_UNPOOLED`, never the pooled one. Neon's pooled endpoint is
PgBouncer in transaction mode, and a migration needs session state it cannot keep across
checkouts; the failures do not mention pooling (`prepared statement already exists`, a
`SET search_path` that silently does not persist, an intermittent read only transaction).
"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine


def _url() -> str:
    url = os.environ.get("DATABASE_URL_UNPOOLED") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("set DATABASE_URL_UNPOOLED (preferred) or DATABASE_URL to migrate.")
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations_online() -> None:
    with create_engine(_url(), future=True).connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
