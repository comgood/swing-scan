// covers: spec 0008 AC-4 (state is the rule), AC-5 (1 to 8 rows), decisions 8, 9 and 11
import { describe, expect, it } from "vitest";

import { mocks } from "@/mocks/handlers";

import {
  builderReducer,
  defaultN,
  indOperand,
  initBuilder,
  newCondition,
  switchRightKind,
  withIndicator,
  type BuilderAction,
  type BuilderState,
} from "./reducer";

const breakout = mocks.templates.find((t) => t.id === "breakout_52w")!;
const catalog = mocks.indicators;

function run(state: BuilderState, ...actions: BuilderAction[]): BuilderState {
  return actions.reduce(builderReducer, state);
}

const start = () => initBuilder(breakout.rule, { template: "breakout_52w" });

describe("builderReducer", () => {
  it("starts on the loaded rule, clean, with one id per row", () => {
    const state = start();
    expect(state.rule).toBe(breakout.rule);
    expect(state.rowIds).toHaveLength(3);
    expect(state.dirty).toBe(false);
    expect(state.source).toEqual({ template: "breakout_52w" });
  });

  it("adds close > sma(50) and marks the rule custom and dirty", () => {
    const state = run(start(), { type: "add" });
    expect(state.rule.conditions.at(-1)).toEqual(newCondition());
    expect(state.rule.conditions.at(-1)).toEqual({
      left: { kind: "ind", ind: "close", n: null, offset: 0, mult: 1 },
      op: ">",
      right: { kind: "ind", ind: "sma", n: 50, offset: 0, mult: 1 },
    });
    expect(state.source).toBe("custom");
    expect(state.dirty).toBe(true);
  });

  it("stops at 8 rows (AC-5)", () => {
    const state = run(start(), ...Array.from({ length: 10 }, () => ({ type: "add" }) as const));
    expect(state.rule.conditions).toHaveLength(8);
    expect(state.rowIds).toHaveLength(8);
  });

  it("never removes the last row (AC-5)", () => {
    const state = run(
      start(),
      { type: "remove", index: 0 },
      { type: "remove", index: 0 },
      { type: "remove", index: 0 },
    );
    expect(state.rule.conditions).toHaveLength(1);
    expect(state.rule.conditions[0]).toEqual(breakout.rule.conditions[2]);
  });

  it("keeps row ids stable and unique across add and remove", () => {
    const before = start();
    const state = run(before, { type: "add" }, { type: "remove", index: 1 }, { type: "add" });
    expect(state.rowIds).toHaveLength(state.rule.conditions.length);
    expect(new Set(state.rowIds).size).toBe(state.rowIds.length);
    expect(state.rowIds[0]).toBe(before.rowIds[0]);
    expect(state.rowIds[1]).toBe(before.rowIds[2]);
  });

  it("edits exactly the row it names", () => {
    const state = run(
      start(),
      { type: "setOp", index: 1, op: "crosses_above" },
      { type: "setLeft", index: 0, operand: indOperand("high", null) },
      { type: "setRight", index: 2, operand: { kind: "value", value: 7 } },
    );
    expect(state.rule.conditions[0].left.ind).toBe("high");
    expect(state.rule.conditions[1].op).toBe("crosses_above");
    expect(state.rule.conditions[2].right).toEqual({ kind: "value", value: 7 });
    expect(state.rule.conditions[1].left).toEqual(breakout.rule.conditions[1].left);
  });

  it("ignores edits to a row that does not exist", () => {
    const before = start();
    expect(run(before, { type: "setOp", index: 9, op: "<" })).toBe(before);
  });

  it("stores the name trimmed (decision 11)", () => {
    expect(run(start(), { type: "setName", name: "  My idea  " }).rule.name).toBe("My idea");
  });

  it("clears dirty on ran but stays custom, so the link stays ?r=", () => {
    const state = run(start(), { type: "add" }, { type: "ran" });
    expect(state.dirty).toBe(false);
    expect(state.source).toBe("custom");
  });

  it("load replaces everything and starts clean", () => {
    const pullback = mocks.templates.find((t) => t.id === "pullback_ema21")!;
    const state = run(
      start(),
      { type: "add" },
      {
        type: "load",
        rule: pullback.rule,
        source: { template: pullback.id },
      },
    );
    expect(state.rule).toBe(pullback.rule);
    expect(state.rowIds).toHaveLength(pullback.rule.conditions.length);
    expect(state.dirty).toBe(false);
  });
});

