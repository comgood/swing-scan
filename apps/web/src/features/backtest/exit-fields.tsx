"use client";

// One full exit set: all six exit types (features 9 and 11), used by the one config form and by
// each exit lab config. A blank field means that exit is not used. A 422 lands on its field (U-7).
import { FormRow } from "@/components/form-row";
import { NumberInput } from "@/components/number-input";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";

import type { ExitField, ExitInputs } from "./inputs";

interface ExitSpec {
  field: ExitField;
  label: string;
  hint: string;
  integer?: boolean;
}

const EXITS: readonly ExitSpec[] = [
  { field: "stopPct", label: "Stop loss (%)", hint: "Blank for no stop" },
  { field: "targetPct", label: "Target (%)", hint: "Blank for no target" },
  { field: "trailPct", label: "Trailing stop (%)", hint: "Blank for no trailing stop" },
  { field: "timeBars", label: "Time exit (bars)", hint: "Blank for no time exit", integer: true },
  { field: "atrK", label: "ATR stop (× ATR)", hint: "Blank for no ATR stop" },
  { field: "atrN", label: "ATR length (bars)", hint: "Used by the ATR stop", integer: true },
  { field: "maN", label: "Close below MA (bars)", hint: "Blank for no MA exit", integer: true },
];

interface ExitFieldsProps {
  value: ExitInputs;
  onChange: (patch: Partial<ExitInputs>) => void;
  errors: Partial<Record<ExitField, string>>;
}

export function ExitFields({ value, onChange, errors }: ExitFieldsProps) {
  return (
    <FormRow columns={4}>
      {EXITS.map((exit) => (
        <NumberInput
          key={exit.field}
          label={exit.label}
          value={value[exit.field]}
          onValueChange={(v) => onChange({ [exit.field]: v })}
          integer={exit.integer}
          hint={exit.hint}
          error={errors[exit.field]}
        />
      ))}
      <Field>
        <FieldLabel>MA type</FieldLabel>
        <NativeSelect
          value={value.maKind}
          onChange={(e) => onChange({ maKind: e.target.value === "ema" ? "ema" : "sma" })}
        >
          <NativeSelectOption value="sma">Simple (SMA)</NativeSelectOption>
          <NativeSelectOption value="ema">Exponential (EMA)</NativeSelectOption>
        </NativeSelect>
        <FieldDescription>Used by the MA exit</FieldDescription>
      </Field>
    </FormRow>
  );
}
