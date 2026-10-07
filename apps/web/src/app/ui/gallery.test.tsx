import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { expectNoAxeViolations } from "@/test/axe";

import { Gallery } from "./gallery";

const SECTIONS = [
  "Buttons",
  "Form controls",
  "Number input",
  "Server errors (422)",
  "Numbers and badges",
  "Data table",
  "Banners",
  "Loading",
  "Error states",
  "Empty state, card, separator",
];

describe("/ui gallery (AC-15, AC-16)", () => {
  it("renders every section", () => {
    render(<Gallery />);
    for (const name of SECTIONS) {
      expect(screen.getByRole("region", { name })).toBeInTheDocument();
    }
  });

  it.each(SECTIONS)("section %s passes axe", async (name) => {
    render(<Gallery />);
    await expectNoAxeViolations(screen.getByRole("region", { name }));
  });

  it("maps the sample 422 to the field and the form summary", () => {
    render(<Gallery />);
    expect(screen.getByLabelText("Cooldown (bars)")).toHaveAccessibleDescription(
      expect.stringContaining("Must be between 2 and 260"),
    );
    expect(screen.getByText("Rule needs at least one condition")).toBeInTheDocument();
  });
});
