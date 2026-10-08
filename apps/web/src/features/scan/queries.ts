"use client";

// The workspace's queries (spec 0005, spec 0008): the template list, the indicator catalog and
// the scan of one rule. Errors reach the page as ApiRequestError, so ErrorState can say what went
// wrong (spec 0003 AC-10); a 422 also carries its field errors for the builder (U-7).
import type { IndicatorSpec, Rule, ScanResponse, TemplateOut } from "@swing-scan/api-client";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { ApiRequestError, toApiError, type ApiError } from "@/lib/api-error";
import { fieldErrorsFrom422, type FieldErrors } from "@/lib/field-errors";

/** A scan the API rejected with 422: the rule is invalid, and these fields say where. */
export class RuleRejectedError extends ApiRequestError {
  constructor(
    apiError: ApiError,
    readonly fieldErrors: FieldErrors,
  ) {
    super(apiError);
    this.name = "RuleRejectedError";
  }
}

async function fetchIndicators({ signal }: { signal: AbortSignal }): Promise<IndicatorSpec[]> {
  let result;
  try {
    result = await api.GET("/api/v1/indicators", { signal });
  } catch (error) {
    throw new ApiRequestError(toApiError(error));
  }
  if (!result.data) throw new ApiRequestError(toApiError(result));
  return result.data;
}

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
  if (result.response.status === 422) {
    throw new RuleRejectedError(toApiError(result), fieldErrorsFrom422(result.error));
  }
  if (!result.data) throw new ApiRequestError(toApiError(result));
  return result.data;
}

/** The indicator catalog never changes while the app is open. */
export function useIndicators() {
  return useQuery({
    queryKey: ["indicators"],
    queryFn: fetchIndicators,
    staleTime: Infinity,
    retry: false,
  });
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
