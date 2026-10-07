// MSW handlers serving the generated mocks in contracts/mocks/ (spec 0002 AC-13).
// Defaults answer like a healthy API; tests switch a route to an error or a delay with
// `server.use(scanHandler("422.rule.unknown_indicator"))` and the like (U-5, U-7).
import type { BacktestRequest, Schemas } from "@swing-scan/api-client";
import { delay, http, HttpResponse, type JsonBodyType } from "msw";

import exitsDuplicateType from "../../../../contracts/mocks/422.exits.duplicate_type.json";
import exitsTooManyConfigs from "../../../../contracts/mocks/422.exits.too_many_configs.json";
import ruleNOutOfRange from "../../../../contracts/mocks/422.rule.n_out_of_range.json";
import ruleTooManyConditions from "../../../../contracts/mocks/422.rule.too_many_conditions.json";
import ruleUnknownIndicator from "../../../../contracts/mocks/422.rule.unknown_indicator.json";
import simOutOfRange from "../../../../contracts/mocks/422.sim.out_of_range.json";
import scanNotImplemented from "../../../../contracts/mocks/501.scan.json";
import backtestNoEntries from "../../../../contracts/mocks/backtest.no_entries.json";
import backtestPortfolio from "../../../../contracts/mocks/backtest.portfolio.json";
import backtestTruncated from "../../../../contracts/mocks/backtest.portfolio.truncated.json";
import backtestTradeLab from "../../../../contracts/mocks/backtest.trade_lab.json";
import indicators from "../../../../contracts/mocks/indicators.json";
import meta from "../../../../contracts/mocks/meta.json";
import scanEmpty from "../../../../contracts/mocks/scan.empty.json";
import scan from "../../../../contracts/mocks/scan.json";
import templates from "../../../../contracts/mocks/templates.json";

/** Matches the API on any origin, so tests and the browser share one set of handlers. */
const API = "*/api/v1";

/** The mock bodies, typed by the generated client. CI validates them against the models. */
export const mocks = {
  meta: meta as Schemas["MetaResponse"],
  indicators: indicators as Schemas["IndicatorSpec"][],
  templates: templates as Schemas["TemplateOut"][],
  scan: scan as Schemas["ScanResponse"],
  scanEmpty: scanEmpty as Schemas["ScanResponse"],
  backtestPortfolio: backtestPortfolio as Schemas["PortfolioResult"],
  backtestTruncated: backtestTruncated as Schemas["PortfolioResult"],
  backtestTradeLab: backtestTradeLab as Schemas["TradeLabResult"],
  backtestNoEntries: backtestNoEntries as Schemas["PortfolioResult"],
};

const errors = {
  "422.rule.unknown_indicator": ruleUnknownIndicator,
  "422.rule.n_out_of_range": ruleNOutOfRange,
  "422.rule.too_many_conditions": ruleTooManyConditions,
  "422.exits.duplicate_type": exitsDuplicateType,
  "422.exits.too_many_configs": exitsTooManyConfigs,
  "422.sim.out_of_range": simOutOfRange,
  "501.scan": scanNotImplemented,
} satisfies Record<string, JsonBodyType>;

export type ErrorMock = keyof typeof errors;

export interface MockOptions {
  /** Wait this long before answering, or forever ("infinite") to hold a loading state. */
  delayMs?: number | "infinite";
}

function statusOf(name: ErrorMock): number {
  return Number(name.slice(0, 3));
}

async function respond(body: JsonBodyType, status: number, options: MockOptions) {
  if (options.delayMs !== undefined) await delay(options.delayMs);
  return HttpResponse.json(body, { status });
}

function errorOrBody(variant: string, body: JsonBodyType, options: MockOptions) {
  return variant in errors
    ? respond(errors[variant as ErrorMock], statusOf(variant as ErrorMock), options)
    : respond(body, 200, options);
}

/**
 * `/health` returns `dict[str, str]` in the contract, so it has no mock file; this body mirrors
 * the API's `{status, data_mode, version}`. `network_error` fails the request outright.
 */
export type HealthVariant = "synthetic" | "live" | "network_error";

export function healthHandler(variant: HealthVariant = "synthetic", options: MockOptions = {}) {
  return http.get(`${API}/health`, () =>
    variant === "network_error"
      ? HttpResponse.error()
      : respond({ status: "ok", data_mode: variant, version: "0.1.0" }, 200, options),
  );
}

export function metaHandler(options: MockOptions = {}) {
  return http.get(`${API}/meta`, () => respond(mocks.meta, 200, options));
}

export function indicatorsHandler(options: MockOptions = {}) {
  return http.get(`${API}/indicators`, () => respond(mocks.indicators, 200, options));
}

export function templatesHandler(options: MockOptions = {}) {
  return http.get(`${API}/templates`, () => respond(mocks.templates, 200, options));
}

export type ScanVariant = "ok" | "empty" | ErrorMock;

export function scanHandler(variant: ScanVariant = "ok", options: MockOptions = {}) {
  const body = variant === "empty" ? mocks.scanEmpty : mocks.scan;
  return http.post(`${API}/scan`, () => errorOrBody(variant, body, options));
}

/** `auto` answers like the real API: 1 config is portfolio mode, 2 to 6 the exit lab. */
export type BacktestVariant = "auto" | "truncated" | "no_entries" | ErrorMock;

export function backtestHandler(variant: BacktestVariant = "auto", options: MockOptions = {}) {
  return http.post(`${API}/backtest`, async ({ request }) => {
    if (variant === "truncated") return respond(mocks.backtestTruncated, 200, options);
    if (variant === "no_entries") return respond(mocks.backtestNoEntries, 200, options);
    if (variant !== "auto") return errorOrBody(variant, {}, options);
    const body = (await request.json()) as BacktestRequest;
    const configs = body.configs?.length ?? 0;
    if (configs > 6) return respond(errors["422.exits.too_many_configs"], 422, options);
    const result = configs === 1 ? mocks.backtestPortfolio : mocks.backtestTradeLab;
    return respond(result, 200, options);
  });
}

export const handlers = [
  healthHandler(),
  metaHandler(),
  indicatorsHandler(),
  templatesHandler(),
  scanHandler(),
  backtestHandler(),
];
