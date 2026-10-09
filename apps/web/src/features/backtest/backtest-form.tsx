"use client";

// The report's inputs: the rule (a `?r=` link's rule or a template), then either the one exit
// config of a portfolio backtest or the exit lab's 2 to 6 configs (spec 0009 AC-20), each with
// all six exit types, and the sim fields (spec 0007 build plan task 5). The lab opens with
// `DEFAULT_CONFIGS` (spec 0009 decision 10) and keeps your edits while you switch back and forth.
// A blank exit field means that exit is not used. A 422 lands on its own field (U-7).
import type { TemplateOut } from "@swing-scan/api-client";
import { useState, type FormEvent } from "react";

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
import { DEFAULT_CONFIGS } from "@/features/exit-lab";

import { ExitFields } from "./exit-fields";
import {
  labFrom,
  type BacktestInputs,
  type ConfigField,
  type InputField,
  type LabConfig,
} from "./inputs";
import { LabConfigs } from "./lab-configs";

/** The rule select's value for the rule a `?r=` link carried. */
const LINK_RULE = "__link__";

interface BacktestFormProps {
  templates: TemplateOut[];
  inputs: BacktestInputs;
  onChange: (inputs: BacktestInputs) => void;
  onSubmit: () => void;
  running: boolean;
  errors: Partial<Record<InputField, string>>;
  /** Each lab config's errors, in order. */
  configErrors?: Partial<Record<ConfigField, string>>[];
  /** The readable `?r=` this page opened with and its rule's name, offered as a choice. */
  link?: { r: string; name: string } | null;
}

export function BacktestForm({
  templates,
  inputs,
  onChange,
  onSubmit,
  running,
  errors,
  configErrors = [],
  link,
}: BacktestFormProps) {
  const [savedLab, setSavedLab] = useState<LabConfig[] | null>(null);
  const set = <K extends keyof BacktestInputs>(key: K, value: BacktestInputs[K]) =>
    onChange({ ...inputs, [key]: value });
  const template = templates.find((t) => t.id === inputs.template);
  const fromLink = link != null && inputs.r !== null;
  const lab = inputs.lab;

  const pickRule = (value: string) => {
    if (value === LINK_RULE && link) onChange({ ...inputs, r: link.r });
    else onChange({ ...inputs, r: null, template: value });
  };

  const pickMode = (toLab: boolean) => {
    if (toLab === (lab !== null)) return;
    if (lab) setSavedLab(lab);
    set("lab", toLab ? (savedLab ?? labFrom(DEFAULT_CONFIGS)) : null);
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

  const modeOption = (toLab: boolean, label: string) => (
    <label className="flex min-w-0 items-start gap-2 text-sm">
      <input
        type="radio"
        name="backtest-mode"
        className="mt-0.5 size-4 shrink-0 accent-primary"
        checked={toLab === (lab !== null)}
        onChange={() => pickMode(toLab)}
      />
      <span className="break-words">{label}</span>
    </label>
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
      <FieldSet className="min-w-0 gap-2">
        <FieldLegend>Run</FieldLegend>
        {modeOption(false, "One exit config: a portfolio backtest")}
        {modeOption(true, "Exit lab: compare 2 to 6 exit configs on the same entries")}
      </FieldSet>
      <FieldSet className="min-w-0">
        <FieldLegend>Exits</FieldLegend>
        {lab ? (
          <LabConfigs
            configs={lab}
            onChange={(configs) => set("lab", configs)}
            errors={configErrors}
          />
        ) : (
          <ExitFields
            value={inputs}
            onChange={(patch) => onChange({ ...inputs, ...patch })}
            errors={errors}
          />
        )}
      </FieldSet>
      <FormRow columns={4}>
        {lab ? (
          <NumberInput
            label="Horizon (bars)"
            value={inputs.horizonBars}
            onValueChange={(v) => set("horizonBars", v)}
            integer
            min={5}
            max={252}
            hint="A trade still open on this bar exits at its close"
            error={errors.horizonBars}
          />
        ) : (
          <NumberInput
            label="Max positions"
            value={inputs.maxPositions}
            onValueChange={(v) => set("maxPositions", v)}
            integer
            min={1}
            max={20}
            error={errors.maxPositions}
          />
        )}
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
          {running ? "Running…" : lab ? "Run exit lab" : "Run backtest"}
        </Button>
      </div>
    </form>
  );
}
