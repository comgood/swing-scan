import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { LIVE_TEXT, SYNTHETIC_TEXT } from "@/components/shell/data-mode-banner";
import { OVERFIT_WARNING, PROCEDURE_NOTE } from "@/features/honesty";
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
  "Research honesty guards",
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

  it("shows every trial counter state, the procedure note and both data banners (spec 0004 AC-9)", () => {
    render(<Gallery />);
    const section = within(screen.getByRole("region", { name: "Research honesty guards" }));
    const first = within(section.getByRole("group", { name: "First trial" }));
    expect(first.getByText("Trial #1 for this rule structure · 1 this session")).toBeVisible();
    expect(section.getByText("Trial #6 for this rule structure · 14 this session")).toBeVisible();
    expect(section.getByText("Trial #10 for this rule structure · 23 this session")).toBeVisible();
    // Warning at 10, and the static warning when storage is unavailable.
    expect(
      within(section.getByRole("group", { name: "Warning at 10" })).getByText(OVERFIT_WARNING),
    ).toBeVisible();
    const unavailable = within(section.getByRole("group", { name: "Storage unavailable" }));
    expect(unavailable.getByText(OVERFIT_WARNING)).toBeVisible();
    expect(unavailable.queryByText(/Trial #/)).not.toBeInTheDocument();
    expect(section.getByText(PROCEDURE_NOTE)).toBeVisible();
    expect(section.getByText(SYNTHETIC_TEXT)).toBeVisible();
    expect(section.getByText(LIVE_TEXT)).toBeVisible();
  });

  it("lets you drive the live demo to the warning at 10 by keyboard, then reset it", async () => {
    const user = userEvent.setup();
    render(<Gallery />);
    const demo = within(screen.getByRole("group", { name: "Live demo" }));
    expect(
      await demo.findByText("Trial #1 for this rule structure · 1 this session"),
    ).toBeVisible();
    demo.getByRole("button", { name: "Run a numbers only tweak" }).focus();
    for (let i = 0; i < 8; i += 1) await user.keyboard("{Enter}");
    expect(
      await demo.findByText("Trial #9 for this rule structure · 9 this session"),
    ).toBeVisible();
    expect(demo.queryByText(OVERFIT_WARNING)).not.toBeInTheDocument();
    await user.keyboard("{Enter}");
    expect(
      await demo.findByText("Trial #10 for this rule structure · 10 this session"),
    ).toBeVisible();
    expect(demo.getByText(OVERFIT_WARNING)).toBeVisible();
    await user.click(demo.getByRole("button", { name: "Reset the demo" }));
    expect(
      await demo.findByText("Trial #1 for this rule structure · 1 this session"),
    ).toBeVisible();
    expect(demo.queryByText(OVERFIT_WARNING)).not.toBeInTheDocument();
  });
});
