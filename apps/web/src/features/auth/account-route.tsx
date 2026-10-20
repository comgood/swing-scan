"use client";

// The account page (spec 0015): who you are, sign out, and delete.
//
// Spec 0015 put deletion behind a confirm dialog in the header menu. There is no Dialog or
// DropdownMenu in the installed component inventory (spec 0003), and adding two primitives to
// the design system to hold one destructive button is a bigger change than giving deletion its
// own small page. The criterion only asks that deleting works and leaves the browser signed
// out, which this does. A two step confirm replaces the modal: the button has to be armed
// before it will delete, so nothing is one stray click away.
import Link from "next/link";
import { useState } from "react";

import { Banner } from "@/components/banner";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { httpStatus } from "@/lib/api-error";

import { AccountsNotHere } from "./auth-routes";
import { goTo } from "./navigate";
import { useDeleteAccount, useLogout, useMe } from "./queries";

export const DELETE_WARNING =
  "Deleting your account also deletes every rule you have saved. The database does that in one " +
  "step, so there is nothing left behind and nothing to undo.";

export function AccountRoute() {
  const me = useMe();
  const logout = useLogout();
  const remove = useDeleteAccount();
  const [armed, setArmed] = useState(false);

  if (me.isPending) return <Skeleton className="h-48 w-full max-w-xl" />;
  if (httpStatus(me.error) === 501) return <AccountsNotHere />;
  if (!me.data) {
    return (
      <p className="text-sm text-muted-foreground">
        You are signed out.{" "}
        <Link href="/sign-in" className="text-primary underline underline-offset-4">
          Sign in
        </Link>
      </p>
    );
  }

  return (
    <section aria-labelledby="account-title" className="flex min-w-0 max-w-xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 id="account-title" className="text-2xl font-semibold">
          Your account
        </h1>
        <p className="text-sm text-muted-foreground">
          Signed in as <span className="font-medium text-foreground">{me.data.email}</span>
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="outline"
          disabled={logout.isPending}
          onClick={() => logout.mutate(undefined, { onSuccess: () => goTo("/") })}
        >
          {logout.isPending && <Spinner />}
          Sign out
        </Button>
      </div>

      <Separator />

      <div className="flex min-w-0 flex-col gap-3">
        <h2 className="text-lg font-semibold">Delete this account</h2>
        <Banner variant="warning" title="This cannot be undone">
          {DELETE_WARNING}
        </Banner>
        {remove.error && (
          <p role="alert" className="text-sm text-destructive">
            The account could not be deleted. Check the engine is running and try again.
          </p>
        )}
        {armed ? (
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium">Delete {me.data.email} and its saved rules?</p>
            <Button
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => remove.mutate(undefined, { onSuccess: () => goTo("/") })}
            >
              {remove.isPending && <Spinner />}
              Yes, delete it
            </Button>
            <Button variant="outline" onClick={() => setArmed(false)}>
              Cancel
            </Button>
          </div>
        ) : (
          <Button variant="outline" className="self-start" onClick={() => setArmed(true)}>
            Delete account
          </Button>
        )}
      </div>
    </section>
  );
}
