import { describe, expect, it } from "vitest";

import { DEFAULT_CONFIGS } from "@/features/exit-lab";
import { fieldErrorsFrom422 } from "@/lib/field-errors";
import { mocks } from "@/mocks/handlers";

import {
  configsOf,
  DEFAULT_INPUTS,
  inputsFromParams,
  labFrom,
  paramsFromInputs,
  placeErrors,
  requestFrom,
  type BacktestInputs,
} from "./inputs";

import exitsDuplicate from "../../../../../contracts/mocks/422.exits.duplicate_type.json";
import simOutOfRange from "../../../../../contracts/mocks/422.sim.out_of_range.json";

const custom: BacktestInputs = {
  ...DEFAULT_INPUTS,
  template: "pullback_ema21",
  stopPct: 5.5,
  timeBars: null,
  maxPositions: 4,
  slippageBps: 0,
  start: "2022-01-03",
  end: "2024-12-31",
};

describe("inputs in the URL", () => {
  it("opens on the defaults with no params", () => {
    expect(inputsFromParams(new URLSearchParams())).toEqual(DEFAULT_INPUTS);
  });

  it("round trips every field", () => {
    expect(inputsFromParams(paramsFromInputs(custom))).toEqual(custom);
  });

  it("round trips all six exits and a ?r= rule, writing ?r= instead of ?template=", () => {
    const every: BacktestInputs = {
      ...custom,
      r: "eyJuYW1lIjoieCJ9",
      atrK: 2,
      atrN: 20,
      targetPct: 15,
      trailPct: 10,
      maN: 21,
      maKind: "ema",
      timeBars: 30,
    };
    const params = paramsFromInputs(every);
    expect(params.has("template")).toBe(false);
    expect(inputsFromParams(params)).toEqual({ ...every, template: DEFAULT_INPUTS.template });
  });

  it("falls back on bad values instead of failing", () => {
    const params = new URLSearchParams({
      x: "{not json",
      max_positions: "lots",
      start: "yesterday",
    });
    const inputs = inputsFromParams(params);
    expect(inputs.stopPct).toBe(DEFAULT_INPUTS.stopPct);
    expect(inputs.maxPositions).toBe(DEFAULT_INPUTS.maxPositions);
    expect(inputs.start).toBe("");
  });
});

describe("requestFrom", () => {
  it("sends one config with only the exits you filled in", () => {
    const body = requestFrom(custom, mocks.templates[1].rule);
    expect(body.configs).toEqual([{ name: "Config 1", exits: [{ type: "stop_pct", pct: 5.5 }] }]);
    expect(body.sim).toMatchObject({
      max_positions: 4,
      slippage_bps: 0,
      start: "2022-01-03",
      end: "2024-12-31",
    });
  });
});

// covers: AC-17 (422 on the right field, U-7)
describe("placeErrors", () => {
  it("puts a sim error on its field", () => {
    const placed = placeErrors(fieldErrorsFrom422(simOutOfRange), DEFAULT_INPUTS);
    expect(placed.fields.maxPositions).toBe("Must be between 1 and 20");
    expect(placed.form).toEqual([]);
  });

  it("puts an exit error on the exit at that index", () => {
    const placed = placeErrors(fieldErrorsFrom422(exitsDuplicate), DEFAULT_INPUTS);
    expect(placed.fields.timeBars).toMatch(/already used/);
    expect(placed.form).toEqual([]);
  });

  it("puts a feature 11 exit's error on the key it names", () => {
    const inputs = { ...DEFAULT_INPUTS, atrK: 2, maN: 3 };
    const body = {
      detail: [
        { loc: ["body", "configs", 0, "exits", 1, "n"], msg: "must be at least 2" },
        { loc: ["body", "configs", 0, "exits", 2, "n"], msg: "must be at least 5" },
      ],
    };
    const placed = placeErrors(fieldErrorsFrom422(body), inputs);
    expect(placed.fields).toEqual({ atrN: "Must be at least 2", maN: "Must be at least 5" });
    expect(placed.form).toEqual([]);
  });

  it("sends errors with no field on this page to the summary", () => {
    const body = { detail: [{ loc: ["body", "rule", "conditions"], msg: "too many" }] };
    expect(placeErrors(fieldErrorsFrom422(body), DEFAULT_INPUTS).form).toEqual(["Too many"]);
  });
});

