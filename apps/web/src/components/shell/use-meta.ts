"use client";

// The dataset poll (spec 0013): the site notices by itself when the writer appends a trading
// day, by asking the existing meta endpoint on an interval. There is no server push, because a
// held open stream on Lambda is billed for every second it stays open (spec 0013, Decision).
// A failure here is never shown: this is a background convenience, and an error surface for it
// would train people to ignore real errors (AC-7).
import type { MetaResponse } from "@swing-scan/api-client";
import { useQuery } from "@tanstack/react-query";

import { ApiRequestError, toApiError } from "@/lib/api-error";
import { api } from "@/lib/api";

import { useHealth } from "./use-health";

/** How often a visible tab asks whether the dataset moved (AC-1). */
export const META_POLL_MS = 30_000;

/**
 * Must stay finite and below the interval: `refetchOnWindowFocus` fires only on a stale query,
 * so an infinite `staleTime`, which is what `useHealth` uses, would never check on refocus (AC-6).
 */
export const META_STALE_MS = 10_000;

/** A hung poll would stall every later one, since no refetch starts while one is in flight. */
export const META_TIMEOUT_MS = 10_000;

async function fetchMeta({ signal }: { signal: AbortSignal }): Promise<MetaResponse> {
  const timeout = AbortSignal.timeout(META_TIMEOUT_MS);
  let result;
  try {
    result = await api.GET("/api/v1/meta", { signal: AbortSignal.any([signal, timeout]) });
  } catch (error) {
    throw new ApiRequestError(timeout.aborted ? { kind: "timeout" } : toApiError(error));
  }
  if (!result.data) throw new ApiRequestError(toApiError(result));
  return result.data;
}

/**
 * The latest known dataset, polled while the tab is in front of you. `refetchIntervalInBackground`
 * defaults to false, so a hidden tab issues nothing at all (AC-6), and the query is gated on the
 * health query so a cold function sees one waking request rather than two racing ones (AC-11).
 * On a failure the last good `data` stays put and the next interval recovers on its own (AC-7).
 * `data` is `null` whenever no market is loaded, which is the absence of data, not a change
 * (AC-8).
 */
export function useMeta() {
  const health = useHealth();
  return useQuery({
    queryKey: ["meta"],
    queryFn: fetchMeta,
    enabled: health.isSuccess,
    refetchInterval: META_POLL_MS,
    staleTime: META_STALE_MS,
    retry: false,
  });
}
