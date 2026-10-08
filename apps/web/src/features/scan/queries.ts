"use client";

// The workspace's two queries (spec 0005): the template list and the scan of one rule. Errors
// reach the page as ApiRequestError, so ErrorState can say what went wrong (spec 0003 AC-10).
import type { Rule, ScanResponse, TemplateOut } from "@swing-scan/api-client";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { ApiRequestError, toApiError } from "@/lib/api-error";

async function fetchTemplates({ signal }: { signal: AbortSignal }): Promise<TemplateOut[]> {
  let result;
  try {
    result = await api.GET("/api/v1/templates", { signal });
  } catch (error) {
    throw new ApiRequestError(toApiError(error));
  }
  if (!result.data) throw new ApiRequestError(toApiError(result));
  return result.data;
}

async function fetchScan(rule: Rule, signal: AbortSignal): Promise<ScanResponse> {
  let result;
  try {
    // The web app never sends `as_of`: the API defaults it to the last session (AC-6).
    result = await api.POST("/api/v1/scan", { body: { rule }, signal });
  } catch (error) {
    throw new ApiRequestError(toApiError(error));
  }
  if (!result.data) throw new ApiRequestError(toApiError(result));
  return result.data;
}

/** Templates never change while the app is open. Failures wait for "Try again". */
export function useTemplates() {
  return useQuery({
    queryKey: ["templates"],
    queryFn: fetchTemplates,
    staleTime: Infinity,
    retry: false,
  });
}

/** One scan per rule; no request runs until a rule is chosen. */
export function useScan(rule: Rule | undefined) {
  return useQuery({
    queryKey: ["scan", rule],
    queryFn: ({ signal }) => fetchScan(rule as Rule, signal),
    enabled: rule !== undefined,
    staleTime: Infinity,
    retry: false,
  });
}
