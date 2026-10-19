"""saved rules: one table, the rule as jsonb (spec 0014)

Revision ID: 0001_saved_rules
Revises: None
"""

from __future__ import annotations

from alembic import op

revision = "0001_saved_rules"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Plain SQL on purpose: the schema is the reviewable artifact, not a model to infer it from.
    # `name` is varchar(40) to match the `Name` contract (1 to 40 after strip). The whole rule
    # is one jsonb column, so condition order and a defaulted `n` round trip untouched and a
    # new contract field needs no migration.
    op.execute("""
        create table rules (
            id         uuid        primary key,
            name       varchar(40) not null,
            rule       jsonb       not null,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
    """)
    # Uniqueness ignores case, so "Foo" and "foo" collide and the route answers 409.
    op.execute("create unique index rules_name_lower_idx on rules (lower(name))")


def downgrade() -> None:
    op.execute("drop table rules")
