import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { LIVE_TEXT, SYNTHETIC_TEXT } from "@/components/shell/data-mode-banner";
import { GUIDE_SOURCE } from "@/features/exit-lab";
import { OVERFIT_WARNING, PROCEDURE_NOTE } from "@/features/honesty";
import { BAD_LINK_NOTICE, STALE_TEXT } from "@/features/rule-builder";
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
  "Backtest report",
  "Exit lab",
  "Rule builder",
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

  // Axe on a dense section (the rule builder's states) takes about 5 s on the CI runner,
  // right at Vitest's default timeout; a timed out run also leaves axe busy for the next test.
  it.each(SECTIONS)(
    "section %s passes axe",
    async (name) => {
      render(<Gallery />);
      await expectNoAxeViolations(screen.getByRole("region", { name }));
    },
    20_000,
  );

  it("maps the sample 422 to the field and the form summary", () => {
    render(<Gallery />);
    expect(screen.getByLabelText("Cooldown (bars)")).toHaveAccessibleDescription(
      expect.stringContaining("Must be between 2 and 260"),
    );
    expect(screen.getByText("Rule needs at least one condition")).toBeInTheDocument();
  });

  it("shows every trial counter state and both data banners, and the procedure note once (spec 0004 AC-9)", () => {
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
    // The procedure note is shown once, in place under the exit lab table.
    expect(section.queryByText(PROCEDURE_NOTE)).not.toBeInTheDocument();
    expect(screen.getAllByText(PROCEDURE_NOTE)).toHaveLength(1);
    expect(section.getByText(SYNTHETIC_TEXT)).toBeVisible();
    expect(section.getByText(LIVE_TEXT)).toBeVisible();
  });

  it("shows the backtest parts, with the truncated trade count (spec 0007)", async () => {
    render(<Gallery />);
    const section = within(screen.getByRole("region", { name: "Backtest report" }));
    expect(section.getByRole("heading", { name: "Assumptions" })).toBeVisible();
    expect(await section.findByText(/^Trial #1 for this rule structure/)).toBeVisible();
    expect(section.getByRole("columnheader", { name: "Benchmark OOS" })).toBeVisible();
    expect(section.getByText(/^Showing 12 of 2,600 trades/)).toBeVisible();
    expect(section.getByRole("img", { name: /^Strategy equity from 100/ })).toBeVisible();
    expect(section.getAllByText("n/a").length).toBeGreaterThan(0);
  });

  it("shows the exit lab parts (spec 0009 AC-13 to AC-17)", async () => {
    const user = userEvent.setup();
    render(<Gallery />);
    const section = within(screen.getByRole("region", { name: "Exit lab" }));
    expect(section.getAllByText("Best IS").length).toBeGreaterThan(0);
    expect(section.getByText("Horizon over 10%")).toBeVisible();
    expect(section.getByText(/^\* R needs a stop\. "Demo MA, no stop" has no stop/)).toBeVisible();
    expect(section.getByText(PROCEDURE_NOTE)).toBeVisible();
    expect(section.getByText(GUIDE_SOURCE)).toBeVisible();
    const toggle = section.getByRole("button", { name: "Random entries for Demo stop" });
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });

  it("shows every rule builder state (spec 0008 AC-10)", () => {
    render(<Gallery />);
    const state = (name: string) => within(screen.getByRole("group", { name }));
    expect(
      state("One default row (remove disabled)").getByRole("button", {
        name: "Remove condition 1",
      }),
    ).toBeDisabled();
    expect(
      state("Number and indicator right sides").getAllByRole("combobox", { name: "Compare with" }),
    ).toHaveLength(2);
    expect(
      state("Eight rows (add disabled)").getByRole("button", { name: "Add condition" }),
    ).toBeDisabled();
    expect(state("422 on a right side n").getByText("Must be between 2 and 252")).toBeVisible();
    expect(state("Stale results").getByText(STALE_TEXT)).toBeVisible();
    expect(state("Bad link notice").getByText(BAD_LINK_NOTICE)).toBeVisible();
    expect(state("JSON panel with Not a rule").getByText("Not a rule")).toBeVisible();
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
