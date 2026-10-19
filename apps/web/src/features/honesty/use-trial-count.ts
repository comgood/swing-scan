"use client";

// Records a completed run's trial keys once it is on screen and returns what the counter shows
// (U-4, spec 0004). Storage is touched only in the browser, after mount, so the static HTML
// never depends on it (the server snapshot is always "pending"). The effect writes to storage
// and caches the result per run; components read that cache through useSyncExternalStore.
// Recording is idempotent, so strict mode's double effect and a re run of the same pairs
// count once.
import { useCallback, useEffect, useSyncExternalStore } from "react";

import {
  browserStores,
  recordTrial,
  recordTrialData,
  type Trial,
  type TrialCount,
  type TrialStores,
} from "./trial-store";

export type TrialCountState =
  | { status: "pending" }
  | {
      status: "counted";
      count: TrialCount;
      /** Every dataset these trials ran on, oldest first (spec 0013 AC-10). */
      dataEnds: string[];
    }
  | { status: "unavailable" };

const PENDING: TrialCountState = { status: "pending" };

/** Results per stores object, then per run, so injected test stores never share a cache. */
const results = new WeakMap<TrialStores, Map<string, TrialCountState>>();
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function cacheFor(stores: TrialStores): Map<string, TrialCountState> {
  let cache = results.get(stores);
  if (!cache) {
    cache = new Map();
    results.set(stores, cache);
  }
  return cache;
}

function runId(trial: Trial, dataEnd: string | undefined): string {
  // The dataset is part of the run: the same pairs on a newer dataset record again, which is how
  // the warning comes to name both datasets (spec 0013 AC-10).
  return `${trial.structure_key}|${trial.pair_keys.join(",")}|${dataEnd ?? ""}`;
}

/** `stores` must be a stable object (module level); a new one each render would loop. */
export function useTrialCount(
  trial: Trial,
  dataEnd?: string,
  stores: TrialStores = browserStores,
): TrialCountState {
  const id = runId(trial, dataEnd);
  const getSnapshot = useCallback(() => cacheFor(stores).get(id) ?? PENDING, [stores, id]);
  const state = useSyncExternalStore(subscribe, getSnapshot, () => PENDING);

  useEffect(() => {
    // Always record on mount: an identical re run adds nothing but shows the current totals.
    const count = recordTrial(trial, stores);
    cacheFor(stores).set(
      id,
      count
        ? {
            status: "counted",
            count,
            dataEnds: dataEnd === undefined ? [] : recordTrialData(trial, dataEnd, stores),
          }
        : { status: "unavailable" },
    );
    for (const listener of listeners) listener();
    // `id` captures all of `trial` and `dataEnd` that matters; a new object for the same run
    // is a no op.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, stores]);

  return state;
}
