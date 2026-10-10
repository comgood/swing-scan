// covers: AC-12, AC-16 (every Assumptions field on screen in plain words, trial counter beside it)
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { memoryStores } from "@/features/honesty/memory-stores";
import { mocks } from "@/mocks/handlers";
import { expectNoAxeViolations } from "@/test/axe";

import { assumptionLines } from "./assumption-labels";
import { AssumptionsHeader } from "./assumptions-header";

const result = mocks.backtestPortfolio;

describe("AssumptionsHeader", () => {
  it("lists every field as a label and a value, in the map's order", async () => {
    const { container } = render(<AssumptionsHeader result={result} stores={memoryStores()} />);
    const header = screen.getByRole("region", { name: "Assumptions" });
    const lines = assumptionLines(result.assumptions);

    const labels = [...header.querySelectorAll("dt")].map((dt) => dt.textContent);
    const values = [...header.querySelectorAll("dd")].map((dd) => dd.textContent);
    expect(labels).toEqual(lines.map((line) => line.label));
    expect(values).toEqual(lines.map((line) => line.text));
    // Nothing is collapsed behind a disclosure: honesty copy is never fine print (design.md).
    expect(header.querySelector("details")).toBeNull();
    await expectNoAxeViolations(container);
  });

  it("puts the trial counter beside the heading", async () => {
    render(<AssumptionsHeader result={result} stores={memoryStores()} />);
    const header = screen.getByRole("region", { name: "Assumptions" });
    expect(within(header).getByRole("heading", { name: "Assumptions", level: 2 })).toBeVisible();
    expect(
      await within(header).findByText(/^Trial #1 for this rule structure/),
    ).toBeInTheDocument();
  });
});
