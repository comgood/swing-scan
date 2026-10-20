"""`make claim-rules EMAIL=you@example.com`: give the rules saved before accounts an owner.

The middle step of spec 0015's three step migration. `0002` adds `rules.account_id` nullable,
this claims whatever was already in the table, then `0003` makes the column NOT NULL.

It refuses unless exactly one account matches the email, so it can never guess which of several
accounts should own rules nobody claimed. Rerunnable: with nothing left unowned it says so and
changes nothing.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

import psycopg

DATABASE_URL_ENV = "DATABASE_URL"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="the account that should own them")
    args = parser.parse_args(argv)
    email: str = args.email.strip()

    url = os.environ.get(DATABASE_URL_ENV)
    if not url:
        print(f"No {DATABASE_URL_ENV} configured. Put it in .env (see .env.example).")
        return 1

    # One transaction: either the owner is found and every orphan is claimed, or nothing changes.
    with psycopg.connect(url, prepare_threshold=0) as conn:
        # Matched case insensitively, the same way the unique index and sign in compare an email.
        found = conn.execute(
            "select id from accounts where lower(email) = lower(%s)", (email,)
        ).fetchall()
        if len(found) != 1:
            which = "no account" if not found else f"{len(found)} accounts"
            print(
                f"Refusing to claim: {which} matches {email!r}. Register that account in the web "
                "app first, then run this again."
            )
            return 1
        account_id = found[0][0]
        cursor = conn.execute(
            "update rules set account_id = %s where account_id is null", (account_id,)
        )
        claimed = cursor.rowcount

    if claimed == 0:
        print("Nothing to claim: every saved rule already has an owner. Run `make migrate`.")
        return 0
    print(f"Claimed {claimed} saved rule(s) for {email}. Now run `make migrate`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
