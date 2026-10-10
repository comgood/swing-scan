"use client";

// One side of a condition: indicator, `n` (windowed only), bars ago and multiplier
// (spec 0008 AC-6, decision 7). Ranges show as hints; the server's 422 is the judge.
import type { IndicatorSpec } from "@swing-scan/api-client";
import { useState } from "react";

import { NumberInput } from "@/components/number-input";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";

import type { OperandErrors } from "./errors";
import { withIndicator, type IndOperand } from "./reducer";

const ENTER_A_NUMBER = "Enter a number";

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

interface OperandFieldsProps {
  operand: IndOperand;
  catalog: readonly IndicatorSpec[];
  onChange: (operand: IndOperand) => void;
  errors?: OperandErrors;
}

export function OperandFields({ operand, catalog, onChange, errors = {} }: OperandFieldsProps) {
  const spec = catalog.find((s) => s.name === operand.ind);
  // A price field has no window, so the slot goes away entirely rather than leaving a hint with
  // nothing above it. A 422 on `n` then has no field of its own, so it lands on the indicator
  // that chose the price field (U-7).
  const windowed = spec?.windowed ?? false;
  const indError = errors.ind ?? (windowed ? undefined : errors.n);
  return (
    <div className="grid min-w-0 grid-cols-1 gap-3 *:min-w-0 sm:grid-cols-4">
      <Field invalid={Boolean(indError)}>
        <FieldLabel>Indicator</FieldLabel>
        <NativeSelect
          value={operand.ind}
          onChange={(e) =>
            onChange(withIndicator(operand, e.target.value as IndOperand["ind"], catalog))
          }
        >
          {catalog.map((s) => (
            <NativeSelectOption key={s.name} value={s.name}>
              {s.label}
            </NativeSelectOption>
          ))}
        </NativeSelect>
        <FieldError>{indError}</FieldError>
      </Field>
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
        label="Bars ago"
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
