import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { expectNoAxeViolations } from "@/test/axe";

import { PROCEDURE_NOTE, ProcedureNote } from "./procedure-note";

describe("ProcedureNote (U-8, AC-7)", () => {
  it("renders the U-8 copy word for word as one line of text", () => {
    render(<ProcedureNote />);
    expect(PROCEDURE_NOTE).toBe(
      "Trade mode isolates the exit effect. Pick the exit on IS, read OOS once, then confirm with a single portfolio backtest.",
    );
    expect(screen.getByText(PROCEDURE_NOTE)).toBeVisible();
  });

  it("hides its icon from assistive tech and passes axe", async () => {
    const { container } = render(<ProcedureNote />);
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    await expectNoAxeViolations(container);
  });
});
