// covers: spec 0008 AC-6 (every field), AC-7 / U-7 (a 422 lands on a visible field), and doc 01
// section 6.8 (the three form labels keep their wording and gain one plain line).
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mocks } from "@/mocks/handlers";

import { OperandFields } from "./operand-fields";
import type { IndOperand } from "./reducer";

const catalog = mocks.indicators;
const windowed = catalog.find((s) => s.windowed)!;
const priceField = catalog.find((s) => !s.windowed)!;

function setup(ind: string, errors: { ind?: string; n?: string } = {}) {
  const operand = { kind: "ind", ind, n: 20, offset: 0, mult: 1 } as IndOperand;
  return render(
    <OperandFields operand={operand} catalog={catalog} onChange={() => {}} errors={errors} />,
  );
}

describe("OperandFields", () => {
  it("explains the three inputs a beginner cannot guess, keeping their labels", () => {
    setup(windowed.name);
    expect(screen.getByLabelText("Window (n)")).toHaveAccessibleDescription(
      expect.stringContaining("How many bars the indicator averages or looks back over."),
    );
    expect(screen.getByLabelText("Bars back")).toHaveAccessibleDescription(
      expect.stringContaining("0 is today's bar, 1 is the bar before it."),
    );
    expect(screen.getByLabelText("Multiplier (×)")).toHaveAccessibleDescription(
      expect.stringContaining("Scales the value. 1 leaves it unchanged."),
    );
  });

  it("leaves no dangling hint where a price field has no window", () => {
    setup(priceField.name);
    expect(screen.queryByLabelText("Window (n)")).not.toBeInTheDocument();
    expect(screen.queryByText(/window/i)).not.toBeInTheDocument();
  });

  it("shows a 422 on n beside the indicator when the window has no field (U-7)", () => {
    setup(priceField.name, { n: "Must be between 2 and 50" });
    expect(screen.getByLabelText("Field")).toHaveAccessibleDescription(
      expect.stringContaining("Must be between 2 and 50"),
    );
  });

  it("keeps a 422 on the indicator itself when both arrive", () => {
    setup(priceField.name, { ind: "Unknown indicator", n: "Must be between 2 and 50" });
    expect(screen.getByLabelText("Field")).toHaveAccessibleDescription(
      expect.stringContaining("Unknown indicator"),
    );
  });
});
