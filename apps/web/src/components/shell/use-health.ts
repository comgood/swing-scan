"use client";

// The shell's one health query (spec 0003 AC-4). It also wakes a cold Lambda.
import { useQuery } from "@tanstack/react-query";

import { ApiRequestError, toApiError } from "@/lib/api-error";
import { api } from "@/lib/api";

export const HEALTH_TIMEOUT_MS = 10_000;

export interface Health {
  status?: string;
  data_mode?: string;
  version?: string;
}

async function fetchHealth({ signal }: { signal: AbortSignal }): Promise<Health> {
  const timeout = AbortSignal.timeout(HEALTH_TIMEOUT_MS);
  let result;
  try {
    result = await api.GET("/api/v1/health", { signal: AbortSignal.any([signal, timeout]) });
  } catch (error) {
    throw new ApiRequestError(timeout.aborted ? { kind: "timeout" } : toApiError(error));
  }
  if (!result.data) throw new ApiRequestError(toApiError(result));
  return result.data;
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: 1,
    staleTime: Infinity,
  });
}

/** Only the exact string "live" counts as live; pending, errors and anything else are synthetic. */
export function isLive(health: Health | undefined): boolean {
  return health?.data_mode === "live";
}
