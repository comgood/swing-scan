"use client";

// The single config backtest report on `/backtest` (spec 0007, FE tasks 5 and 6). Inputs come
// from the URL and go back into it on submit; the run starts only when you press "Run
// backtest", so reloading a shared link never records a trial on its own.
import type { BacktestRequest } from "@swing-scan/api-client";
import { useState } from "react";

import { Banner } from "@/components/banner";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { FormErrorSummary } from "@/components/form-error-summary";
import { Skeleton } from "@/components/ui/skeleton";
import { WarmupNotice } from "@/components/warmup-notice";
import { pickTemplate } from "@/features/scan";
import type { TrialStores } from "@/features/honesty";
import { ApiRequestError } from "@/lib/api-error";

import { AssumptionsHeader } from "./assumptions-header";
import { BacktestForm } from "./backtest-form";
import { inputsFromParams, paramsFromInputs, placeErrors, requestFrom } from "./inputs";
import { MetricsTable } from "./metrics-table";
import { useBacktest, useTemplates, ValidationFailed, type PortfolioResult } from "./queries";

interface BacktestReportProps {
  /** The page's search params at load. */
  initialParams: URLSearchParams;
  /** Injected trial storage for tests; the browser stores by default. */
  stores?: TrialStores;
}

export function BacktestReport({ initialParams, stores }: BacktestReportProps) {
  const templates = useTemplates();
  const backtest = useBacktest();
  const [inputs, setInputs] = useState(() => inputsFromParams(initialParams));
  const [sent, setSent] = useState(inputs);

  const run = (body: BacktestRequest) => backtest.mutate(body);
  const submit = () => {
    const template = templates.data && pickTemplate(templates.data, inputs.template);
    if (!template) return;
    const next = { ...inputs, template: template.id };
    setInputs(next);
    setSent(next);
    window.history.replaceState(null, "", `?${paramsFromInputs(next).toString()}`);
    run(requestFrom(next, template.rule));
  };

  const invalid = backtest.error instanceof ValidationFailed ? backtest.error : null;
  const placed = invalid ? placeErrors(invalid.errors, sent) : { fields: {}, form: [] };
  const failed = backtest.error instanceof ApiRequestError ? backtest.error.apiError : null;

  return (
    <div className="flex min-w-0 flex-col gap-8">
      <section aria-labelledby="backtest-title" className="flex min-w-0 flex-col gap-4">
        <h1 id="backtest-title" className="text-2xl font-semibold">
          Backtest
        </h1>
        <WarmupNotice pending={templates.isPending || backtest.isPending} />
        {templates.isPending && <Skeleton className="h-40 w-full" />}
        {templates.error instanceof ApiRequestError && (
          <ErrorState error={templates.error.apiError} onRetry={() => void templates.refetch()} />
        )}
        {templates.data && (
          <BacktestForm
            templates={templates.data}
            inputs={inputs}
            onChange={setInputs}
            onSubmit={submit}
            running={backtest.isPending}
            errors={placed.fields}
          />
        )}
        <FormErrorSummary errors={placed.form} />
        {failed && (
          <ErrorState
            error={failed}
            onRetry={backtest.variables ? () => run(backtest.variables) : undefined}
          />
        )}
      </section>
      {backtest.data && <Report result={backtest.data} stores={stores} />}
    </div>
  );
}

function Report({ result, stores }: { result: PortfolioResult; stores?: TrialStores }) {
  const noEntries = result.warnings.find((w) => w.code === "no_entries");
  const others = result.warnings.filter((w) => w.code !== "no_entries");
  return (
    <>
      <AssumptionsHeader result={result} stores={stores} />
      {others.map((w) => (
        <Banner key={w.code} variant="info">
          {w.message}
        </Banner>
      ))}
      {noEntries ? (
        <EmptyState title="No trades" hint={noEntries.message} />
      ) : (
        <section aria-labelledby="metrics-title" className="flex min-w-0 flex-col gap-3">
          <h2 id="metrics-title" className="text-lg font-semibold">
            Results
          </h2>
          <MetricsTable result={result} />
        </section>
      )}
    </>
  );
}
