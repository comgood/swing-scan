"use client";

// The trial counter line and the overfit warning (U-4, doc 02 §7.5, spec 0004).
// `TrialCounter` is presentational, so the /ui gallery can show every state; `RunTrialCounter`
// records a completed run and is what the report (feature 9) and exit lab (feature 12) place.
// The copy is fixed by doc 01 U-4 and stays word for word.
import { Banner } from "@/components/banner";
import { formatInt } from "@/lib/format";
import { cn } from "@/lib/utils";

import { isOverTrialLimit, type Trial, type TrialStores } from "./trial-store";
import { useTrialCount, type TrialCountState } from "./use-trial-count";

export const OVERFIT_WARNING =
  "You've tested many variants of this rule structure; the best IS result is likely overfit. Read OOS once and treat the result as a hypothesis.";

export function trialCounterText(trialNumber: number, sessionTotal: number): string {
  return `Trial #${formatInt(trialNumber)} for this rule structure · ${formatInt(sessionTotal)} this session`;
}

interface TrialCounterProps {
  state: TrialCountState;
  className?: string;
}

export function TrialCounter({ state, className }: TrialCounterProps) {
  const counted = state.status === "counted" ? state.count : null;
  const warn = state.status === "unavailable" || (counted !== null && isOverTrialLimit(counted));
  return (
    <div data-slot="trial-counter" className={cn("flex min-w-0 flex-col gap-3", className)}>
      {/* Always in the DOM, so a new count after a re run is announced politely. */}
      <p role="status" aria-live="polite" className="text-sm break-words tabular-nums">
        {counted && trialCounterText(counted.trialNumber, counted.sessionTotal)}
      </p>
      {warn && <Banner variant="warning">{OVERFIT_WARNING}</Banner>}
    </div>
  );
}

interface RunTrialCounterProps {
  /** `trial` from a 200 backtest response (portfolio or exit lab). */
  trial: Trial;
  className?: string;
  /** Injected storage for tests and the gallery; the browser stores by default. */
  stores?: TrialStores;
}

/** Records this run's pairs once and shows the counter. Mount it only for a completed run. */
export function RunTrialCounter({ trial, className, stores }: RunTrialCounterProps) {
  const state = useTrialCount(trial, stores);
  return <TrialCounter state={state} className={className} />;
}
