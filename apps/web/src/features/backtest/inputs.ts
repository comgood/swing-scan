// The report page's inputs (spec 0007 decision 11): they live in the URL so a link reproduces a
// run. `?r=` carries a rule from the rule builder (spec 0008 decision 12), else `?template=`
// names one, never both after a run; `?x=` carries the exits as JSON, `{"exits": [...]}` for one
// config or `{"configs": [...]}` for the exit lab's 2 to 6 (spec 0009); the sim fields are plain
// keys. Bad or missing values fall back to defaults.
import type { BacktestRequest, ExitConfig, Rule } from "@swing-scan/api-client";

import { errorAt, errorsUnder, withoutTag, type FieldErrors } from "@/lib/field-errors";

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
  /** The exit lab's 2 to 6 configs; null runs the one config above as a portfolio backtest. */
  lab: LabConfig[] | null;
  /** Trade mode only: a trade still open on this bar exits at its close. */
  horizonBars: number | null;
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
  lab: null,
  horizonBars: 60,
  maxPositions: 10,
  slippageBps: 10,
  start: "",
  end: "",
};

/** Portfolio mode ignores the horizon and trade mode max positions, but the generated
 * `SimParams` type requires both. The seed stays the contract's default (AGENTS.md). */
const HORIZON_BARS = 60;
const MAX_POSITIONS = 10;
const SEED = 42;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
export const CONFIG_NAME = "Config 1";
export const MIN_CONFIGS = 2;
export const MAX_CONFIGS = 6;

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

export type ExitInputs = Pick<BacktestInputs, ExitField | "maKind">;

/** One exit lab config: a name and a full exit set. `id` keys its card and never leaves the page. */
export type LabConfig = ExitInputs & { id: number; name: string };

let lastConfigId = 0;
export const nextConfigId = () => ++lastConfigId;

type Json = Record<string, unknown> | null | undefined;

function numberOr(text: string | null, fallback: number | null): number | null {
  if (text === null || text.trim() === "") return fallback;
  const value = Number(text);
  return Number.isFinite(value) ? value : fallback;
}

function dateOr(text: string | null): string {
  return text !== null && DATE.test(text) ? text : "";
}

function parseJson(text: string | null): Json {
  if (text === null) return null;
  try {
    return JSON.parse(text) as Json;
  } catch {
    return null;
  }
}

/** The exit fields a contract exit list fills; a type it lacks is blank. Null if not a list. */
function readExits(exits: unknown): ExitInputs | null {
  if (!Array.isArray(exits)) return null;
  const byType = (type: string) => exits.find((e: unknown) => (e as Json)?.type === type) as Json;
  const read = (type: string, key: string): number | null => {
    const value = byType(type)?.[key];
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  };
  const found = Object.fromEntries(
    EXIT_FIELDS.map(({ field, type, key }) => [field, read(type, key)]),
  ) as Record<ExitField, number | null>;
  return {
    ...found,
    atrN: found.atrN ?? DEFAULT_INPUTS.atrN,
    maKind: byType("close_below_ma")?.ma === "ema" ? "ema" : "sma",
  };
}

function exitsFrom(x: Json): ExitInputs {
  const { stopPct, atrK, atrN, targetPct, trailPct, maN, maKind, timeBars } = DEFAULT_INPUTS;
  return readExits(x?.exits) ?? { stopPct, atrK, atrN, targetPct, trailPct, maN, maKind, timeBars };
}

/** Contract configs as editable lab configs, at most six (the lab opens with `DEFAULT_CONFIGS`). */
export function labFrom(configs: readonly unknown[]): LabConfig[] {
  return configs.slice(0, MAX_CONFIGS).map((config, i) => {
    const name = (config as Json)?.name;
    return {
      ...(readExits((config as Json)?.exits) ?? (readExits([]) as ExitInputs)),
      id: nextConfigId(),
      name: typeof name === "string" ? name : `Config ${String(i + 1)}`,
    };
  });
}

function labOf(x: Json): LabConfig[] | null {
  const configs = x?.configs;
  return Array.isArray(configs) && configs.length >= MIN_CONFIGS ? labFrom(configs) : null;
}

export function inputsFromParams(params: URLSearchParams): BacktestInputs {
  const x = parseJson(params.get("x"));
  return {
    template: params.get("template") || DEFAULT_INPUTS.template,
    r: params.get("r") || null,
    ...exitsFrom(x),
    lab: labOf(x),
    horizonBars: numberOr(params.get("horizon_bars"), DEFAULT_INPUTS.horizonBars),
    maxPositions: numberOr(params.get("max_positions"), DEFAULT_INPUTS.maxPositions),
    slippageBps: numberOr(params.get("slippage_bps"), DEFAULT_INPUTS.slippageBps),
    start: dateOr(params.get("start")),
    end: dateOr(params.get("end")),
  };
}

