import type { ScanRequest } from "@swing-scan/api-client";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { mocks } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { expectNoAxeViolations } from "@/test/axe";
import { renderWithQuery } from "@/test/render";

import { pickTemplate, ScanWorkspace } from "./scan-workspace";

const breakout = mocks.templates.find((t) => t.id === "breakout_52w")!;
const pullback = mocks.templates.find((t) => t.id === "pullback_ema21")!;

/** Records every scan body, answering with the default mock. */
function recordScans() {
  const bodies: ScanRequest[] = [];
  server.use(
    http.post("*/api/v1/scan", async ({ request }) => {
      bodies.push((await request.json()) as ScanRequest);
      return HttpResponse.json(mocks.scan);
    }),
  );
  return bodies;
}

describe("pickTemplate", () => {
  it("returns the requested template", () => {
    expect(pickTemplate(mocks.templates, "pullback_ema21")?.id).toBe("pullback_ema21");
  });

  it.each([null, undefined, "nope"])("falls back to Breakout for %s", (id) => {
    expect(pickTemplate(mocks.templates, id)?.id).toBe("breakout_52w");
  });

  it("falls back to the first template when Breakout is missing", () => {
    expect(pickTemplate([pullback], "nope")?.id).toBe("pullback_ema21");
  });
});

// covers: AC-9 (first visit), AC-13 (visible price filter, rule sent as is)
describe("ScanWorkspace", () => {
  it("opens on Breakout with its conditions and today's hits", async () => {
    const bodies = recordScans();
    renderWithQuery(<ScanWorkspace />);

    const select = await screen.findByLabelText("Template");
    expect(select).toHaveValue("breakout_52w");
    expect(
      within(select)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(mocks.templates.map((t) => t.name));

    const conditions = screen.getByRole("list");
    expect(
      within(conditions)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual(["close > highest(252)[1]", "volume > 1.5×avg_volume(50)", "close > 5"]);

    expect(
      await screen.findByRole("heading", { name: `Hits on ${mocks.scan.as_of}` }),
    ).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(mocks.scan.rows.length + 1);
    expect(within(table).getByRole("columnheader", { name: /highest\(252\)\[1\]/ })).toBeVisible();

    expect(bodies).toEqual([{ rule: breakout.rule }]);
  });

  it("scans the other template when you switch, with its rule unchanged", async () => {
    const bodies = recordScans();
    const user = userEvent.setup();
    renderWithQuery(<ScanWorkspace />);

    await user.selectOptions(await screen.findByLabelText("Template"), "pullback_ema21");

    expect(screen.getByText(pullback.description)).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(pullback.rule.conditions.length);
    expect(screen.getByText("close > 5")).toBeInTheDocument();
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toEqual({ rule: pullback.rule });
  });

  it("marks today's new entries with a New badge", async () => {
    renderWithQuery(<ScanWorkspace />);
    await screen.findByRole("table");
    const newCount = mocks.scan.rows.filter((r) => r.new_today).length;
    expect(screen.getAllByText("New", { selector: "[data-slot=badge]" })).toHaveLength(newCount);
  });

  it("has no axe violations", async () => {
    const { container } = renderWithQuery(<ScanWorkspace />);
    await screen.findByRole("table");
    await expectNoAxeViolations(container);
  });
});