describe("field defaults (decision 9)", () => {
  it("gives price fields a null n, rs its catalog default, and others 14", () => {
    expect(defaultN("close", catalog)).toBeNull();
    expect(defaultN("volume", catalog)).toBeNull();
    expect(defaultN("rs", catalog)).toBe(126);
    expect(defaultN("rsi", catalog)).toBe(14);
    expect(defaultN("highest", catalog)).toBe(14);
  });

  it("keeps offset and mult when the indicator changes, and resets n", () => {
    const op = { kind: "ind" as const, ind: "highest" as const, n: 252, offset: 1, mult: 1.5 };
    expect(withIndicator(op, "close", catalog)).toEqual({ ...op, ind: "close", n: null });
    expect(withIndicator(op, "rs", catalog)).toEqual({ ...op, ind: "rs", n: 126 });
  });

  it("switches the right side to sma(50) or to 0, keeping nothing", () => {
    expect(switchRightKind("ind")).toEqual(indOperand("sma", 50));
    expect(switchRightKind("value")).toEqual({ kind: "value", value: 0 });
  });
});

describe("builderReducer edges (AC-5, decisions 9 and 11)", () => {
  const rows = (count: number) =>
    initBuilder(
      { name: "r", conditions: Array.from({ length: count }, () => newCondition()) },
      "custom",
    );

  it("returns the same state for add at 8 rows, so a clean rule stays clean", () => {
    const before = rows(8);
    const after = run(before, { type: "add" });
    expect(after).toBe(before);
    expect(after.dirty).toBe(false);
  });

  it("allows the 8th row and refuses only the 9th", () => {
    const eight = run(rows(7), { type: "add" });
    expect(eight.rule.conditions).toHaveLength(8);
    expect(run(eight, { type: "add" })).toBe(eight);
  });

  it("returns the same state for remove on the last row, so it stays clean", () => {
    const before = rows(1);
    const after = run(before, { type: "remove", index: 0 });
    expect(after).toBe(before);
    expect(after.dirty).toBe(false);
  });

  it("ignores a remove whose index is out of range", () => {
    const before = start();
    expect(run(before, { type: "remove", index: 3 })).toBe(before);
    expect(run(before, { type: "remove", index: -1 })).toBe(before);
  });

  it.each([
    ["setOp", { type: "setOp", index: 0, op: "<" }],
    ["setLeft", { type: "setLeft", index: 0, operand: indOperand("open", null) }],
    ["setRight", { type: "setRight", index: 0, operand: { kind: "value", value: 1 } }],
    ["setName", { type: "setName", name: "Mine" }],
  ] as const)("marks the rule custom and dirty on %s", (_label, action) => {
    const state = run(start(), action);
    expect(state.source).toBe("custom");
    expect(state.dirty).toBe(true);
  });

  it("stores a name of only spaces as empty, for the server's 422 to judge (decision 6)", () => {
    expect(run(start(), { type: "setName", name: "   " }).rule.name).toBe("");
  });

  it("trims only the ends of a 40 character name (decision 11)", () => {
    const forty = "a".repeat(19) + "  " + "b".repeat(19);
    expect(run(start(), { type: "setName", name: `\t${forty} \n` }).rule.name).toBe(forty);
  });

  it("load with dirty keeps it dirty and custom, as a pasted rule does", () => {
    const state = run(start(), { type: "load", rule: rows(1).rule, source: "custom", dirty: true });
    expect(state.dirty).toBe(true);
    expect(state.source).toBe("custom");
    expect(state.rowIds).toEqual(["r0"]);
  });

  it("the right side switch replaces the old operand, whatever it held (decision 9)", () => {
    const custom = { kind: "ind" as const, ind: "rsi" as const, n: 21, offset: 3, mult: 2 };
    const state = run(
      initBuilder(
        { name: "r", conditions: [{ left: indOperand("close", null), op: ">", right: custom }] },
        "custom",
      ),
      { type: "setRight", index: 0, operand: switchRightKind("value") },
      { type: "setRight", index: 0, operand: switchRightKind("ind") },
    );
    expect(state.rule.conditions[0].right).toEqual(indOperand("sma", 50));
  });
});

describe("withIndicator n resets (decision 9)", () => {
  it("gives a price field turned windowed the fallback 14", () => {
    expect(withIndicator(indOperand("close", null), "sma", catalog).n).toBe(14);
  });

  it("keeps n null when moving between price fields", () => {
    expect(withIndicator(indOperand("close", null), "volume", catalog).n).toBeNull();
  });

  it("resets a custom n even between windowed indicators, or to the same one", () => {
    expect(withIndicator(indOperand("sma", 200), "ema", catalog).n).toBe(14);
    expect(withIndicator(indOperand("sma", 200), "sma", catalog).n).toBe(14);
  });

  it("gives an indicator missing from the catalog a null n", () => {
    expect(defaultN("macd", catalog)).toBeNull();
  });
});
