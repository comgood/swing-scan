// The report page's inputs (spec 0007 decision 11): they live in the URL so a link reproduces a
// run. `?template=` names the rule until feature 10 adds `?r=`; `?x=` carries the one exit
// config as JSON; the sim fields are plain keys. Bad or missing values fall back to defaults.
import type { BacktestRequest, ExitConfig, Rule } from "@swing-scan/api-client";

import { errorAt, errorsUnder, type FieldErrors } from "@/lib/field-errors";

export interface BacktestInputs {
  template: string;
  stopPct: number | null;
  timeBars: number | null;
  maxPositions: number | null;
  slippageBps: number | null;
  start: string;
  end: string;
}

/** Defaults match the contract's (`StopPct.pct`, `SimParams`) and the frozen mock's config. */
export const DEFAULT_INPUTS: BacktestInputs = {
  template: "breakout_52w",
  stopPct: 8,
  timeBars: 20,
  maxPositions: 10,
  slippageBps: 10,
  start: "",
  end: "",
};

/** Ignored in portfolio mode, but required by the generated `SimParams` type. */
const HORIZON_BARS = 60;
const SEED = 42;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
export const CONFIG_NAME = "Config 1";

type Exit = ExitConfig["exits"][number];

function numberOr(text: string | null, fallback: number | null): number | null {
  if (text === null || text.trim() === "") return fallback;
  const value = Number(text);
  return Number.isFinite(value) ? value : fallback;
}

function dateOr(text: string | null): string {
  return text !== null && DATE.test(text) ? text : "";
}

function exitsFrom(text: string | null): Pick<BacktestInputs, "stopPct" | "timeBars"> {
  const fallback = { stopPct: DEFAULT_INPUTS.stopPct, timeBars: DEFAULT_INPUTS.timeBars };
  if (text === null) return fallback;
  try {
    const parsed: unknown = JSON.parse(text);
    const exits = (parsed as { exits?: unknown }).exits;
    if (!Array.isArray(exits)) return fallback;
    const find = (type: string, key: string): number | null => {
      const exit = exits.find((e: unknown) => (e as { type?: unknown })?.type === type) as
        Record<string, unknown> | undefined;
      const value = exit?.[key];
      return typeof value === "number" && Number.isFinite(value) ? value : null;
    };
    return { stopPct: find("stop_pct", "pct"), timeBars: find("time", "bars") };
  } catch {
    return fallback;
  }
}

export function inputsFromParams(params: URLSearchParams): BacktestInputs {
  return {
    template: params.get("template") || DEFAULT_INPUTS.template,
    ...exitsFrom(params.get("x")),
    maxPositions: numberOr(params.get("max_positions"), DEFAULT_INPUTS.maxPositions),
    slippageBps: numberOr(params.get("slippage_bps"), DEFAULT_INPUTS.slippageBps),
    start: dateOr(params.get("start")),
    end: dateOr(params.get("end")),
  };
}

/** The exits in request order; a blank field means that exit is not used. */
export function exitsOf(inputs: BacktestInputs): Exit[] {
  const exits: Exit[] = [];
  if (inputs.stopPct !== null) exits.push({ type: "stop_pct", pct: inputs.stopPct });
  if (inputs.timeBars !== null) exits.push({ type: "time", bars: inputs.timeBars });
  return exits;
}

export function paramsFromInputs(inputs: BacktestInputs): URLSearchParams {
  const params = new URLSearchParams({ template: inputs.template });
  params.set("x", JSON.stringify({ exits: exitsOf(inputs) }));
  if (inputs.maxPositions !== null) params.set("max_positions", String(inputs.maxPositions));
  if (inputs.slippageBps !== null) params.set("slippage_bps", String(inputs.slippageBps));
  if (inputs.start) params.set("start", inputs.start);
  if (inputs.end) params.set("end", inputs.end);
  return params;
}

export function requestFrom(inputs: BacktestInputs, rule: Rule): BacktestRequest {
  return {
    rule,
    configs: [{ name: CONFIG_NAME, exits: exitsOf(inputs) }],
    sim: {
      max_positions: inputs.maxPositions ?? (DEFAULT_INPUTS.maxPositions as number),
      slippage_bps: inputs.slippageBps ?? (DEFAULT_INPUTS.slippageBps as number),
      horizon_bars: HORIZON_BARS,
      seed: SEED,
      start: inputs.start || null,
      end: inputs.end || null,
    },
  };
}

export type InputField = "stopPct" | "timeBars" | "maxPositions" | "slippageBps" | "start" | "end";

const SIM_FIELDS: Record<string, InputField> = {
  "sim.max_positions": "maxPositions",
  "sim.slippage_bps": "slippageBps",
  "sim.start": "start",
  "sim.end": "end",
};

/** Puts each 422 issue on the field you typed it in (U-7); the rest go to the form summary. */
export function placeErrors(
  errors: FieldErrors,
  inputs: BacktestInputs,
): { fields: Partial<Record<InputField, string>>; form: string[] } {
  const fields: Partial<Record<InputField, string>> = {};
  const placed = new Set<string>();
  for (const [path, field] of Object.entries(SIM_FIELDS)) {
    const message = errorAt(errors, path);
    if (message) {
      fields[field] = message;
      placed.add(path);
    }
  }
  exitsOf(inputs).forEach((exit, index) => {
    const under = errorsUnder(errors, `configs.0.exits.${String(index)}`);
    const first = Object.entries(under)[0];
    if (!first) return;
    fields[exit.type === "stop_pct" ? "stopPct" : "timeBars"] = first[1];
    Object.keys(under).forEach((path) => placed.add(path));
  });
  const rest = Object.entries(errors.fields)
    .filter(([path]) => !placed.has(path))
    .map(([, message]) => message);
  return { fields, form: [...errors.form, ...rest] };
}
