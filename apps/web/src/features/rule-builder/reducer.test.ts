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
