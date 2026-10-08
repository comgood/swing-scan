// Rule operands as the scan shows them (spec 0005, spec 0002 value sourcing). The labels follow
// spec 0002's grammar `[{mult}×]{ind}[({n})][[{offset}]]`, so the conditions text reads the same
// as the `columns` the API sends. Formats are picked from the operand, never parsed from a label.
import type { Rule, Schemas } from "@swing-scan/api-client";

export type IndOperand = Schemas["IndOperand"];
export type Condition = Schemas["Condition"];
export type Operator = Condition["op"];

/** `rs` without `n` is filled in as 126 by the validator (spec 0002 AC-7). */
const RS_DEFAULT_N = 126;

function filledN(op: IndOperand): number | null {
  if (op.n !== null && op.n !== undefined) return op.n;
  return op.ind === "rs" ? RS_DEFAULT_N : null;
}

/**
 * Python's shortest float repr for `mult` (bounded to 0.1 to 10 by the contract, so it never
 * needs an exponent): JavaScript drops the `.0` of a whole number, Python keeps it.
 */
function pythonFloat(value: number): string {
  return Number.isInteger(value) ? `${value}.0` : String(value);
}

/** `close`, `highest(252)[1]`, `1.5×avg_volume(50)`, `rs(126)`. */
export function operandLabel(op: IndOperand): string {
  const mult = op.mult ?? 1;
  const n = filledN(op);
  const offset = op.offset ?? 0;
  return [
    mult !== 1 ? `${pythonFloat(mult)}×` : "",
    op.ind,
    n !== null ? `(${n})` : "",
    offset > 0 ? `[${offset}]` : "",
  ].join("");
}

function operandKey(op: IndOperand): string {
  return JSON.stringify([op.ind, filledN(op), op.offset ?? 0, op.mult ?? 1]);
}

/**
 * The indicator operands of a rule in the order the scan's `columns` list them: each condition's
 * left then right operand, number operands skipped, deduped by `(ind, n, offset, mult)`.
 */
export function operandColumns(rule: Rule): IndOperand[] {
  const seen = new Set<string>();
  const columns: IndOperand[] = [];
  for (const condition of rule.conditions) {
    for (const op of [condition.left, condition.right]) {
      if (op.kind !== "ind") continue;
      const key = operandKey(op);
      if (seen.has(key)) continue;
      seen.add(key);
      columns.push(op);
    }
  }
  return columns;
}

export const OPERATOR_TEXT: Record<Operator, string> = {
  ">": ">",
  "<": "<",
  ">=": ">=",
  "<=": "<=",
  crosses_above: "crosses above",
  crosses_below: "crosses below",
};

/** `close > highest(252)[1]`, `close > 5`, `ema(21) crosses above sma(50)`. */
export function conditionText(condition: Condition): string {
  const right =
    condition.right.kind === "value"
      ? String(condition.right.value)
      : operandLabel(condition.right);
  return `${operandLabel(condition.left)} ${OPERATOR_TEXT[condition.op]} ${right}`;
}
