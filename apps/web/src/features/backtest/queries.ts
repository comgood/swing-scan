"use client";

// The report's requests: the template list, the indicator catalog (to check a `?r=` rule) and
// the backtest itself, which runs only on submit. Errors reach the page as ApiRequestError; a
// 422 keeps its body so the fields can show it (U-7).
import type { BacktestRequest, Schemas } from "@swing-scan/api-client";
import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { ApiRequestError, toApiError } from "@/lib/api-error";
import { fieldErrorsFrom422, type FieldErrors } from "@/lib/field-errors";

// The template list and the indicator catalog are the scan workspace's queries, re-exported so
// this page keeps importing them from one place. Same query keys, so both pages share one cache.
export { useIndicators, useTemplates } from "@/features/scan";

export type PortfolioResult = Schemas["PortfolioResult"];
export type TradeLabResult = Schemas["TradeLabResult"];
export type BacktestResult = PortfolioResult | TradeLabResult;

/** A 422: the fields to mark, not a page error. */
export class ValidationFailed extends Error {
  constructor(readonly errors: FieldErrors) {
    super("HTTP 422");
    this.name = "ValidationFailed";
  }
}

async function runBacktest(body: BacktestRequest): Promise<BacktestResult> {
  let result;
  try {
    result = await api.POST("/api/v1/backtest", { body });
  } catch (error) {
    throw new ApiRequestError(toApiError(error));
  }
  if (result.response.status === 422) throw new ValidationFailed(fieldErrorsFrom422(result.error));
  if (!result.data) throw new ApiRequestError(toApiError(result));
  // One config answers in portfolio mode, 2 to 6 in trade mode (spec 0002); else a contract bug.
  const mode = body.configs.length === 1 ? "portfolio" : "trade";
  if (result.data.mode !== mode) {
    throw new ApiRequestError({ kind: "http", status: 500, detail: "Unexpected result mode" });
  }
  return result.data;
}

export function useBacktest() {
  return useMutation({ mutationFn: runBacktest, retry: false });
}
