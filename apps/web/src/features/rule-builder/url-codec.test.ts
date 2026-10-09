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

  it("puts keys in contract order, so equal rules encode to the same link", () => {
    const shuffled = {
      conditions: [
        {
          right: { value: 5, kind: "value" },
          op: ">",
          left: { mult: 1, offset: 0, n: null, ind: "close", kind: "ind" },
        },
      ],
      name: "r",
    };
    const rule = normaliseRule(shuffled, NAMES)!;
    expect(JSON.stringify(rule)).toBe(
      '{"name":"r","conditions":[{"left":{"kind":"ind","ind":"close","n":null,"offset":0,' +
        '"mult":1},"op":">","right":{"kind":"value","value":5}}]}',
    );
  });
});

describe("the ?r= format (decision 3)", () => {
  /** Node's own base64url of the compact UTF-8 JSON: the format decision 3 names. */
  const reference = (rule: Rule) => Buffer.from(JSON.stringify(rule), "utf8").toString("base64url");

  it("is base64url of the compact UTF-8 JSON, byte for byte", () => {
    expect(encodeRule(EVERY_FIELD)).toBe(reference(EVERY_FIELD));
    const json = Buffer.from(encodeRule(EVERY_FIELD), "base64url").toString("utf8");
    expect(json).toBe(JSON.stringify(EVERY_FIELD));
    expect(json).not.toMatch(/\n|": /);
  });

  it.each(["r", "ru", "rul", "rule"])("never pads, whatever the length (name %s)", (name) => {
    const rule = { ...EVERY_FIELD, name };
    const encoded = encodeRule(rule);
    expect(encoded).not.toContain("=");
    expect(encoded).toBe(reference(rule));
    expect(decodeRule(encoded, NAMES)).toEqual(rule);
  });

  it.each([
    ["accents", "Café crème à la carte"],
    ["CJK", "突破 52 週高値"],
    ["emoji outside the BMP", "🚀📈🧪"],
    ["right to left", "قاعدة الاختراق"],
    ["quotes and slashes", 'say "hi" \\ / <b>'],
  ])("round trips a name with %s as UTF-8", (_label, name) => {
    const rule = { ...EVERY_FIELD, name };
    expect(encodeRule(rule)).toBe(reference(rule));
    expect(decodeRule(encodeRule(rule), NAMES)?.name).toBe(name);
  });

  it("decodes a link built by another base64url encoder", () => {
    const rule = mocks.templates[0].rule;
    expect(decodeRule(reference(rule), NAMES)).toEqual(rule);
  });

  it.each([
    ["padded", () => encodeRaw({ ...EVERY_FIELD, name: "r" }) + "="],
    ["standard base64 (+ and /)", () => btoa("ûÿ¿")],
    ["a length that no base64 has", () => "AAAAA"],
    ["a name that is a number", () => encodeRaw({ ...EVERY_FIELD, name: 7 })],
    [
      "a value that is a string",
      () => {
        const c = EVERY_FIELD.conditions[1];
        return encodeRaw({
          name: "r",
          conditions: [{ ...c, right: { kind: "value", value: "5" } }],
        });
      },
    ],
    [
      "a fractional n",
      () => {
        const c = EVERY_FIELD.conditions[0];
        return encodeRaw({ name: "r", conditions: [{ ...c, left: { ...c.left, n: 2.5 } }] });
      },
    ],
    ["JSON null", () => encodeRaw(null)],
    ["a JSON array", () => encodeRaw([EVERY_FIELD])],
  ])("returns null for %s, so the page falls back to Breakout (decision 4)", (_label, make) => {
    expect(decodeRule(make(), NAMES)).toBeNull();
  });
});
