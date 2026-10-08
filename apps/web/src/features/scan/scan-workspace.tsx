"use client";

// The scan workspace on `/` (spec 0005 AC-9 to AC-12, spec 0008): pick a template or edit the
// rule builder, see today's hits. Templates come only from `GET /templates`; nothing here hard
// codes one. The rule lives in the link (`?template` or `?r`), read inside `Suspense` for the
// static export. A loaded rule scans at once; an edit waits for "Run scan" (spec 0008 AC-8).
import type { IndicatorSpec, Rule, ScanResponse, TemplateOut } from "@swing-scan/api-client";
import { hashKey } from "@tanstack/react-query";
import { Suspense, useEffect, useMemo, useReducer, useState } from "react";

import { Banner } from "@/components/banner";
import { ErrorState } from "@/components/error-state";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { WarmupNotice } from "@/components/warmup-notice";
import {
  BAD_LINK_NOTICE,
  builderReducer,
  decodeRule,
  encodeRule,
  initBuilder,
  RuleBuilder,
  STALE_TEXT,
  type BuilderState,
} from "@/features/rule-builder";
import { ApiRequestError, type ApiError } from "@/lib/api-error";
import { formatDate } from "@/lib/format";

import { operandColumns } from "./operands";
import { RuleRejectedError, useIndicators, useScan, useTemplates } from "./queries";
import { ResultsTable } from "./results-table";
import { useRuleLink, type RuleLink } from "./use-rule-link";

/** The template a first visit opens on (spec 0005 value sourcing). */
export const DEFAULT_TEMPLATE_ID = "breakout_52w";

/** URL writes after an edit wait this long, so typing does not rewrite the link per key. */
export const LINK_DEBOUNCE_MS = 300;

export const REJECTED_TEXT = "The rule was rejected. Fix the marked fields and run the scan again.";

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

/** The link for a template: Breakout has no parameter (spec 0008 AC-2). */
function templateLink(id: string): RuleLink {
  return { template: id === DEFAULT_TEMPLATE_ID ? null : id, r: null };
}

interface Opening {
  state: BuilderState;
  /** The link to write once on open: a bad `?r` or unknown `?template` is dropped. */
  fix: RuleLink | null;
  badLink: boolean;
}

