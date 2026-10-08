"use client";

// The assumptions header (U-3, spec 0007 AC-12) with the trial counter beside it (AC-16, U-4).
// Honesty copy is never collapsed or styled as fine print (design.md).
import { RunTrialCounter, type TrialStores } from "@/features/honesty";

import { assumptionLines } from "./assumption-labels";
import type { PortfolioResult } from "./queries";

interface AssumptionsHeaderProps {
  result: PortfolioResult;
  /** Injected trial storage for tests; the browser stores by default. */
  stores?: TrialStores;
}

export function AssumptionsHeader({ result, stores }: AssumptionsHeaderProps) {
  return (
    <section
      aria-labelledby="assumptions-title"
      className="flex min-w-0 flex-col gap-4 rounded-lg border bg-card p-4"
    >
      <div className="flex min-w-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <h2 id="assumptions-title" className="text-lg font-semibold">
          Assumptions
        </h2>
        <RunTrialCounter trial={result.trial} stores={stores} className="md:max-w-md" />
      </div>
      <dl className="grid min-w-0 grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
        {assumptionLines(result.assumptions).map((line) => (
          <div key={line.key} className="min-w-0">
            <dt className="text-muted-foreground">{line.label}</dt>
            <dd className="break-words">{line.text}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
