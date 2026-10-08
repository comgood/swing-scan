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
  return (
    <div className="grid min-w-0 grid-cols-1 gap-3 *:min-w-0 sm:grid-cols-4">
      <Field invalid={Boolean(errors.ind)}>
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
        <FieldError>{errors.ind}</FieldError>
      </Field>
      {spec?.windowed ? (
        <RequiredNumber
          label="Window (n)"
          integer
          value={operand.n ?? null}
          min={spec.n_min ?? undefined}
          max={spec.n_max ?? undefined}
          error={errors.n}
          onChange={(n) => onChange({ ...operand, n })}
        />
      ) : (
        <p className="self-end pb-2 text-xs text-muted-foreground">
          No window for a price field
          {errors.n && <span className="block text-sm text-destructive">{errors.n}</span>}
        </p>
      )}
      <RequiredNumber
        label="Bars ago"
        integer
        value={operand.offset}
        min={0}
        max={20}
        error={errors.offset}
        onChange={(offset) => onChange({ ...operand, offset })}
      />
      <RequiredNumber
        label="Multiplier (×)"
        value={operand.mult}
        min={0.1}
        max={10}
        error={errors.mult}
        onChange={(mult) => onChange({ ...operand, mult })}
      />
    </div>
  );
}
