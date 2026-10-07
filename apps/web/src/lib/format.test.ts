import { describe, expect, it } from "vitest";

import { formatDate, formatInt, formatNumber, formatPct, formatPrice, formatR } from "./format";

describe("formatters (AC-12)", () => {
  it("formats percents with a sign, never multiplying by 100", () => {
    expect(formatPct(3.254)).toBe("+3.25%");
    expect(formatPct(-1.1)).toBe("-1.10%");
    expect(formatPct(0.001)).toBe("0.00%");
    expect(formatPct(-0.004)).toBe("0.00%");
    expect(formatPct(12.5, { decimals: 1 })).toBe("+12.5%");
    expect(formatPct(1234.5)).toBe("+1,234.50%");
  });

  it("formats numbers, R multiples, prices and integers with separators", () => {
    expect(formatNumber(1234567.891)).toBe("1,234,567.89");
    expect(formatNumber(-0.001)).toBe("0.00");
    expect(formatR(1.32)).toBe("1.32R");
    expect(formatR(-0.5)).toBe("-0.50R");
    expect(formatPrice(2310)).toBe("2,310.00");
    expect(formatInt(1499.6)).toBe("1,500");
    expect(formatInt(-0.4)).toBe("0");
  });

  it("uses the ASCII hyphen minus for negatives", () => {
    expect(formatNumber(-5).charCodeAt(0)).toBe(45);
  });

  it.each([null, undefined, Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY])(
    "shows n/a for %s",
    (v) => {
      expect(formatPct(v)).toBe("n/a");
      expect(formatNumber(v)).toBe("n/a");
      expect(formatR(v)).toBe("n/a");
      expect(formatPrice(v)).toBe("n/a");
      expect(formatInt(v)).toBe("n/a");
    },
  );

  it("passes API dates through unchanged", () => {
    expect(formatDate("2024-01-22")).toBe("2024-01-22");
    expect(formatDate(null)).toBe("n/a");
  });
});
