// The report page's inputs (spec 0007 decision 11): they live in the URL so a link reproduces a
// run. `?r=` carries a rule from the rule builder (spec 0008 decision 12), else `?template=`
// names one, never both after a run; `?x=` carries the one exit config as JSON; the sim fields
// are plain keys. Bad or missing values fall back to defaults.
import type { BacktestRequest, ExitConfig, Rule } from "@swing-scan/api-client";

import { errorAt, errorsUnder, type FieldErrors } from "@/lib/field-errors";

export type MaKind = "sma" | "ema";

export interface BacktestInputs {
  template: string;
  /** An encoded rule (`?r=`); while set it is the rule, not `template`. */
  r: string | null;
  stopPct: number | null;
  /** ATR stop multiple; blank means no ATR stop. `atrN` is the ATR length. */
  atrK: number | null;
  atrN: number | null;
  targetPct: number | null;
  trailPct: number | null;
  /** Close below MA length; blank means no MA exit. */
  maN: number | null;
  maKind: MaKind;
  timeBars: number | null;
  maxPositions: number | null;
  slippageBps: number | null;
  start: string;
  end: string;
}

/** Defaults match the contract's (`StopPct.pct`, `StopAtr.n`, `SimParams`) and the mock's config. */
export const DEFAULT_INPUTS: BacktestInputs = {
  template: "breakout_52w",
  r: null,
  stopPct: 8,
  atrK: null,
  atrN: 14,
  targetPct: null,
  trailPct: null,
  maN: null,
  maKind: "sma",
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

export type ExitField = "stopPct" | "atrK" | "atrN" | "targetPct" | "trailPct" | "maN" | "timeBars";

/** Each numeric exit field and the contract key it fills, in the contract's exit order. */
const EXIT_FIELDS: readonly { field: ExitField; type: Exit["type"]; key: string }[] = [
  { field: "stopPct", type: "stop_pct", key: "pct" },
  { field: "atrK", type: "stop_atr", key: "k" },
  { field: "atrN", type: "stop_atr", key: "n" },
  { field: "targetPct", type: "target", key: "pct" },
  { field: "trailPct", type: "trail_pct", key: "pct" },
  { field: "maN", type: "close_below_ma", key: "n" },
  { field: "timeBars", type: "time", key: "bars" },
];

function numberOr(text: string | null, fallback: number | null): number | null {
  if (text === null || text.trim() === "") return fallback;
  const value = Number(text);
  return Number.isFinite(value) ? value : fallback;
}

function dateOr(text: string | null): string {
  return text !== null && DATE.test(text) ? text : "";
}

type ExitInputs = Pick<BacktestInputs, ExitField | "maKind">;

function exitsFrom(text: string | null): ExitInputs {
  const { stopPct, atrK, atrN, targetPct, trailPct, maN, maKind, timeBars } = DEFAULT_INPUTS;
  const fallback = { stopPct, atrK, atrN, targetPct, trailPct, maN, maKind, timeBars };
  if (text === null) return fallback;
  try {
    const parsed: unknown = JSON.parse(text);
    const exits = (parsed as { exits?: unknown } | null)?.exits;
    if (!Array.isArray(exits)) return fallback;
    const byType = (type: string) =>
      exits.find((e: unknown) => (e as { type?: unknown } | null)?.type === type) as
        Record<string, unknown> | undefined;
    const read = (type: string, key: string): number | null => {
      const value = byType(type)?.[key];
      return typeof value === "number" && Number.isFinite(value) ? value : null;
    };
    const found = Object.fromEntries(
      EXIT_FIELDS.map(({ field, type, key }) => [field, read(type, key)]),
    ) as Record<ExitField, number | null>;
    return {
      ...found,
      atrN: found.atrN ?? atrN,
      maKind: byType("close_below_ma")?.ma === "ema" ? "ema" : "sma",
    };
  } catch {
    return fallback;
  }
}

export function inputsFromParams(params: URLSearchParams): BacktestInputs {
  return {
    template: params.get("template") || DEFAULT_INPUTS.template,
    r: params.get("r") || null,
    ...exitsFrom(params.get("x")),
    maxPositions: numberOr(params.get("max_positions"), DEFAULT_INPUTS.maxPositions),
    slippageBps: numberOr(params.get("slippage_bps"), DEFAULT_INPUTS.slippageBps),
    start: dateOr(params.get("start")),
    end: dateOr(params.get("end")),
  };
}

/** The exits in the contract's order; a blank field means that exit is not used. */
export function exitsOf(inputs: BacktestInputs): Exit[] {
  const exits: Exit[] = [];
  if (inputs.stopPct !== null) exits.push({ type: "stop_pct", pct: inputs.stopPct });
  if (inputs.atrK !== null) {
    const n = inputs.atrN ?? (DEFAULT_INPUTS.atrN as number);
    exits.push({ type: "stop_atr", k: inputs.atrK, n });
  }
  if (inputs.targetPct !== null) exits.push({ type: "target", pct: inputs.targetPct });
  if (inputs.trailPct !== null) exits.push({ type: "trail_pct", pct: inputs.trailPct });
  if (inputs.maN !== null) {
    exits.push({ type: "close_below_ma", n: inputs.maN, ma: inputs.maKind });
  }
  if (inputs.timeBars !== null) exits.push({ type: "time", bars: inputs.timeBars });
  return exits;
}

export function paramsFromInputs(inputs: BacktestInputs): URLSearchParams {
  const params = new URLSearchParams(
    inputs.r !== null ? { r: inputs.r } : { template: inputs.template },
  );
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

export type InputField = ExitField | "maxPositions" | "slippageBps" | "start" | "end";

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
    const prefix = `configs.0.exits.${String(index)}`;
    const own = EXIT_FIELDS.filter((f) => f.type === exit.type);
    for (const [path, message] of Object.entries(errorsUnder(errors, prefix))) {
      // `…exits.1.n` lands on that key's field; `…exits.1` or `…exits.1.type` on the first one.
      const key = path.slice(prefix.length + 1);
      const field = (own.find((f) => f.key === key) ?? own[0])?.field;
      if (!field) continue;
      fields[field] ??= message;
      placed.add(path);
    }
  });
  const rest = Object.entries(errors.fields)
    .filter(([path]) => !placed.has(path))
    .map(([, message]) => message);
  return { fields, form: [...errors.form, ...rest] };
}
