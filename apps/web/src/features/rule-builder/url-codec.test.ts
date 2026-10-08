// covers: spec 0008 AC-1 (round trip), AC-3 (bad links), the is-rule shape guard
import type { Rule } from "@swing-scan/api-client";
import { describe, expect, it } from "vitest";

import { mocks } from "@/mocks/handlers";

import { normaliseRule } from "./is-rule";
import { decodeRule, encodeRule, MAX_ENCODED_LENGTH } from "./url-codec";

const NAMES = mocks.indicators.map((s) => s.name);

const EVERY_FIELD: Rule = {
  name: "Ünïcode rule ✓ 🚀",
  conditions: [
    {
      left: { kind: "ind", ind: "ema", n: 21, offset: 3, mult: 1.01 },
      op: "crosses_above",
      right: { kind: "ind", ind: "sma", n: 50, offset: 0, mult: 1 },
    },
    {
      left: { kind: "ind", ind: "close", n: null, offset: 0, mult: 1 },
      op: "<=",
      right: { kind: "value", value: -2.5 },
    },
    {
      left: { kind: "ind", ind: "rs", n: 126, offset: 20, mult: 0.1 },
      op: "crosses_below",
      right: { kind: "ind", ind: "rsi", n: 14, offset: 1, mult: 10 },
    },
  ],
};

function encodeRaw(value: unknown): string {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

describe("encodeRule and decodeRule (AC-1)", () => {
  it.each(mocks.templates.map((t) => [t.id, t.rule] as const))(
    "round trips template %s exactly",
    (_id, rule) => {
      expect(decodeRule(encodeRule(rule), NAMES)).toEqual(rule);
    },
  );

  it("round trips a rule using every field, with any characters in the name", () => {
    const encoded = encodeRule(EVERY_FIELD);
    expect(encoded).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(decodeRule(encoded, NAMES)).toEqual(EVERY_FIELD);
  });

  it("serialises to JSON and back unchanged", () => {
    expect(JSON.parse(JSON.stringify(EVERY_FIELD))).toEqual(EVERY_FIELD);
  });

  it("fills a missing n with null so the rule equals the template form", () => {
    const rule = {
      name: "r",
      conditions: [
        {
          left: { kind: "ind", ind: "close", offset: 0, mult: 1 },
          op: ">",
          right: { kind: "value", value: 5 },
        },
      ],
    };
    expect(decodeRule(encodeRaw(rule), NAMES)?.conditions[0].left.n).toBeNull();
  });
});

describe("decodeRule rejects bad links (AC-3)", () => {
  const base = EVERY_FIELD.conditions[1];
  it.each([
    ["empty", ""],
    ["not base64url", "abc$%"],
    ["not JSON", encodeRaw("x").slice(0, 2) + "@@"],
    ["too long", "A".repeat(MAX_ENCODED_LENGTH + 1)],
    ["invalid UTF-8", "_w"],
    ["JSON that is not a rule", encodeRaw({ hello: 1 })],
    ["zero conditions", encodeRaw({ name: "r", conditions: [] })],
    ["nine conditions", encodeRaw({ name: "r", conditions: Array(9).fill(base) })],
    ["an unknown key", encodeRaw({ ...EVERY_FIELD, extra: true })],
    [
      "an unknown indicator",
      encodeRaw({ name: "r", conditions: [{ ...base, left: { ...base.left, ind: "macd" } }] }),
    ],
    ["an unknown operator", encodeRaw({ name: "r", conditions: [{ ...base, op: "==" }] })],
    [
      "a fractional offset",
      encodeRaw({ name: "r", conditions: [{ ...base, left: { ...base.left, offset: 1.5 } }] }),
    ],
    [
      "a value operand on the left",
      encodeRaw({ name: "r", conditions: [{ ...base, left: { kind: "value", value: 1 } }] }),
    ],
    ["a missing name", encodeRaw({ conditions: [base] })],
  ])("returns null for %s", (_label, text) => {
    expect(decodeRule(text, NAMES)).toBeNull();
  });
});

describe("normaliseRule", () => {
  it("leaves ranges to the server: an out of range n still has the rule shape", () => {
    const rule = structuredClone(EVERY_FIELD);
    rule.conditions[2].right = { kind: "ind", ind: "rsi", n: 60, offset: 25, mult: 50 };
    expect(normaliseRule(rule, NAMES)).toEqual(rule);
  });
});
