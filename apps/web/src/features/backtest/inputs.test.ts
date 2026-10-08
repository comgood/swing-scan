import { describe, expect, it } from "vitest";

import { fieldErrorsFrom422 } from "@/lib/field-errors";
import { mocks } from "@/mocks/handlers";

import {
  DEFAULT_INPUTS,
  inputsFromParams,
  paramsFromInputs,
  placeErrors,
  requestFrom,
  type BacktestInputs,
} from "./inputs";

import exitsDuplicate from "../../../../../contracts/mocks/422.exits.duplicate_type.json";
import simOutOfRange from "../../../../../contracts/mocks/422.sim.out_of_range.json";

const custom: BacktestInputs = {
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

  it("sends errors with no field on this page to the summary", () => {
    const body = { detail: [{ loc: ["body", "rule", "conditions"], msg: "too many" }] };
    expect(placeErrors(fieldErrorsFrom422(body), DEFAULT_INPUTS).form).toEqual(["Too many"]);
  });
});
