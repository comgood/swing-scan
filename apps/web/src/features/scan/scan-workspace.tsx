"use client";

// The template workspace on `/` (spec 0005 AC-9 to AC-12): pick a template, read its
// conditions, see today's hits. Templates come only from `GET /templates`; nothing here hard
// codes one. The selection lives in `?template`, read inside `Suspense` for the static export.
import type { TemplateOut } from "@swing-scan/api-client";
import { Suspense, useEffect, useMemo } from "react";

import { ErrorState } from "@/components/error-state";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { WarmupNotice } from "@/components/warmup-notice";
import { ApiRequestError, type ApiError } from "@/lib/api-error";
import { formatDate } from "@/lib/format";

import { operandColumns } from "./operands";
import { useScan, useTemplates } from "./queries";
import { ResultsTable } from "./results-table";
import { TemplateConditions } from "./template-conditions";
import { useTemplateParam } from "./use-template-param";

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

function apiErrorOf(error: Error): ApiError {
  return error instanceof ApiRequestError ? error.apiError : { kind: "network" };
}

function WorkspaceSkeleton() {
  return (
    <div className="flex min-w-0 flex-col gap-8">
      <p role="status" className="sr-only">
        Loading templates…
      </p>
      <div className="flex max-w-md flex-col gap-2">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-9 w-full" />
      </div>
      <div className="flex flex-col gap-2">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-4 w-full max-w-sm" />
        <Skeleton className="h-4 w-full max-w-xs" />
      </div>
      <Skeleton className="h-48 w-full" />
    </div>
  );
}

function ScanResults({ template }: { template: TemplateOut }) {
  const scan = useScan(template.rule);
  const operands = useMemo(() => operandColumns(template.rule), [template.rule]);

  return (
    <section aria-labelledby="scan-hits" className="flex min-w-0 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <h2 id="scan-hits" className="text-lg font-semibold">
          {scan.data ? `Hits on ${formatDate(scan.data.as_of)}` : "Hits"}
        </h2>
        <WarmupNotice pending={scan.isPending} />
      </div>
      {scan.isError ? (
        <ErrorState
          error={apiErrorOf(scan.error)}
          onRetry={() => void scan.refetch()}
          headingLevel={3}
        />
      ) : scan.data ? (
        <ResultsTable
          key={template.id}
          result={scan.data}
          operands={operands}
          caption={`${template.name}: hits`}
        />
      ) : (
        <Skeleton className="h-48 w-full" />
      )}
    </section>
  );
}

function Workspace() {
  const templates = useTemplates();
  const [param, setParam] = useTemplateParam();
  const template = templates.data ? pickTemplate(templates.data, param) : undefined;

  // An unknown id opens Breakout and drops the parameter, once the list is known.
  const unknown =
    templates.data !== undefined && param !== null && !templates.data.some((t) => t.id === param);
  useEffect(() => {
    if (unknown) setParam(null);
  }, [unknown, setParam]);

  if (templates.isError) {
    return (
      <ErrorState error={apiErrorOf(templates.error)} onRetry={() => void templates.refetch()} />
    );
  }
  if (!templates.data || !template) return <WorkspaceSkeleton />;

  return (
    <div className="flex min-w-0 flex-col gap-8">
      <Field className="max-w-md">
        <FieldLabel>Template</FieldLabel>
        <NativeSelect
          value={template.id}
          onChange={(e) => setParam(e.target.value === DEFAULT_TEMPLATE_ID ? null : e.target.value)}
        >
          {templates.data.map((t) => (
            <NativeSelectOption key={t.id} value={t.id}>
              {t.name}
            </NativeSelectOption>
          ))}
        </NativeSelect>
        <FieldDescription>{template.description}</FieldDescription>
      </Field>
      <TemplateConditions rule={template.rule} />
      <ScanResults template={template} />
    </div>
  );
}

export function ScanWorkspace() {
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <h1 className="text-2xl font-semibold">Template scan</h1>
      <Suspense fallback={<WorkspaceSkeleton />}>
        <Workspace />
      </Suspense>
    </div>
  );
}
