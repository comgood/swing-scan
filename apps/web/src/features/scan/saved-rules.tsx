"use client";

// Saved rules (specs 0014, 0015): save the rule on screen under its name, load one back,
// delete one. Three states, and telling them apart is the point:
//
//   501  the surface does not exist here (the deployed demo) -> show nothing at all
//   401  it exists and you are signed out -> say so, and link to sign in
//   200  your rules
//
// The old version hid the section on any failure, which was right while there were no accounts.
// Now hiding it when you are merely signed out would read as "this feature is gone" on the one
// machine where it works (spec 0015, AC-12).
import type { Rule, SavedRule } from "@swing-scan/api-client";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { ApiRequestError, httpStatus } from "@/lib/api-error";

import { RuleRejectedError, useDeleteRule, useSavedRules, useSaveRule } from "./queries";

export const EMPTY_TEXT = "Nothing saved yet. Save the rule above to keep it.";
export const SAVE_FAILED = "The rule could not be saved.";
export const SIGNED_OUT_TITLE = "Sign in to save rules";
export const SIGNED_OUT_HINT =
  "Saved rules belong to an account. Everything else on this page works without one.";

/**
 * What to show when a save is refused: the API's own words, so a duplicate name reads as the
 * 409 said it and a rejected rule reads as its first field error (AC-3, AC-4).
 */
export function saveMessage(error: Error): string {
  if (error instanceof RuleRejectedError) {
    const { fields, form } = error.fieldErrors;
    return [...form, ...Object.values(fields)][0] ?? SAVE_FAILED;
  }
  if (error instanceof ApiRequestError && error.apiError.kind === "http") {
    return error.apiError.detail ?? SAVE_FAILED;
  }
  return SAVE_FAILED;
}

export function SavedRules({ rule, onLoad }: { rule: Rule; onLoad: (rule: Rule) => void }) {
  const saved = useSavedRules();
  const save = useSaveRule();
  const remove = useDeleteRule();

  // Signed out, but the feature is here: say which, rather than vanishing (AC-12).
  if (httpStatus(saved.error) === 401) {
    return (
      <section aria-labelledby="saved-rules" className="flex min-w-0 flex-col gap-3">
        <h2 id="saved-rules" className="text-lg font-semibold">
          Saved rules
        </h2>
        <EmptyState
          title={SIGNED_OUT_TITLE}
          hint={
            <>
              {SIGNED_OUT_HINT}{" "}
              <Link href="/sign-in" className="text-primary underline underline-offset-4">
                Sign in
              </Link>
            </>
          }
        />
      </section>
    );
  }

  // No list and not a 401: the surface is not here (501 off your machine), or the API is down.
  // Both look the same on purpose, because in both cases there is nothing you can do here.
  if (!saved.data) return null;

  return (
    <section aria-labelledby="saved-rules" className="flex min-w-0 flex-col gap-3">
      <h2 id="saved-rules" className="text-lg font-semibold">
        Saved rules
      </h2>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          disabled={save.isPending}
          onClick={() => save.mutate(rule)}
          // The name belongs to the rule, so saving twice under one name is the 409, not a prompt.
        >
          Save this rule
        </Button>
        {save.error && (
          <p role="alert" className="text-sm text-destructive">
            {saveMessage(save.error)}
          </p>
        )}
      </div>
      {saved.data.length === 0 ? (
        <p className="text-sm text-muted-foreground">{EMPTY_TEXT}</p>
      ) : (
        <ul className="flex min-w-0 flex-col gap-2">
          {saved.data.map((item: SavedRule) => (
            <li key={item.id} className="flex flex-wrap items-center gap-2">
              <span className="min-w-0 flex-1 truncate text-sm">{item.rule.name}</span>
              {/* The list carries whole rules, so Load is local: no second request (spec 0014). */}
              {/* Named per row: several rows of bare "Load" are indistinguishable to a screen
                  reader, which is what the visible name beside them is doing for everyone else. */}
              <Button
                variant="secondary"
                size="sm"
                aria-label={`Load ${item.rule.name}`}
                onClick={() => onLoad(item.rule)}
              >
                Load
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={remove.isPending}
                aria-label={`Delete ${item.rule.name}`}
                onClick={() => remove.mutate(item.id)}
              >
                Delete
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
