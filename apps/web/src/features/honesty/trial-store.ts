// The structure keyed trial counter (U-4, doc 02 §7.5, spec 0004). The keys come from the
// backtest response (spec 0002); the browser never hashes anything. Each distinct pair key adds
// one to its structure key's count in localStorage; a separate set in sessionStorage gives the
// session total. Recording is idempotent, so a repeated render never double counts.
import type { Schemas } from "@swing-scan/api-client";

export type Trial = Schemas["Trial"];

/** At this many trials for one rule structure, the overfit warning shows (U-4). */
export const TRIAL_WARNING_AT = 10;

export const TRIAL_KEY_PREFIX = "swing-scan:trials:v1:";
export const SESSION_KEY = "swing-scan:session-trials:v1";

/**
 * The dataset ends a structure key's trials were counted on (spec 0013 AC-10). A **sibling** of
 * `TRIAL_KEY_PREFIX`, never a field inside it: `readSet` treats a non array value as empty and
 * overwrites it, so folding this into the existing array would wipe every count ever recorded.
 */
export const TRIAL_DATA_KEY_PREFIX = "swing-scan:trial-data:v1:";

/** What the counter shows after a run: N for the rule structure, M for the session. */
export interface TrialCount {
  trialNumber: number;
  sessionTotal: number;
}

/** The two stores, injectable for tests. Each getter may throw when storage is blocked. */
export interface TrialStores {
  local: () => Storage;
  session: () => Storage;
}

export const browserStores: TrialStores = {
  local: () => window.localStorage,
  session: () => window.sessionStorage,
};

function readSet(storage: Storage, key: string): string[] {
  const raw = storage.getItem(key);
  if (raw === null) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    // A value that does not parse as a string list is treated as empty and overwritten.
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

/** Returns the stored set in insertion order, so what was there first stays first (AC-10). */
function addAll(storage: Storage, key: string, items: readonly string[]): string[] {
  const seen = readSet(storage, key);
  const set = new Set(seen);
  for (const item of items) set.add(item);
  const all = [...set];
  if (all.length !== seen.length) storage.setItem(key, JSON.stringify(all));
  return all;
}

/**
 * Records a completed run's pairs and returns the new counts, or `null` when either storage is
 * unavailable (the caller then hides the counters and shows the static warning).
 */
export function recordTrial(trial: Trial, stores: TrialStores = browserStores): TrialCount | null {
  try {
    const local = stores.local();
    const session = stores.session();
    const trials = addAll(local, TRIAL_KEY_PREFIX + trial.structure_key, trial.pair_keys);
    const sessionTotal = addAll(session, SESSION_KEY, trial.pair_keys);
    return { trialNumber: trials.length, sessionTotal: sessionTotal.length };
  } catch {
    return null;
  }
}

/**
 * Adds the dataset this run was computed on to its structure key's sibling key and returns every
 * dataset seen for it, oldest first (spec 0013 AC-10). `dataEnd` comes from the result being
 * recorded (`assumptions.data_end`).
 *
 * Deliberately separate from `recordTrial`: the count arrays are never read or rewritten here,
 * so a dataset change cannot cost a single count. An empty pair list records nothing, exactly as
 * `recordTrial` does. Returns `[]` when storage is blocked, which only hides the dataset
 * sentence; `recordTrial` has already reported the storage failure by then.
 */
export function recordTrialData(
  trial: Trial,
  dataEnd: string,
  stores: TrialStores = browserStores,
): string[] {
  try {
    const key = TRIAL_DATA_KEY_PREFIX + trial.structure_key;
    return addAll(stores.local(), key, trial.pair_keys.length > 0 ? [dataEnd] : []);
  } catch {
    return [];
  }
}

/** True when the count reaches the overfit warning threshold (U-4). */
export function isOverTrialLimit(count: TrialCount): boolean {
  return count.trialNumber >= TRIAL_WARNING_AT;
}
