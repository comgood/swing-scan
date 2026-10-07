"use client";

// A number field that keeps your draft text and commits on blur or Enter (spec 0003 AC-6).
// It only checks that the text is a number; ranges are the server's 422 to report.
// Ids, aria-invalid and aria-describedby come from Base UI's Field (React.useId inside).
import { useState, type KeyboardEvent } from "react";

import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

const NUMBER_TEXT = /^-?(\d+\.?\d*|\.\d+)$/;

export interface NumberInputProps {
  label: string;
  value: number | null;
  onValueChange: (value: number | null) => void;
  min?: number;
  max?: number;
  integer?: boolean;
  /** A server error for this field, e.g. from `errorAt` (AC-7). */
  error?: string;
  hint?: string;
  disabled?: boolean;
  name?: string;
  className?: string;
}

type Parsed = { ok: true; value: number | null } | { ok: false; message: string };

export function parseNumberText(text: string, integer: boolean): Parsed {
  const trimmed = text.trim();
  if (trimmed === "") return { ok: true, value: null };
  if (!NUMBER_TEXT.test(trimmed)) return { ok: false, message: "Enter a number" };
  const value = Number(trimmed) + 0; // `+ 0` turns -0 into 0
  if (integer && !Number.isInteger(value)) return { ok: false, message: "Enter a whole number" };
  return { ok: true, value };
}

function textOf(value: number | null): string {
  return value === null ? "" : String(value);
}

export function NumberInput({
  label,
  value,
  onValueChange,
  min,
  max,
  integer = false,
  error,
  hint,
  disabled,
  name,
  className,
}: NumberInputProps) {
  const [draft, setDraft] = useState(() => textOf(value));
  const [localError, setLocalError] = useState<string | null>(null);
  const [focused, setFocused] = useState(false);
  const [lastValue, setLastValue] = useState(value);

  // A value set from outside while you are not typing (a template load) replaces the draft.
  if (value !== lastValue) {
    setLastValue(value);
    if (!focused) {
      setDraft(textOf(value));
      setLocalError(null);
    }
  }

  const commit = () => {
    const parsed = parseNumberText(draft, integer);
    if (!parsed.ok) {
      setLocalError(parsed.message);
      return;
    }
    setLocalError(null);
    setDraft(textOf(parsed.value));
    if (parsed.value !== value) onValueChange(parsed.value);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    // Commit first; the key still submits the form.
    if (event.key === "Enter") commit();
  };

  const rangeHint =
    min !== undefined && max !== undefined
      ? `Allowed: ${String(min)} to ${String(max)}`
      : undefined;
  const description = [hint, rangeHint].filter(Boolean).join(" · ");
  const shownError = localError ?? error;

  return (
    <Field invalid={Boolean(shownError)} disabled={disabled} name={name} className={className}>
      <FieldLabel>{label}</FieldLabel>
      <Input
        type="text"
        inputMode={integer ? "numeric" : "decimal"}
        autoComplete="off"
        value={draft}
        onChange={(event) => {
          setDraft(event.target.value);
          setLocalError(null);
        }}
        onFocus={() => setFocused(true)}
        onBlur={() => {
          setFocused(false);
          commit();
        }}
        onKeyDown={onKeyDown}
        className="tabular-nums"
      />
      {description && <FieldDescription>{description}</FieldDescription>}
      <FieldError>{shownError}</FieldError>
    </Field>
  );
}
