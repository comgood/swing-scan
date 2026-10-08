// A shape guard for rules from untrusted text (a `?r=` link or the JSON panel), spec 0008.
// It checks shape only; ranges are the server's 422 to report. A missing `n` is filled with
// `null` first, so a decoded rule compares equal to one from `GET /templates`.
import type { Rule, Schemas } from "@swing-scan/api-client";

type Condition = Schemas["Condition"];
type Operator = Condition["op"];

export const OPERATORS: readonly Operator[] = [
  ">",
  "<",
  ">=",
  "<=",
  "crosses_above",
  "crosses_below",
];

export const MAX_CONDITIONS = 8;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function onlyKeys(value: Record<string, unknown>, allowed: readonly string[]): boolean {
  return Object.keys(value).every((key) => allowed.includes(key));
}

const isWhole = (v: unknown): v is number => typeof v === "number" && Number.isInteger(v);
const isFiniteNumber = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

function normalOperand(value: unknown, names: readonly string[], allowValue: boolean): unknown {
  if (!isObject(value)) return undefined;
  if (value.kind === "value" && allowValue) {
    return onlyKeys(value, ["kind", "value"]) && isFiniteNumber(value.value)
      ? { kind: "value", value: value.value }
      : undefined;
  }
  if (value.kind !== "ind" || !onlyKeys(value, ["kind", "ind", "n", "offset", "mult"])) {
    return undefined;
  }
  const n = value.n ?? null;
  const ok =
    typeof value.ind === "string" &&
    names.includes(value.ind) &&
    (n === null || isWhole(n)) &&
    isWhole(value.offset) &&
    isFiniteNumber(value.mult);
  return ok
    ? { kind: "ind", ind: value.ind, n, offset: value.offset, mult: value.mult }
    : undefined;
}

/** The rule in canonical form (keys in contract order, `n` filled), or null if not a rule. */
export function normaliseRule(value: unknown, names: readonly string[]): Rule | null {
  if (!isObject(value) || !onlyKeys(value, ["name", "conditions"])) return null;
  const { name, conditions } = value;
  if (typeof name !== "string" || !Array.isArray(conditions)) return null;
  if (conditions.length < 1 || conditions.length > MAX_CONDITIONS) return null;
  const out: Condition[] = [];
  for (const c of conditions) {
    if (!isObject(c) || !onlyKeys(c, ["left", "op", "right"])) return null;
    const left = normalOperand(c.left, names, false);
    const right = normalOperand(c.right, names, true);
    if (!left || !right || !OPERATORS.includes(c.op as Operator)) return null;
    out.push({ left, op: c.op, right } as Condition);
  }
  return { name, conditions: out };
}
