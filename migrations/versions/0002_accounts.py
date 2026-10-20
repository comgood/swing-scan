"""accounts, and a rule now belongs to one (spec 0015)

Revision ID: 0002_accounts
Revises: 0001_saved_rules

`account_id` arrives nullable, because a NOT NULL column cannot be added to a table that
already holds rows. `0003` tightens it once the existing rules are claimed by `make claim-rules`.
"""

from __future__ import annotations

from alembic import op

revision = "0002_accounts"
down_revision = "0001_saved_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Plain SQL, as 0001 established: the schema is the reviewable artifact.
    # `email` is varchar(254), the longest address a mail system has to accept. It is only ever
    # an identifier here: nothing is sent to it, so there is no verification and no format check
    # beyond its length. `password_hash` is the Argon2id PHC string, which carries its own salt
    # and cost parameters, so there is no salt column and no parameter to choose.
    # No `updated_at`: changing an email or a password is out of scope, so nothing updates a row.
    op.execute("""
        create table accounts (
            id            uuid         primary key,
            email         varchar(254) not null,
            password_hash text         not null,
            created_at    timestamptz  not null default now()
        )
    """)
    # Uniqueness ignores case, so "You@x.com" and "you@x.com" are one account (AC-6).
    op.execute("create unique index accounts_email_lower_idx on accounts (lower(email))")

    # Cascade, so deleting an account takes its rules with it and no code path can forget (AC-9).
    op.execute("""
        alter table rules
            add column account_id uuid,
            add constraint rules_account_id_fkey
                foreign key (account_id) references accounts (id) on delete cascade
    """)
    # Name uniqueness becomes per account: two accounts may each keep a rule called "Foo",
    # one account may not keep two. The global index 0001 created cannot express that.
    op.execute("drop index rules_name_lower_idx")
    op.execute("""
        create unique index rules_account_name_lower_idx
            on rules (account_id, lower(name))
    """)


def downgrade() -> None:
    # Restoring the global name index is not always possible: once two accounts have each saved
    # a rule under the same name, `rules_name_lower_idx` cannot be created, and a downgrade that
    # fails halfway is worse than one that refuses. Forward is the only route from here, which is
    # fine for a local database you can drop and migrate again.
    duplicates = op.get_bind().exec_driver_sql(
        "select count(*) from (select lower(name) from rules group by 1 having count(*) > 1) d"
    )
    if (duplicates.scalar() or 0) > 0:
        raise RuntimeError(
            "Cannot downgrade 0002: two accounts share a rule name, so the global unique index "
            "on lower(name) cannot be restored. Drop the duplicate rules first, or recreate the "
            "database with `make migrate`."
        )
    op.execute("drop index rules_account_name_lower_idx")
    op.execute("alter table rules drop constraint rules_account_id_fkey, drop column account_id")
    op.execute("create unique index rules_name_lower_idx on rules (lower(name))")
    op.execute("drop table accounts")
