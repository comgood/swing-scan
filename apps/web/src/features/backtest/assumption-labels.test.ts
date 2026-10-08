import { describe, expect, it } from "vitest";

import { mocks } from "@/mocks/handlers";

import { ASSUMPTION_LABELS, assumptionLines, exitText, NOT_USED } from "./assumption-labels";

const assumptions = mocks.backtestPortfolio.assumptions;

// covers: AC-12 (one label per Assumptions field, null reads "not used in portfolio mode")
describe("assumptionLines", () => {
  it("has one line per Assumptions field", () => {
    const keys = assumptionLines(assumptions).map((l) => l.key);
    expect([...keys].sort()).toEqual(Object.keys(assumptions).sort());
    expect(Object.keys(ASSUMPTION_LABELS)).toHaveLength(Object.keys(assumptions).length);
  });

  it("reads a null field as not used in portfolio mode", () => {
    const byKey = Object.fromEntries(assumptionLines(assumptions).map((l) => [l.key, l.text]));
    expect(byKey.horizon_bars).toBe(NOT_USED);
    expect(byKey.seed).toBe(NOT_USED);
  });

  it("says every U-3 item in plain words", () => {
    const byKey = Object.fromEntries(assumptionLines(assumptions).map((l) => [l.key, l.text]));
    expect(byKey).toMatchObject({
      slippage_bps: "10 bps per side",
      max_positions: "10",
      cooldown_bars: "10 bars",
      configs: "Baseline: stop 8.00% below entry, exit at the close of bar 20",
      oos_start: "2024-07-03",
      oos_fraction: "last 30% of sessions",
      data_mode: "synthetic",
      data_version: "synthetic:v1:seed42",
      data_seed: "42",
    });
  });
});

describe("exitText", () => {
  it("describes the exits feature 11 adds too", () => {
    expect(exitText({ type: "close_below_ma", ma: "ema", n: 21 })).toBe(
      "exit at the next open after a close below EMA(21)",
    );
    expect(exitText({ type: "stop_atr", k: 2, n: 14 })).toBe("stop 2.00 × ATR(14) below entry");
  });
});