// covers: spec 0009 AC-20 (the exit lab's 2 to 6 configs in `?x=`, 422 on the config's field)
describe("exit lab inputs", () => {
  const lab: BacktestInputs = { ...custom, lab: labFrom(DEFAULT_CONFIGS), horizonBars: 40 };

  it("turns the default configs into lab configs and back unchanged", () => {
    expect(configsOf(lab)).toEqual(DEFAULT_CONFIGS);
    expect(new Set(lab.lab!.map((c) => c.id)).size).toBe(DEFAULT_CONFIGS.length);
  });

  it("round trips the configs and the horizon through ?x= and ?horizon_bars=", () => {
    const params = paramsFromInputs(lab);
    expect(JSON.parse(params.get("x")!)).toEqual({ configs: DEFAULT_CONFIGS });
    expect(params.get("horizon_bars")).toBe("40");
    expect(params.has("max_positions")).toBe(false);
    const back = inputsFromParams(params);
    expect(configsOf(back)).toEqual(DEFAULT_CONFIGS);
    expect(back.horizonBars).toBe(40);
  });

  it("keeps an old one config ?x= link a portfolio backtest", () => {
    const x = JSON.stringify({ exits: [{ type: "stop_pct", pct: 6 }] });
    const inputs = inputsFromParams(new URLSearchParams({ x }));
    expect(inputs.lab).toBeNull();
    expect(inputs.stopPct).toBe(6);
  });

  it("ignores fewer than 2 configs and keeps at most 6", () => {
    const read = (configs: unknown[]) =>
      inputsFromParams(new URLSearchParams({ x: JSON.stringify({ configs }) })).lab;
    expect(read(DEFAULT_CONFIGS.slice(0, 1))).toBeNull();
    expect(read([...DEFAULT_CONFIGS, ...DEFAULT_CONFIGS.slice(0, 3)])).toHaveLength(6);
  });

  it("sends every config with the horizon and the default max positions", () => {
    const body = requestFrom({ ...lab, maxPositions: 99 }, mocks.templates[0].rule);
    expect(body.configs).toEqual(DEFAULT_CONFIGS);
    expect(body.sim).toMatchObject({ horizon_bars: 40, max_positions: 10, seed: 42 });
  });

  it("puts a tagged real API error on that config's exit field", () => {
    const body = {
      detail: [
        // Config 2 is stop_atr, target, time: its exit 0 is the ATR stop.
        { loc: ["body", "configs", 1, "exits", 0, "stop_atr", "n"], msg: "must be at least 2" },
        { loc: ["body", "configs", 3, "exits", 1, "time", "bars"], msg: "must be at least 1" },
        { loc: ["body", "configs", 2, "name"], msg: "duplicate config name" },
        { loc: ["body", "configs", 4, "exits"], msg: "too short" },
        { loc: ["body", "sim", "horizon_bars"], msg: "must be between 5 and 252" },
      ],
    };
    const placed = placeErrors(fieldErrorsFrom422(body), lab);
    expect(placed.configs).toEqual([
      {},
      { atrN: "Must be at least 2" },
      { name: "Duplicate config name" },
      { timeBars: "Must be at least 1" },
      { config: "Too short" },
    ]);
    expect(placed.fields).toEqual({ horizonBars: "Must be between 5 and 252" });
    expect(placed.form).toEqual([]);
  });

  it("sends a configs count error to the summary", () => {
    const body = { detail: [{ loc: ["body", "configs"], msg: "must be between 1 and 6" }] };
    expect(placeErrors(fieldErrorsFrom422(body), lab).form).toEqual(["Must be between 1 and 6"]);
  });
});
