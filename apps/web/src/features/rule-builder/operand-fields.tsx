"use client";

// One side of a condition: the field (a price field, an indicator, or a fixed number on the
// right), `n` (windowed only), bars back and multiplier (spec 0008 AC-6, decision 7). Ranges
// show as hints; the server's 422 is the judge.
import type { IndicatorSpec } from "@swing-scan/api-client";
import { useState } from "react";

import { NumberInput } from "@/components/number-input";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";

import type { OperandErrors } from "./errors";
import { withIndicator, type IndOperand } from "./reducer";

const ENTER_A_NUMBER = "Enter a number";

/** The right side's "a fixed number" choice, which is a `kind`, not an indicator name. */
export const NUMBER_CHOICE = "__number";

export const FIELD_LABEL = "Field";

interface RequiredNumberProps {
  label: string;
  value: number | null;
  onChange: (value: number) => void;
  integer?: boolean;
  min?: number;
  max?: number;
  error?: string;
  /** One plain line under the field, which a beginner cannot guess (doc 01 section 6.8). */
  hint?: string;
}

/** A number the rule always needs: an empty entry keeps the last value and asks for one. */
export function RequiredNumber({ onChange, error, ...props }: RequiredNumberProps) {
  const [empty, setEmpty] = useState(false);
  return (
    <NumberInput
      {...props}
      error={empty ? ENTER_A_NUMBER : error}
      onValueChange={(next) => {
        setEmpty(next === null);
        if (next !== null) onChange(next);
      }}
    />
  );
}

/**
 * The option text carries the name the rule and the scan's columns use, with `(n)` on the ones
 * that take a window, so the "Window (n)" field below has an obvious owner: `sma(n)`.
 */
function optionText(spec: IndicatorSpec): string {
  return `${spec.label} — ${spec.name}${spec.windowed ? "(n)" : ""}`;
}

interface FieldSelectProps {
  /** An indicator name, or `NUMBER_CHOICE` on a right side holding a number. */
  value: string;
  catalog: readonly IndicatorSpec[];
  error?: string;
  /** Given on a right side: it may also hold a fixed number (decision 9). */
  onPickNumber?: () => void;
  onPickIndicator: (ind: IndOperand["ind"]) => void;
}

/** What this side of the condition reads: one list, so there is no second "compare with" step. */
function FieldSelect({ value, catalog, error, onPickNumber, onPickIndicator }: FieldSelectProps) {
  return (
    <Field invalid={Boolean(error)}>
      <FieldLabel>{FIELD_LABEL}</FieldLabel>
      <NativeSelect
        value={value}
        onChange={(e) => {
          const picked = e.target.value;
          if (picked === NUMBER_CHOICE) onPickNumber?.();
          else onPickIndicator(picked as IndOperand["ind"]);
        }}
      >
        {onPickNumber && (
          <NativeSelectOption value={NUMBER_CHOICE}>A number you type</NativeSelectOption>
        )}
        {catalog.map((s) => (
          <NativeSelectOption key={s.name} value={s.name}>
            {optionText(s)}
          </NativeSelectOption>
        ))}
      </NativeSelect>
      <FieldError>{error}</FieldError>
    </Field>
  );
}

interface OperandFieldsProps {
  operand: IndOperand;
  catalog: readonly IndicatorSpec[];
  onChange: (operand: IndOperand) => void;
  errors?: OperandErrors;
  /** Right side only: picking a number switches this side's kind. */
  onPickNumber?: () => void;
}

export function OperandFields({
  operand,
  catalog,
  onChange,
  errors = {},
  onPickNumber,
}: OperandFieldsProps) {
  const spec = catalog.find((s) => s.name === operand.ind);
  // A price field has no window, so the slot goes away entirely rather than leaving a hint with
  // nothing above it. A 422 on `n` then has no field of its own, so it lands on the field
  // that chose the price field (U-7).
  const windowed = spec?.windowed ?? false;
  const indError = errors.ind ?? (windowed ? undefined : errors.n);
  return (
    <div className="grid min-w-0 grid-cols-1 gap-3 *:min-w-0 sm:grid-cols-4">
      <FieldSelect
        value={operand.ind}
        catalog={catalog}
        error={indError}
        onPickNumber={onPickNumber}
        onPickIndicator={(ind) => onChange(withIndicator(operand, ind, catalog))}
      />
      {windowed && (
        <RequiredNumber
          label="Window (n)"
          hint="How many bars the indicator averages or looks back over."
          integer
          value={operand.n ?? null}
          min={spec?.n_min ?? undefined}
          max={spec?.n_max ?? undefined}
          error={errors.n}
          onChange={(n) => onChange({ ...operand, n })}
        />
      )}
      <RequiredNumber
        label="Bars back"
        hint="0 is today's bar, 1 is the bar before it."
        integer
        value={operand.offset}
        min={0}
        max={20}
        error={errors.offset}
        onChange={(offset) => onChange({ ...operand, offset })}
      />
      <RequiredNumber
        label="Multiplier (×)"
        hint="Scales the value. 1 leaves it unchanged."
        value={operand.mult}
        min={0.1}
        max={10}
        error={errors.mult}
        onChange={(mult) => onChange({ ...operand, mult })}
      />
    </div>
  );
}

interface NumberOperandFieldsProps {
  value: number | null;
  catalog: readonly IndicatorSpec[];
  errors?: OperandErrors;
  onChange: (value: number) => void;
  onPickIndicator: (ind: IndOperand["ind"]) => void;
}

/** A right side holding a fixed number: the same field list, then the number itself. */
export function NumberOperandFields({
  value,
  catalog,
  errors = {},
  onChange,
  onPickIndicator,
}: NumberOperandFieldsProps) {
  return (
    <div className="grid min-w-0 grid-cols-1 gap-3 *:min-w-0 sm:grid-cols-4">
      <FieldSelect
        value={NUMBER_CHOICE}
        catalog={catalog}
        error={errors.ind}
        onPickNumber={() => undefined}
        onPickIndicator={onPickIndicator}
      />
      <RequiredNumber label="Number" value={value} error={errors.value} onChange={onChange} />
    </div>
  );
}
