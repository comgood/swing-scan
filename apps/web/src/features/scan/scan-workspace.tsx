"use client";

// The template workspace on `/` (spec 0005 AC-9): pick a template, read its conditions, see
// today's hits. Templates come only from `GET /templates`; nothing here hard codes one.
import type { TemplateOut } from "@swing-scan/api-client";
import { useState } from "react";

import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { formatDate } from "@/lib/format";

import { useScan, useTemplates } from "./queries";
import { ResultsTable } from "./results-table";
import { TemplateConditions } from "./template-conditions";

/** The template a first visit opens on (spec 0005 value sourcing). */
export const DEFAULT_TEMPLATE_ID = "breakout_52w";

/** The requested template, else Breakout, else the first one the API lists. */
export function pickTemplate(
  templates: TemplateOut[],
  id: string | null | undefined,
): TemplateOut | undefined {
  return (
    templates.find((t) => t.id === id) ??
    templates.find((t) => t.id === DEFAULT_TEMPLATE_ID) ??
    templates[0]
  );
}

export function ScanWorkspace() {
  const templates = useTemplates();
  const [selectedId, setSelectedId] = useState<string>(DEFAULT_TEMPLATE_ID);
  const template = templates.data ? pickTemplate(templates.data, selectedId) : undefined;
  const scan = useScan(template?.rule);

  return (
    <div className="flex min-w-0 flex-col gap-8">
      <section aria-labelledby="scan-title" className="flex min-w-0 flex-col gap-4">
        <h1 id="scan-title" className="text-2xl font-semibold">
          Template scan
        </h1>
        {templates.data && template && (
          <Field className="max-w-md">
            <FieldLabel>Template</FieldLabel>
            <NativeSelect value={template.id} onChange={(e) => setSelectedId(e.target.value)}>
              {templates.data.map((t) => (
                <NativeSelectOption key={t.id} value={t.id}>
                  {t.name}
                </NativeSelectOption>
              ))}
            </NativeSelect>
            <FieldDescription>{template.description}</FieldDescription>
          </Field>
        )}
      </section>

      {template && <TemplateConditions rule={template.rule} />}

      {template && scan.data && (
        <section aria-labelledby="scan-hits" className="flex min-w-0 flex-col gap-3">
          <h2 id="scan-hits" className="text-lg font-semibold">
            Hits on {formatDate(scan.data.as_of)}
          </h2>
          <ResultsTable result={scan.data} caption={`${template.name}: hits`} />
        </section>
      )}
    </div>
  );
}
