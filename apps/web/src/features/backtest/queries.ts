"use client";

// The report's two requests: the template list (rule source until feature 10) and the backtest
// itself, which runs only on submit. Errors reach the page as ApiRequestError; a 422 keeps its
// body so the fields can show it (U-7).
import type { BacktestRequest, Schemas, TemplateOut } from "@swing-scan/api-client";
import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { ApiRequestError, toApiError } from "@/lib/api-error";
import { fieldErrorsFrom422, type FieldErrors } from "@/lib/field-errors";

export type PortfolioResult = Schemas["PortfolioResult"];

/** A 422: the fields to mark, not a page error. */
export class ValidationFailed extends Error {
  constructor(readonly errors: FieldErrors) {
    super("HTTP 422");
    this.name = "ValidationFailed";
  }
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

async function runBacktest(body: BacktestRequest): Promise<PortfolioResult> {
  let result;
  try {
    result = await api.POST("/api/v1/backtest", { body });
  } catch (error) {
    throw new ApiRequestError(toApiError(error));
  }
  if (result.response.status === 422) throw new ValidationFailed(fieldErrorsFrom422(result.error));
  if (!result.data) throw new ApiRequestError(toApiError(result));
  // One config always answers in portfolio mode (spec 0002); anything else is a contract bug.
  if (result.data.mode !== "portfolio") {
    throw new ApiRequestError({ kind: "http", status: 500, detail: "Unexpected result mode" });
  }
  return result.data;
}

/** Same key and fetch as the scan workspace, so the two pages share one cached list. */
export function useTemplates() {
  return useQuery({
    queryKey: ["templates"],
    queryFn: fetchTemplates,
    staleTime: Infinity,
    retry: false,
  });
}

export function useBacktest() {
  return useMutation({ mutationFn: runBacktest, retry: false });
}
