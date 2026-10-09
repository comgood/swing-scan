"use client";

// The single config backtest report on `/backtest` (spec 0007, FE tasks 5 and 6). Inputs come
// from the URL and go back into it on submit; the run starts only when you press "Run
// backtest", so reloading a shared link never records a trial on its own. A `?r=` link from the
// rule builder (spec 0008 decision 12) is checked against the indicator catalog; one that does
// not decode falls back to the template with a notice.
import type { BacktestRequest } from "@swing-scan/api-client";
import { useMemo, useState } from "react";

import { Banner } from "@/components/banner";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { FormErrorSummary } from "@/components/form-error-summary";
import { Skeleton } from "@/components/ui/skeleton";
import { WarmupNotice } from "@/components/warmup-notice";
import { decodeRule } from "@/features/rule-builder";
import { pickTemplate } from "@/features/scan";
import type { TrialStores } from "@/features/honesty";
import { ApiRequestError } from "@/lib/api-error";

import { AssumptionsHeader } from "./assumptions-header";
import { BacktestForm } from "./backtest-form";
import { EquityChart } from "./equity-chart";
import { inputsFromParams, paramsFromInputs, placeErrors, requestFrom } from "./inputs";
import { MetricsTable } from "./metrics-table";
import {
  useBacktest,
  useIndicators,
  useTemplates,
  ValidationFailed,
  type PortfolioResult,
} from "./queries";
import { TradeList } from "./trade-list";

export const BAD_RULE_LINK = "This link's rule could not be read. Pick a template instead.";

interface BacktestReportProps {
  /** The page's search params at load. */
  initialParams: URLSearchParams;
  /** Injected trial storage for tests; the browser stores by default. */
  stores?: TrialStores;
}

export function BacktestReport({ initialParams, stores }: BacktestReportProps) {
  const [opened] = useState(() => inputsFromParams(initialParams));
  const templates = useTemplates();
  const indicators = useIndicators(opened.r !== null);
  const backtest = useBacktest();
  const [inputs, setInputs] = useState(opened);
  const [sent, setSent] = useState(inputs);

  const linkRule = useMemo(
    () =>
      opened.r !== null && indicators.data
        ? decodeRule(
            opened.r,
            indicators.data.map((s) => s.name),
          )
        : null,
    [opened.r, indicators.data],
  );
  const link = linkRule && opened.r !== null ? { r: opened.r, name: linkRule.name } : null;
  const badLink = opened.r !== null && indicators.data !== undefined && linkRule === null;
  const catalogReady = opened.r === null || indicators.data !== undefined;

  const run = (body: BacktestRequest) => backtest.mutate(body);
  const submit = () => {
    const useLink = link !== null && linkRule !== null && inputs.r !== null;
    const template = templates.data && pickTemplate(templates.data, inputs.template);
    if (!template) return;
    const next = { ...inputs, template: template.id, r: useLink ? link.r : null };
    setInputs(next);
    setSent(next);
    window.history.replaceState(null, "", `?${paramsFromInputs(next).toString()}`);
    run(requestFrom(next, useLink ? linkRule : template.rule));
  };

  const invalid = backtest.error instanceof ValidationFailed ? backtest.error : null;
  const placed = invalid ? placeErrors(invalid.errors, sent) : { fields: {}, form: [] };
  const failed = backtest.error instanceof ApiRequestError ? backtest.error.apiError : null;
  const loading = templates.isPending || (opened.r !== null && indicators.isPending);

  return (
    <div className="flex min-w-0 flex-col gap-8">
      <section aria-labelledby="backtest-title" className="flex min-w-0 flex-col gap-4">
        <h1 id="backtest-title" className="text-2xl font-semibold">
          Backtest
        </h1>
        <WarmupNotice pending={loading || backtest.isPending} />
        {badLink && <Banner variant="info">{BAD_RULE_LINK}</Banner>}
        {loading && (
          <>
            <p role="status" className="sr-only">
              Loading templates…
            </p>
            <Skeleton className="h-40 w-full" />
          </>
        )}
        {templates.error instanceof ApiRequestError && (
          <ErrorState error={templates.error.apiError} onRetry={() => void templates.refetch()} />
        )}
        {indicators.error instanceof ApiRequestError && (
          <ErrorState error={indicators.error.apiError} onRetry={() => void indicators.refetch()} />
        )}
        {templates.data && catalogReady && (
          <BacktestForm
            templates={templates.data}
            inputs={inputs}
            onChange={setInputs}
            onSubmit={submit}
            running={backtest.isPending}
            errors={placed.fields}
            link={link}
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
      {backtest.isPending && <ReportSkeleton />}
      {backtest.data && <Report result={backtest.data} stores={stores} />}
    </div>
  );
}

function ReportSkeleton() {
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <p role="status" className="sr-only">
        Running the backtest…
      </p>
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-48 w-full" />
      <Skeleton className="h-64 w-full" />
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
        <>
          <section aria-labelledby="metrics-title" className="flex min-w-0 flex-col gap-3">
            <h2 id="metrics-title" className="text-lg font-semibold">
              Results
            </h2>
            <MetricsTable result={result} />
          </section>
          <section aria-labelledby="equity-title" className="flex min-w-0 flex-col gap-3">
            <h2 id="equity-title" className="text-lg font-semibold">
              Equity
            </h2>
            <EquityChart
              equity={result.equity}
              benchmark={result.benchmark}
              oosStart={result.oos_start}
            />
          </section>
          <section aria-labelledby="trades-title" className="flex min-w-0 flex-col gap-3">
            <h2 id="trades-title" className="text-lg font-semibold">
              Trades
            </h2>
            <TradeList
              trades={result.trades}
              total={result.trades_total}
              truncated={result.trades_truncated}
              oosStart={result.oos_start}
            />
          </section>
        </>
      )}
    </>
  );
}
