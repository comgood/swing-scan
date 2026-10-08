import type { Rule } from "@swing-scan/api-client";
import { describe, expect, it } from "vitest";

import { mocks } from "@/mocks/handlers";

import { conditionText, type IndOperand, operandColumns, operandLabel } from "./operands";

function ind(partial: Partial<IndOperand> & Pick<IndOperand, "ind">): IndOperand {
  return { kind: "ind", n: null, offset: 0, mult: 1, ...partial };
}

describe("operandLabel (spec 0002 label grammar)", () => {
  it.each([
    [ind({ ind: "close" }), "close"],
    [ind({ ind: "highest", n: 252, offset: 1 }), "highest(252)[1]"],
    [ind({ ind: "avg_volume", n: 50, mult: 1.5 }), "1.5×avg_volume(50)"],
    [ind({ ind: "ema", n: 21, offset: 5 }), "ema(21)[5]"],
    [ind({ ind: "ema", n: 21, mult: 1.01 }), "1.01×ema(21)"],
    [ind({ ind: "rs", n: 126 }), "rs(126)"],
    [ind({ ind: "rs" }), "rs(126)"],
    [ind({ ind: "sma", n: 50, mult: 2 }), "2.0×sma(50)"],
    [ind({ ind: "low", mult: 0.25 }), "0.25×low"],
  ])("labels %j as %s", (op, label) => {
    expect(operandLabel(op)).toBe(label);
  });
});

describe("operandColumns", () => {
  it("lists left then right operands, skips numbers and dedupes", () => {
    const rule: Rule = {
      name: "r",
      conditions: [
        { left: ind({ ind: "close" }), op: ">", right: { kind: "value", value: 5 } },
        { left: ind({ ind: "close" }), op: ">", right: ind({ ind: "sma", n: 50 }) },
        {
          left: ind({ ind: "sma", n: 50 }),
          op: "crosses_above",
          right: ind({ ind: "sma", n: 200 }),
        },
      ],
    };
    expect(operandColumns(rule).map(operandLabel)).toEqual(["close", "sma(50)", "sma(200)"]);
  });

  it("treats rs without n and rs(126) as one column", () => {
    const rule: Rule = {
      name: "r",
      conditions: [
        { left: ind({ ind: "rs" }), op: ">", right: { kind: "value", value: 80 } },
        { left: ind({ ind: "rs", n: 126 }), op: "<", right: { kind: "value", value: 99 } },
      ],
    };
    expect(operandColumns(rule)).toHaveLength(1);
  });

  it.each(mocks.templates.map((t) => [t.id, t] as const))(
    "gives template %s distinct, non empty columns",
    (_id, template) => {
      const labels = operandColumns(template.rule).map(operandLabel);
      expect(new Set(labels).size).toBe(labels.length);
      expect(labels.length).toBeGreaterThan(0);
    },
  );

  it.each([
    ["scan", mocks.scan],
    ["scan.empty", mocks.scanEmpty],
  ] as const)("has as many columns as the %s mock (Breakout)", (_name, response) => {
    const breakout = mocks.templates.find((t) => t.id === "breakout_52w");
    expect(breakout).toBeDefined();
    const columns = operandColumns(breakout!.rule);
    expect(columns).toHaveLength(response.columns.length);
    expect(columns.map(operandLabel)).toEqual(response.columns);
    for (const row of response.rows) expect(row.operands).toHaveLength(columns.length);
  });
});

describe("conditionText", () => {
  it("shows the visible price filter as close > 5", () => {
    expect(
      conditionText({ left: ind({ ind: "close" }), op: ">", right: { kind: "value", value: 5 } }),
    ).toBe("close > 5");
  });

  it("writes crosses in words", () => {
    expect(
      conditionText({
        left: ind({ ind: "ema", n: 21 }),
        op: "crosses_below",
        right: ind({ ind: "sma", n: 50 }),
      }),
    ).toBe("ema(21) crosses below sma(50)");
  });
});
