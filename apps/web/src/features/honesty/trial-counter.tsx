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

/**
 * Names the datasets the counted trials ran on, oldest first (spec 0013 AC-10). A separate
 * sentence after `OVERFIT_WARNING`, which doc 01 U-4 fixes word for word. When a count spans two
 * datasets it says so: the point of the counter is that you tried many variants, and hiding that
 * the data moved under them would defeat it.
 */
export function trialDataText(dataEnds: readonly string[]): string {
  if (dataEnds.length === 0) return "";
  if (dataEnds.length === 1) return `Those trials ran on data as of ${dataEnds[0]}.`;
  return `Those trials ran on more than one dataset: data as of ${new Intl.ListFormat(
    "en-US",
  ).format(dataEnds)}.`;
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
      {warn && (
        <Banner variant="warning">
          {/* Each sentence is its own element: U-4 fixes this copy word for word, so it stays a
              node of exactly that text rather than merging with the dataset sentence. */}
          <span>{OVERFIT_WARNING}</span>
          {state.status === "counted" && state.dataEnds.length > 0 && (
            <span> {trialDataText(state.dataEnds)}</span>
          )}
        </Banner>
      )}
    </div>
  );
}

interface RunTrialCounterProps {
  /** `trial` from a 200 backtest response (portfolio or exit lab). */
  trial: Trial;
  /**
   * `assumptions.data_end` from the same result: the dataset it was computed on (AC-10). Every
   * caller holding a result passes it. It is optional only because a caller without one still
   * shows the counter (QA's U-4 acceptance tests, which the builder lanes never edit), and a
   * missing dataset simply leaves the warning's dataset sentence off.
   */
  dataEnd?: string;
  className?: string;
  /** Injected storage for tests and the gallery; the browser stores by default. */
  stores?: TrialStores;
}

/** Records this run's pairs once and shows the counter. Mount it only for a completed run. */
export function RunTrialCounter({ trial, dataEnd, className, stores }: RunTrialCounterProps) {
  const state = useTrialCount(trial, dataEnd, stores);
  return <TrialCounter state={state} className={className} />;
}
