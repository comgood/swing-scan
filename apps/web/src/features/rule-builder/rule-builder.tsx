"use client";

// The rule builder (spec 0008): a name, 1 to 8 condition rows joined by AND, "Run scan", and the
// JSON panel. It is controlled: the caller owns `useReducer(builderReducer, …)`, so the scan
// request is `state.rule` and nothing else holds a copy (R-8). 422s map to their fields (U-7).
import type { IndicatorSpec } from "@swing-scan/api-client";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { FormErrorSummary } from "@/components/form-error-summary";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import type { FieldErrors } from "@/lib/field-errors";

import { ConditionRow } from "./condition-row";
import { builderErrors } from "./errors";
import { MAX_CONDITIONS } from "./is-rule";
import { JsonPanel } from "./json-panel";
import { DEFAULT_NAME, type BuilderAction, type BuilderState } from "./reducer";

export const MAX_ROWS_REASON = "A rule has at most 8 conditions.";
export const STALE_TEXT = "Results are for the previous rule. Run scan to update.";
export const NAME_MAX = 40;
export const NAME_EMPTY = "Give the rule a name before you run it.";
export const NAME_TOO_LONG = `Shorten the name to ${NAME_MAX} characters or fewer.`;

/**
 * The server's name rule (1 to 40 characters once trimmed), checked here first so a rejected
 * name is visible instead of a run that silently does nothing (UAT).
 */
export function nameError(name: string): string | undefined {
  const trimmed = name.trim();
  if (trimmed.length === 0) return NAME_EMPTY;
  if (trimmed.length > NAME_MAX) return NAME_TOO_LONG;
  return undefined;
}

function NameField({
  name,
  onChange,
  error,
}: {
  name: string;
  onChange: (v: string) => void;
  error?: string;
}) {
  const [draft, setDraft] = useState(name);
  const [lastName, setLastName] = useState(name);
  // A loaded rule replaces the draft; your own typing (trimmed in the rule) does not.
  if (name !== lastName) {
    setLastName(name);
    if (draft.trim() !== name) setDraft(name);
  }
  return (
    <Field invalid={Boolean(error)} className="max-w-md">
      <FieldLabel>Name</FieldLabel>
      <Input
        value={draft}
        maxLength={NAME_MAX + 20}
        onChange={(e) => {
          setDraft(e.target.value);
          onChange(e.target.value);
        }}
      />
      <FieldDescription>
        1 to {NAME_MAX} characters. It never changes the rule&apos;s trials.
      </FieldDescription>
      <FieldError>{error}</FieldError>
    </Field>
  );
}

export interface RuleBuilderProps {
  state: BuilderState;
  dispatch: (action: BuilderAction) => void;
  catalog: readonly IndicatorSpec[];
  /** The last scan's 422, through `fieldErrorsFrom422`. */
  errors?: FieldErrors;
  /** Shows "Run scan"; the caller posts `state.rule` and then dispatches `ran`. */
  onRun?: () => void;
  running?: boolean;
  /** Results on screen are for an earlier rule. */
  stale?: boolean;
  jsonOpen?: boolean;
  /** "Backtest this rule" opens this link (`/backtest?r=…`, decision 12). */
  backtestHref?: string;
}

export function RuleBuilder({
  state,
  dispatch,
  catalog,
  errors,
  onRun,
  running,
  stale,
  jsonOpen,
  backtestHref,
}: RuleBuilderProps) {
  const { rule, rowIds } = state;
  const shown = builderErrors(errors, rule.conditions.length);
  const atMax = rule.conditions.length >= MAX_CONDITIONS;
  const names = catalog.map((s) => s.name);
  const titleId = useId();
  const maxId = useId();
  // Once "Run scan" has been pressed the name is checked live, so fixing it clears the error.
  const [checked, setChecked] = useState(false);
  const localName = checked ? nameError(rule.name) : undefined;
  const nameMessage = shown.name ?? localName;
  // The name error also goes in the summary: an inline FieldError alone was missed (UAT).
  const summary = nameMessage ? [nameMessage, ...shown.top] : shown.top;
  const summaryKey = summary.join("\n");
  const summaryRef = useRef<HTMLDivElement>(null);
  const rejected = Boolean(errors) || localName !== undefined;

  // A rejected run must do something visible: focus the summary it just filled.
  useEffect(() => {
    if (summaryKey) summaryRef.current?.focus();
  }, [summaryKey]);

  return (
    <div role="group" aria-labelledby={titleId} className="flex min-w-0 flex-col gap-4">
      <h2 id={titleId} className="text-lg font-semibold">
        Conditions
      </h2>
      <NameField
        name={rule.name}
        error={nameMessage}
        onChange={(name) => dispatch({ type: "setName", name })}
      />
      <p className="text-sm text-muted-foreground">A ticker is a hit when all of these hold.</p>
      <div ref={summaryRef} tabIndex={-1}>
        <FormErrorSummary errors={summary} />
      </div>
      <div className="flex min-w-0 flex-col gap-3">
        {rule.conditions.map((condition, index) => (
          <ConditionRow
            key={rowIds[index]}
            index={index}
            condition={condition}
            catalog={catalog}
            dispatch={dispatch}
            canRemove={rule.conditions.length > 1}
            errors={shown.rows[index]}
          />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="outline"
          disabled={atMax}
          aria-describedby={atMax ? maxId : undefined}
          onClick={() => dispatch({ type: "add" })}
        >
          Add condition
        </Button>
        {atMax && (
          <span id={maxId} className="text-xs text-muted-foreground">
            {MAX_ROWS_REASON}
          </span>
        )}
        {onRun && (
          <Button
            onClick={() => {
              setChecked(true);
              if (!nameError(rule.name)) onRun();
            }}
            disabled={running}
          >
            Run scan
          </Button>
        )}
        {backtestHref && (
          // A rejected rule would travel into `?r=`, so the hand off waits for a valid one.
          <Button disabled={rejected} render={rejected ? undefined : <Link href={backtestHref} />}>
            Backtest this rule
          </Button>
        )}
        {state.source !== "custom" && (
          <Button
            variant="secondary"
            onClick={() =>
              dispatch({
                type: "load",
                rule: { ...rule, name: DEFAULT_NAME },
                source: "custom",
                dirty: true,
              })
            }
          >
            Create my own rule
          </Button>
        )}
      </div>
      {stale && (
        <p role="status" className="text-sm text-muted-foreground">
          {STALE_TEXT}
        </p>
      )}
      <JsonPanel
        rule={rule}
        names={names}
        defaultOpen={jsonOpen}
        onLoad={(loaded) => dispatch({ type: "load", rule: loaded, source: "custom", dirty: true })}
      />
    </div>
  );
}
