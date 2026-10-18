"use client";

// Saved rules (spec 0014): save the rule on screen under its name, load one back, delete one.
// The whole section is hidden unless `GET /rules` answers, which is how the deployed demo looks:
// there are no accounts yet, so the API answers 501 there and nothing here is reachable (AC-6).
import type { Rule, SavedRule } from "@swing-scan/api-client";

import { Button } from "@/components/ui/button";
import { ApiRequestError } from "@/lib/api-error";

import { RuleRejectedError, useDeleteRule, useSavedRules, useSaveRule } from "./queries";

export const EMPTY_TEXT = "Nothing saved yet. Save the rule above to keep it.";
export const SAVE_FAILED = "The rule could not be saved.";

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

  // No list means no feature here: 501 off your machine, and the same when the API is down.
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
              <Button variant="secondary" size="sm" onClick={() => onLoad(item.rule)}>
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
