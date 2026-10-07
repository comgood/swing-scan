import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SignedValue } from "./signed-value";

// covers: AC-12 (SignedValue: sign always shown for non zero, colour by sign, foreground at zero)
describe("SignedValue (AC-12)", () => {
  it.each([
    [3.254, "pct", "+3.25%", "text-positive"],
    [-1.1, "pct", "-1.10%", "text-negative"],
    [1.32, "r", "+1.32R", "text-positive"],
    [-0.5, "r", "-0.50R", "text-negative"],
    [1234.5, "number", "+1,234.50", "text-positive"],
  ] as const)(
    "renders %s as %s text %s in its gain or loss colour",
    (value, format, text, tone) => {
      render(<SignedValue value={value} format={format} />);
      expect(screen.getByText(text)).toHaveClass(tone, "tabular-nums");
    },
  );

  it.each([0, 0.004, -0.004])(
    "shows %s, which rounds to zero, unsigned in the foreground colour",
    (value) => {
      render(<SignedValue value={value} format="pct" />);
      expect(screen.getByText("0.00%")).toHaveClass("text-foreground");
    },
  );

  it.each([null, undefined, Number.NaN])("shows n/a for %s", (value) => {
    render(<SignedValue value={value} format="r" />);
    expect(screen.getByText("n/a")).toHaveClass("text-foreground");
  });
});