/** The exits in the contract's order; a blank field means that exit is not used. */
export function exitsOf(inputs: ExitInputs): Exit[] {
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

/** The configs a run sends: the lab's 2 to 6, or the one config of a portfolio backtest. */
export function configsOf(inputs: BacktestInputs): ExitConfig[] {
  if (inputs.lab) return inputs.lab.map((c) => ({ name: c.name, exits: exitsOf(c) }));
  return [{ name: CONFIG_NAME, exits: exitsOf(inputs) }];
}

export function paramsFromInputs(inputs: BacktestInputs): URLSearchParams {
  const params = new URLSearchParams(
    inputs.r !== null ? { r: inputs.r } : { template: inputs.template },
  );
  if (inputs.lab) {
    params.set("x", JSON.stringify({ configs: configsOf(inputs) }));
    if (inputs.horizonBars !== null) params.set("horizon_bars", String(inputs.horizonBars));
  } else {
    params.set("x", JSON.stringify({ exits: exitsOf(inputs) }));
    if (inputs.maxPositions !== null) params.set("max_positions", String(inputs.maxPositions));
  }
  if (inputs.slippageBps !== null) params.set("slippage_bps", String(inputs.slippageBps));
  if (inputs.start) params.set("start", inputs.start);
  if (inputs.end) params.set("end", inputs.end);
  return params;
}

export function requestFrom(inputs: BacktestInputs, rule: Rule): BacktestRequest {
  const lab = inputs.lab !== null;
  return {
    rule,
    configs: configsOf(inputs),
    sim: {
      max_positions: lab ? MAX_POSITIONS : (inputs.maxPositions ?? MAX_POSITIONS),
      slippage_bps: inputs.slippageBps ?? (DEFAULT_INPUTS.slippageBps as number),
      horizon_bars: lab ? (inputs.horizonBars ?? HORIZON_BARS) : HORIZON_BARS,
      seed: SEED,
      start: inputs.start || null,
      end: inputs.end || null,
    },
  };
}

export type InputField =
  ExitField | "horizonBars" | "maxPositions" | "slippageBps" | "start" | "end";

/** Where a lab config's errors land: an exit field, its name, or the card as a whole. */
export type ConfigField = ExitField | "name" | "config";

export interface PlacedErrors {
  fields: Partial<Record<InputField, string>>;
  /** One entry per lab config, in order; empty for a portfolio backtest. */
  configs: Partial<Record<ConfigField, string>>[];
  form: string[];
}

const SIM_FIELDS: Record<string, InputField> = {
  "sim.horizon_bars": "horizonBars",
  "sim.max_positions": "maxPositions",
  "sim.slippage_bps": "slippageBps",
  "sim.start": "start",
  "sim.end": "end",
};

const EXIT_TYPES = [...new Set(EXIT_FIELDS.map((f) => f.type))];

/** The real API names the exit's tag in `loc` (`configs.0.exits.1.stop_atr.n`); drop it (U-7). */
function untagged(errors: FieldErrors): FieldErrors {
  const fields: Record<string, string> = {};
  for (const [path, message] of Object.entries(errors.fields)) {
    const parts = path.split(".");
    const isExit = parts[0] === "configs" && parts[2] === "exits";
    fields[(isExit ? withoutTag(parts, 4, EXIT_TYPES) : parts).join(".")] ??= message;
  }
  return { fields, form: errors.form };
}

/** Config `index`'s errors keyed by its fields; marks each path it used in `placed`. */
function placeConfig(
  errors: FieldErrors,
  index: number,
  exits: ExitInputs,
  placed: Set<string>,
): Partial<Record<ConfigField, string>> {
  const out: Partial<Record<ConfigField, string>> = {};
  const config = `configs.${String(index)}`;
  exitsOf(exits).forEach((exit, j) => {
    const prefix = `${config}.exits.${String(j)}`;
    const own = EXIT_FIELDS.filter((f) => f.type === exit.type);
    for (const [path, message] of Object.entries(errorsUnder(errors, prefix))) {
      // `…exits.1.n` lands on that key's field; `…exits.1` or `…exits.1.type` on the first one.
      const key = path.slice(prefix.length + 1);
      const field = (own.find((f) => f.key === key) ?? own[0])?.field;
      if (!field) continue;
      out[field] ??= message;
      placed.add(path);
    }
  });
  const rest: [string, ConfigField][] = [
    [`${config}.name`, "name"],
    [`${config}.exits`, "config"],
    [config, "config"],
  ];
  for (const [path, field] of rest) {
    const message = errorAt(errors, path);
    if (message === undefined) continue;
    out[field] ??= message;
    placed.add(path);
  }
  return out;
}

/** Puts each 422 issue on the field you typed it in (U-7); the rest go to the form summary. */
export function placeErrors(raw: FieldErrors, inputs: BacktestInputs): PlacedErrors {
  const errors = untagged(raw);
  const fields: Partial<Record<InputField, string>> = {};
  const placed = new Set<string>();
  for (const [path, field] of Object.entries(SIM_FIELDS)) {
    const message = errorAt(errors, path);
    if (message) {
      fields[field] = message;
      placed.add(path);
    }
  }
  let configs: Partial<Record<ConfigField, string>>[] = [];
  if (inputs.lab) {
    configs = inputs.lab.map((config, i) => placeConfig(errors, i, config, placed));
  } else {
    // One config has no card and a fixed name: its exit errors go on the fields, the rest to
    // the summary.
    const single = placeConfig(errors, 0, inputs, placed);
    for (const { field } of EXIT_FIELDS) if (single[field]) fields[field] = single[field];
    for (const path of ["configs.0.name", "configs.0.exits", "configs.0"]) placed.delete(path);
  }
  const rest = Object.entries(errors.fields)
    .filter(([path]) => !placed.has(path))
    .map(([, message]) => message);
  return { fields, configs, form: [...errors.form, ...rest] };
}