/** What a link opens: a readable `?r`, else the named template, else Breakout (AC-2, AC-3). */
export function openLink(
  link: RuleLink,
  templates: TemplateOut[],
  catalog: readonly IndicatorSpec[],
): Opening | null {
  if (link.r !== null) {
    const rule = decodeRule(
      link.r,
      catalog.map((s) => s.name),
    );
    if (rule) {
      return {
        state: initBuilder(rule, "custom"),
        fix: link.template === null ? null : { template: null, r: link.r },
        badLink: false,
      };
    }
  }
  const template = pickTemplate(templates, link.r === null ? link.template : null);
  if (!template) return null;
  const wanted = templateLink(template.id);
  const fix = wanted.template === link.template && link.r === null ? null : wanted;
  return { state: initBuilder(template.rule, { template: template.id }), fix, badLink: !!link.r };
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

interface ShownResult {
  data: ScanResponse;
  rule: Rule;
}

function Editor({
  templates,
  catalog,
  opening,
  setLink,
}: {
  templates: TemplateOut[];
  catalog: IndicatorSpec[];
  opening: Opening;
  setLink: (link: RuleLink) => void;
}) {
  const [state, dispatch] = useReducer(builderReducer, opening.state);
  const [ranRule, setRanRule] = useState<Rule>(opening.state.rule);
  const [badLink, setBadLink] = useState(opening.badLink);
  const scan = useScan(ranRule);
  const [shown, setShown] = useState<ShownResult | null>(null);
  // Results stay on screen until the next answer, so a 422 or a pending run keeps them (stale).
  if (scan.data && scan.data !== shown?.data) setShown({ data: scan.data, rule: ranRule });

  const { fix } = opening;
  useEffect(() => {
    if (fix) setLink(fix);
  }, [fix, setLink]);

  // After an edit the link is `?r` for good; written after a pause in typing (decision 3).
  const { rule, source } = state;
  useEffect(() => {
    if (source !== "custom") return;
    const timer = setTimeout(
      () => setLink({ template: null, r: encodeRule(rule) }),
      LINK_DEBOUNCE_MS,
    );
    return () => clearTimeout(timer);
  }, [rule, source, setLink]);

  const run = (next: Rule) => {
    if (hashKey([next]) === hashKey([ranRule])) void scan.refetch();
    else setRanRule(next);
  };

  const pickTemplateId = (id: string) => {
    const template = templates.find((t) => t.id === id);
    if (!template) return;
    dispatch({ type: "load", rule: template.rule, source: { template: id } });
    setLink(templateLink(id));
    setBadLink(false);
    run(template.rule);
  };

  const rejected = scan.error instanceof RuleRejectedError ? scan.error : null;
  // A 422 names rows by index, so it only marks rows while the row count still matches.
  const fieldErrors =
    rejected && ranRule.conditions.length === state.rule.conditions.length
      ? rejected.fieldErrors
      : undefined;
  const stale = shown !== null && (state.dirty || hashKey([shown.rule]) !== hashKey([ranRule]));
  const template =
    typeof source === "object" ? templates.find((t) => t.id === source.template) : undefined;
  const operands = useMemo(() => (shown ? operandColumns(shown.rule) : []), [shown]);
  const backtestHref = `/backtest?${new URLSearchParams({
    ...(template ? { template: template.id } : {}),
    r: encodeRule(state.rule),
  }).toString()}`;

  return (
    <div className="flex min-w-0 flex-col gap-8">
      {badLink && <Banner variant="info">{BAD_LINK_NOTICE}</Banner>}
      <Field className="max-w-md">
        <FieldLabel>Template</FieldLabel>
        <NativeSelect value={template?.id ?? ""} onChange={(e) => pickTemplateId(e.target.value)}>
          {!template && (
            <NativeSelectOption value="" disabled>
              Your own rule
            </NativeSelectOption>
          )}
          {templates.map((t) => (
            <NativeSelectOption key={t.id} value={t.id}>
              {t.name}
            </NativeSelectOption>
          ))}
        </NativeSelect>
        <FieldDescription>
          {template ? template.description : "Edited from a template. Pick one to start over."}
        </FieldDescription>
      </Field>
      <RuleBuilder
        state={state}
        dispatch={dispatch}
        catalog={catalog}
        errors={fieldErrors}
        running={scan.isFetching}
        backtestHref={backtestHref}
        onRun={() => {
          dispatch({ type: "ran" });
          run(state.rule);
        }}
      />
      <section aria-labelledby="scan-hits" className="flex min-w-0 flex-col gap-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <h2 id="scan-hits" className="text-lg font-semibold">
            {shown ? `Hits on ${formatDate(shown.data.as_of)}` : "Hits"}
          </h2>
          <WarmupNotice pending={scan.isFetching} />
        </div>
        {stale && (
          <p role="status" className="text-sm text-muted-foreground">
            {STALE_TEXT}
          </p>
        )}
        {rejected
          ? !shown && <p className="text-sm text-muted-foreground">{REJECTED_TEXT}</p>
          : scan.isError && (
              <ErrorState
                error={apiErrorOf(scan.error)}
                onRetry={() => void scan.refetch()}
                headingLevel={3}
              />
            )}
        {shown ? (
          <ResultsTable
            key={hashKey([shown.rule])}
            result={shown.data}
            operands={operands}
            caption={`${shown.rule.name}: hits`}
          />
        ) : (
          !scan.isError && <Skeleton className="h-48 w-full" />
        )}
      </section>
    </div>
  );
}

function Workspace() {
  const templates = useTemplates();
  const catalog = useIndicators();
  const [link, setLink] = useRuleLink();
  // The link is read once, when the templates and the catalog are in (spec 0005 AC-10 gate).
  const [opening, setOpening] = useState<Opening | null>(null);
  if (!opening && templates.data && catalog.data) {
    const opened = openLink(link, templates.data, catalog.data);
    if (opened) setOpening(opened);
  }

  const failed = templates.isError ? templates : catalog.isError ? catalog : null;
  if (failed?.error) {
    return <ErrorState error={apiErrorOf(failed.error)} onRetry={() => void failed.refetch()} />;
  }
  if (!opening || !templates.data || !catalog.data) return <WorkspaceSkeleton />;
  return (
    <Editor templates={templates.data} catalog={catalog.data} opening={opening} setLink={setLink} />
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
