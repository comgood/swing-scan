// The rule builder's one state (spec 0008 decision 2): the contract `Rule` itself, plus stable
// row ids for React keys. Nothing else holds the rule, so the scan request is `state.rule`.
import type { IndicatorSpec, Rule, Schemas } from "@swing-scan/api-client";

import { MAX_CONDITIONS } from "./is-rule";

export type Condition = Schemas["Condition"];
export type IndOperand = Schemas["IndOperand"];
export type RightOperand = Condition["right"];
export type Operator = Condition["op"];

export type RuleSource = { template: string } | "custom";

export interface BuilderState {
  rule: Rule;
  rowIds: string[];
  source: RuleSource;
  /** Edited since the rule was loaded or last run. */
  dirty: boolean;
  nextId: number;
}

export type BuilderAction =
  /** `dirty` marks a load that counts as an edit (a pasted rule), so it waits for "Run scan". */
  | { type: "load"; rule: Rule; source: RuleSource; dirty?: boolean }
  | { type: "add" }
  | { type: "remove"; index: number }
  | { type: "setLeft"; index: number; operand: IndOperand }
  | { type: "setOp"; index: number; op: Operator }
  | { type: "setRight"; index: number; operand: RightOperand }
  | { type: "setName"; name: string }
  | { type: "ran" };

/** Builder constants, not catalog values (decision 9): 14 fits every windowed range. */
export const FALLBACK_N = 14;
export const DEFAULT_NAME = "My rule";

export function indOperand(ind: IndOperand["ind"], n: number | null): IndOperand {
  return { kind: "ind", ind, n, offset: 0, mult: 1 };
}

/** A new row reads `close > sma(50)` (decision 8). */
export function newCondition(): Condition {
  return { left: indOperand("close", null), op: ">", right: indOperand("sma", 50) };
}

/** `n` after picking `ind`: null for a price field, else the catalog default, else 14. */
export function defaultN(ind: string, catalog: readonly IndicatorSpec[]): number | null {
  const spec = catalog.find((s) => s.name === ind);
  if (!spec?.windowed) return null;
  return spec.n_default ?? FALLBACK_N;
}

/** The operand with a new indicator; offset and mult stay, `n` resets (decision 9). */
export function withIndicator(
  operand: IndOperand,
  ind: IndOperand["ind"],
  catalog: readonly IndicatorSpec[],
): IndOperand {
  return { ...operand, ind, n: defaultN(ind, catalog) };
}

/** Number to Indicator starts at `sma(50)`, Indicator to Number at 0 (decision 9). */
export function switchRightKind(kind: RightOperand["kind"]): RightOperand {
  return kind === "value" ? { kind: "value", value: 0 } : indOperand("sma", 50);
}

export function initBuilder(rule: Rule, source: RuleSource): BuilderState {
  return {
    rule,
    rowIds: rule.conditions.map((_, i) => `r${i}`),
    source,
    dirty: false,
    nextId: rule.conditions.length,
  };
}

function editRow(state: BuilderState, index: number, row: Partial<Condition>): BuilderState {
  if (index < 0 || index >= state.rule.conditions.length) return state;
  const conditions = state.rule.conditions.map((c, i) => (i === index ? { ...c, ...row } : c));
  return { ...state, rule: { ...state.rule, conditions }, source: "custom", dirty: true };
}

export function builderReducer(state: BuilderState, action: BuilderAction): BuilderState {
  switch (action.type) {
    case "load":
      return { ...initBuilder(action.rule, action.source), dirty: action.dirty ?? false };
    case "add": {
      if (state.rule.conditions.length >= MAX_CONDITIONS) return state;
      return {
        ...state,
        rule: { ...state.rule, conditions: [...state.rule.conditions, newCondition()] },
        rowIds: [...state.rowIds, `r${state.nextId}`],
        nextId: state.nextId + 1,
        source: "custom",
        dirty: true,
      };
    }
    case "remove": {
      const count = state.rule.conditions.length;
      if (count <= 1 || action.index < 0 || action.index >= count) return state;
      return {
        ...state,
        rule: {
          ...state.rule,
          conditions: state.rule.conditions.filter((_, i) => i !== action.index),
        },
        rowIds: state.rowIds.filter((_, i) => i !== action.index),
        source: "custom",
        dirty: true,
      };
    }
    case "setLeft":
      return editRow(state, action.index, { left: action.operand });
    case "setOp":
      return editRow(state, action.index, { op: action.op });
    case "setRight":
      return editRow(state, action.index, { right: action.operand });
    case "setName":
      return {
        ...state,
        rule: { ...state.rule, name: action.name.trim() },
        source: "custom",
        dirty: true,
      };
    case "ran":
      return { ...state, dirty: false };
  }
}
