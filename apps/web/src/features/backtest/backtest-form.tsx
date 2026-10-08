"use client";

// The report's inputs: the rule (a `?r=` link's rule or a template), the one exit config with
// all six exit types (features 9 and 11), and the sim fields (spec 0007 build plan task 5). A
// blank exit field means that exit is not used. A 422 lands on its own field (U-7).
import type { TemplateOut } from "@swing-scan/api-client";
import type { FormEvent } from "react";

import { FormRow } from "@/components/form-row";
import { NumberInput } from "@/components/number-input";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";

import type { BacktestInputs, ExitField, InputField } from "./inputs";

/** The rule select's value for the rule a `?r=` link carried. */
const LINK_RULE = "__link__";

interface BacktestFormProps {
  templates: TemplateOut[];
  inputs: BacktestInputs;
  onChange: (inputs: BacktestInputs) => void;
  onSubmit: () => void;
  running: boolean;
  errors: Partial<Record<InputField, string>>;
  /** The readable `?r=` this page opened with and its rule's name, offered as a choice. */
  link?: { r: string; name: string } | null;
}

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

export function BacktestForm({
  templates,
  inputs,
  onChange,
  onSubmit,
  running,
  errors,
  link,
}: BacktestFormProps) {
  const set = <K extends keyof BacktestInputs>(key: K, value: BacktestInputs[K]) =>
    onChange({ ...inputs, [key]: value });
  const template = templates.find((t) => t.id === inputs.template);
  const fromLink = link != null && inputs.r !== null;

  const pickRule = (value: string) => {
    if (value === LINK_RULE && link) onChange({ ...inputs, r: link.r });
    else onChange({ ...inputs, r: null, template: value });
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit();
  };

  const dateField = (key: "start" | "end", label: string) => (
    <Field invalid={Boolean(errors[key])}>
      <FieldLabel>{label}</FieldLabel>
      <Input type="date" value={inputs[key]} onChange={(e) => set(key, e.target.value)} />
      <FieldDescription>Blank uses the whole history.</FieldDescription>
      <FieldError>{errors[key]}</FieldError>
    </Field>
  );

  return (
    <form onSubmit={submit} aria-label="Backtest settings" className="flex min-w-0 flex-col gap-4">
      <Field className="max-w-md">
        <FieldLabel>Rule</FieldLabel>
        <NativeSelect
          value={fromLink ? LINK_RULE : inputs.template}
          onChange={(e) => pickRule(e.target.value)}
        >
          {link && (
            <NativeSelectOption value={LINK_RULE}>From your link: {link.name}</NativeSelectOption>
          )}
          {templates.map((t) => (
            <NativeSelectOption key={t.id} value={t.id}>
              {t.name}
            </NativeSelectOption>
          ))}
        </NativeSelect>
        <FieldDescription>
          {fromLink ? "The rule as you built it on the scan page." : template?.description}
        </FieldDescription>
      </Field>
      <FieldSet className="min-w-0">
        <FieldLegend>Exits</FieldLegend>
        <FormRow columns={4}>
          {EXITS.map((exit) => (
            <NumberInput
              key={exit.field}
              label={exit.label}
              value={inputs[exit.field]}
              onValueChange={(v) => set(exit.field, v)}
              integer={exit.integer}
              hint={exit.hint}
              error={errors[exit.field]}
            />
          ))}
          <Field>
            <FieldLabel>MA type</FieldLabel>
            <NativeSelect
              value={inputs.maKind}
              onChange={(e) => set("maKind", e.target.value === "ema" ? "ema" : "sma")}
            >
              <NativeSelectOption value="sma">Simple (SMA)</NativeSelectOption>
              <NativeSelectOption value="ema">Exponential (EMA)</NativeSelectOption>
            </NativeSelect>
            <FieldDescription>Used by the MA exit</FieldDescription>
          </Field>
        </FormRow>
      </FieldSet>
      <FormRow columns={4}>
        <NumberInput
          label="Max positions"
          value={inputs.maxPositions}
          onValueChange={(v) => set("maxPositions", v)}
          integer
          min={1}
          max={20}
          error={errors.maxPositions}
        />
        <NumberInput
          label="Slippage (bps)"
          value={inputs.slippageBps}
          onValueChange={(v) => set("slippageBps", v)}
          error={errors.slippageBps}
        />
        {dateField("start", "Start")}
        {dateField("end", "End")}
      </FormRow>
      <div>
        <Button type="submit" disabled={running} aria-busy={running}>
          {running ? "Running…" : "Run backtest"}
        </Button>
      </div>
    </form>
  );
}
