"""every rule has an owner (spec 0015)

Revision ID: 0003_rules_account_not_null
Revises: 0002_accounts

The second half of the three step migration. It refuses rather than failing on a constraint
violation, so the message tells you what to run. `transaction_per_migration` in `env.py` is what
makes that refusal safe: `0002` stays applied, so there is an `accounts` table to register into
and the backfill can actually run.
"""

from __future__ import annotations

from alembic import op

revision = "0003_rules_account_not_null"
down_revision = "0002_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    orphans = op.get_bind().exec_driver_sql("select count(*) from rules where account_id is null")
    count = orphans.scalar() or 0
    if count > 0:
        raise RuntimeError(
            f"{count} saved rule(s) have no owner yet, so account_id cannot become NOT NULL. "
            "Register an account in the web app, then run "
            "`make claim-rules EMAIL=you@example.com` and `make migrate` again. "
            "Migration 0002 stays applied, so nothing is lost."
        )
    # On a fresh database this is the common path: zero rows, so it runs straight through and
    # `make migrate` reaches head in one command.
    op.execute("alter table rules alter column account_id set not null")


def downgrade() -> None:
    op.execute("alter table rules alter column account_id drop not null")
