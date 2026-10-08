"use client";

// The rule as JSON, with Copy, and a paste box that loads a rule (spec 0008 decision 10).
// Pasted text is untrusted: parsed in a try and shape checked; it is shown as text only.
import { Field as FieldPrimitive } from "@base-ui/react/field";
import type { Rule } from "@swing-scan/api-client";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";

import { normaliseRule } from "./is-rule";

export const NOT_A_RULE = "Not a rule";

/** The rule in pasted text, or null. */
export function parseRuleText(text: string, names: readonly string[]): Rule | null {
  try {
    return normaliseRule(JSON.parse(text), names);
  } catch {
    return null;
  }
}

interface JsonPanelProps {
  rule: Rule;
  names: readonly string[];
  onLoad: (rule: Rule) => void;
  /** Opens the panel, e.g. in the gallery. */
  defaultOpen?: boolean;
  defaultDraft?: string;
  /** Shows "Not a rule" from the start (the gallery). */
  defaultError?: boolean;
}

export function JsonPanel({
  rule,
  names,
  onLoad,
  defaultOpen,
  defaultDraft = "",
  defaultError = false,
}: JsonPanelProps) {
  const [draft, setDraft] = useState(defaultDraft);
  const [error, setError] = useState<string | null>(defaultError ? NOT_A_RULE : null);
  const [copied, setCopied] = useState(false);
  const json = JSON.stringify(rule, null, 2);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  const load = () => {
    const parsed = parseRuleText(draft, names);
    if (!parsed) {
      setError(NOT_A_RULE);
      return;
    }
    setError(null);
    setDraft("");
    onLoad(parsed);
  };

  return (
    <details open={defaultOpen} className="min-w-0 rounded-lg border p-4">
      <summary className="cursor-pointer text-sm font-medium">Rule as JSON</summary>
      <div className="mt-3 flex min-w-0 flex-col gap-3">
        <pre
          tabIndex={0}
          aria-label="Rule JSON"
          className="max-h-80 min-w-0 overflow-auto rounded-md bg-muted p-3 font-mono text-xs"
        >
          {json}
        </pre>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void copy()}>
            Copy JSON
          </Button>
          <span role="status" className="text-xs text-muted-foreground">
            {copied ? "Copied" : ""}
          </span>
        </div>
        <Field invalid={Boolean(error)}>
          <FieldLabel>Paste a rule</FieldLabel>
          <FieldPrimitive.Control
            render={
              <textarea
                rows={4}
                spellCheck={false}
                className="w-full min-w-0 rounded-md border border-input bg-transparent px-3 py-2 font-mono text-base aria-invalid:border-destructive sm:text-sm"
              />
            }
            value={draft}
            onValueChange={(value) => {
              setDraft(String(value));
              setError(null);
            }}
          />
          <FieldError>{error}</FieldError>
        </Field>
        <div>
          <Button size="sm" onClick={load} disabled={draft.trim() === ""}>
            Load rule
          </Button>
        </div>
      </div>
    </details>
  );
}
