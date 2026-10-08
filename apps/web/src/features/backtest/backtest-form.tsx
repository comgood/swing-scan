"use client";

// The report's inputs: the template (rule), the `stop_pct` and `time` exits feature 9 supports,
// and the sim fields (spec 0007 build plan task 5). A 422 lands on its own field (U-7).
import type { TemplateOut } from "@swing-scan/api-client";
import type { FormEvent } from "react";

import { FormRow } from "@/components/form-row";
import { NumberInput } from "@/components/number-input";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";

import type { BacktestInputs, InputField } from "./inputs";

interface BacktestFormProps {
  templates: TemplateOut[];
  inputs: BacktestInputs;
  onChange: (inputs: BacktestInputs) => void;
  onSubmit: () => void;
  running: boolean;
  errors: Partial<Record<InputField, string>>;
}

export function BacktestForm({
  templates,
  inputs,
  onChange,
  onSubmit,
  running,
  errors,
}: BacktestFormProps) {
  const set = <K extends keyof BacktestInputs>(key: K, value: BacktestInputs[K]) =>
    onChange({ ...inputs, [key]: value });
  const template = templates.find((t) => t.id === inputs.template);

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
        <FieldLabel>Template</FieldLabel>
        <NativeSelect value={inputs.template} onChange={(e) => set("template", e.target.value)}>
          {templates.map((t) => (
            <NativeSelectOption key={t.id} value={t.id}>
              {t.name}
            </NativeSelectOption>
          ))}
        </NativeSelect>
        {template && <FieldDescription>{template.description}</FieldDescription>}
      </Field>
      <FormRow columns={2}>
        <NumberInput
          label="Stop loss (%)"
          value={inputs.stopPct}
          onValueChange={(v) => set("stopPct", v)}
          hint="Blank for no stop"
          error={errors.stopPct}
        />
        <NumberInput
          label="Time exit (bars)"
          value={inputs.timeBars}
          onValueChange={(v) => set("timeBars", v)}
          integer
          hint="Blank for no time exit"
          error={errors.timeBars}
        />
      </FormRow>
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
