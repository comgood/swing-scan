"use client";

// The header's account state (spec 0015): your email as a link to the account page, or a sign
// in link, or nothing at all.
//
// Nothing where accounts do not run, which is the deployed demo: a sign in link that leads to
// "there is no sign in here" would be a dead end offered in the one place every page shows.
import Link from "next/link";

import { httpStatus } from "@/lib/api-error";

import { useMe } from "./queries";

export function AccountStatus() {
  const me = useMe();

  // Still asking, or the surface is off here: show nothing rather than guessing, so the header
  // never flashes "Sign in" on a site that has none.
  if (me.isPending) return null;
  // 501 means there is no sign in here; anything else that failed is not worth a header
  // control either, because the one thing it could offer would not work.
  if (me.error && httpStatus(me.error) !== 401) return null;

  if (!me.data) {
    return (
      <Link
        href="/sign-in"
        className="rounded-md text-sm font-medium text-muted-foreground hover:text-foreground"
      >
        Sign in
      </Link>
    );
  }

  return (
    <Link
      href="/account"
      className="min-w-0 truncate rounded-md text-sm font-medium text-muted-foreground hover:text-foreground"
      // The email is the label, so a screen reader hears whose account it is, not just "account".
      aria-label={`Your account, ${me.data.email}`}
    >
      {me.data.email}
    </Link>
  );
}
