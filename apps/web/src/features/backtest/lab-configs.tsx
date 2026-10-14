"use client";

// The exit lab's configs (spec 0009 AC-20, X-2): 2 to 6 named exit sets, each a full exit form.
// Config 1 is the baseline (its IS trades feed the guide row and its trades the list). Add is
// disabled at 6 and remove at 2; removing a config moves focus to "Add config".
import { useRef } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { formatInt } from "@/lib/format";

import { ExitFields } from "./exit-fields";
import {
  DEFAULT_INPUTS,
  MAX_CONFIGS,
  MIN_CONFIGS,
  nextConfigId,
  type ConfigField,
  type LabConfig,
} from "./inputs";

interface LabConfigsProps {
  configs: LabConfig[];
  onChange: (configs: LabConfig[]) => void;
  errors: Partial<Record<ConfigField, string>>[];
}

/** A new config: the first free "Config N" name with the one config form's default exits. */
function newConfig(configs: LabConfig[]): LabConfig {
  const names = new Set(configs.map((c) => c.name));
  let n = configs.length + 1;
  while (names.has(`Config ${String(n)}`)) n += 1;
  const { stopPct, atrK, atrN, targetPct, trailPct, maN, maKind, timeBars } = DEFAULT_INPUTS;
  const exits = { stopPct, atrK, atrN, targetPct, trailPct, maN, maKind, timeBars };
  return { ...exits, id: nextConfigId(), name: `Config ${String(n)}` };
}

export function LabConfigs({ configs, onChange, errors }: LabConfigsProps) {
  const addRef = useRef<HTMLButtonElement>(null);
  const update = (id: number, patch: Partial<LabConfig>) =>
    onChange(configs.map((c) => (c.id === id ? { ...c, ...patch } : c)));
  const remove = (id: number) => {
    onChange(configs.filter((c) => c.id !== id));
    addRef.current?.focus();
  };

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Every config trades the same entries, so the exit is the only thing that changes between
        rows. Use {formatInt(MIN_CONFIGS)} to {formatInt(MAX_CONFIGS)} configs.
      </p>
      {configs.map((config, i) => {
        const own = errors[i] ?? {};
        const title = `Config ${String(i + 1)}${i === 0 ? " (baseline)" : ""}`;
        return (
          <FieldSet key={config.id} className="min-w-0 gap-4 rounded-lg border p-4">
            <FieldLegend>{title}</FieldLegend>
            {own.config && <p className="text-sm break-words text-destructive">{own.config}</p>}
            <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start">
              <Field invalid={Boolean(own.name)} className="min-w-0 sm:max-w-sm">
                <FieldLabel>Name</FieldLabel>
                <Input
                  value={config.name}
                  maxLength={40}
                  onChange={(e) => update(config.id, { name: e.target.value })}
                />
                <FieldError>{own.name}</FieldError>
              </Field>
              <Button
                type="button"
                variant="outline"
                className="sm:mt-6"
                disabled={configs.length <= MIN_CONFIGS}
                aria-label={`Remove ${title}`}
                onClick={() => remove(config.id)}
              >
                Remove
              </Button>
            </div>
            <ExitFields
              value={config}
              onChange={(patch) => update(config.id, patch)}
              errors={own}
            />
          </FieldSet>
        );
      })}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          ref={addRef}
          type="button"
          variant="outline"
          disabled={configs.length >= MAX_CONFIGS}
          onClick={() => onChange([...configs, newConfig(configs)])}
        >
          Add config
        </Button>
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {formatInt(configs.length)} of {formatInt(MAX_CONFIGS)} configs
        </p>
      </div>
    </div>
  );
}
