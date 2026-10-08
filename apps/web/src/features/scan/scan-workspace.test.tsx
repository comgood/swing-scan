import type { ScanRequest } from "@swing-scan/api-client";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { decodeRule, STALE_TEXT } from "@/features/rule-builder";
import { mocks, scanHandler } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { expectNoAxeViolations } from "@/test/axe";
import { renderWithQuery } from "@/test/render";

import { pickTemplate, REJECTED_TEXT, ScanWorkspace } from "./scan-workspace";

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

const NAMES = mocks.indicators.map((s) => s.name);

/** The builder's condition rows (spec 0008), each with its one line text. */
const conditionRows = () => screen.getAllByRole("group", { name: /^Condition \d$/ });
const rowText = (row: HTMLElement) => row.querySelector("p.font-mono")?.textContent;
const side = (n: number, name: "Left side" | "Right side") =>
  within(screen.getByRole("group", { name: `Condition ${n}` })).getByRole("group", { name });

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

    expect(conditionRows().map(rowText)).toEqual([
      "close > highest(252)[1]",
      "volume > 1.5×avg_volume(50)",
      "close > 5",
    ]);

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
    expect(conditionRows()).toHaveLength(pullback.rule.conditions.length);
    expect(screen.getByText("close > 5")).toBeInTheDocument();
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toEqual({ rule: pullback.rule });
  });
});

// covers: spec 0008 AC-4 (the request is the rows), AC-7 (422 on its field), AC-8 (edits wait
// for Run scan, stale results labelled), decision 12 (Backtest this rule)
describe("ScanWorkspace with the rule builder", () => {
  async function editRow3To(user: ReturnType<typeof userEvent.setup>, value: string) {
    const number = within(side(3, "Right side")).getByLabelText("Number");
    await user.clear(number);
    await user.type(number, `${value}{Enter}`);
  }

  it("runs an edit only on Run scan, labelling the old results stale until then", async () => {
    const bodies = recordScans();
    const user = userEvent.setup();
    renderWithQuery(<ScanWorkspace />);
    await screen.findByRole("table");
    expect(screen.queryByText(STALE_TEXT)).not.toBeInTheDocument();

    await editRow3To(user, "10");
    expect(screen.getByText(STALE_TEXT)).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByLabelText("Template")).toHaveValue("");
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(bodies).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "Run scan" }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    const conditions = breakout.rule.conditions.map((c, i) =>
      i === 2 ? { ...c, right: { kind: "value", value: 10 } } : c,
    );
    expect(bodies[1]).toEqual({ rule: { ...breakout.rule, conditions } });
    await waitFor(() => expect(screen.queryByText(STALE_TEXT)).not.toBeInTheDocument());
  });

  it("puts a 422 on the field its loc names and keeps the rule as typed", async () => {
    server.use(scanHandler("422.rule.n_out_of_range"));
    const user = userEvent.setup();
    renderWithQuery(<ScanWorkspace />);
    await user.selectOptions(await screen.findByLabelText("Template"), "pullback_ema21");

    const n = within(side(1, "Left side")).getByLabelText("Window (n)");
    await waitFor(() => expect(n).toHaveAttribute("aria-invalid", "true"));
    expect(within(side(1, "Left side")).getByText("Must be between 2 and 50")).toBeVisible();
    expect(n).toHaveValue("21");
    expect(screen.getByText(REJECTED_TEXT)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("runs the same rule again on Run scan after a 422", async () => {
    let calls = 0;
    server.use(
      http.post("*/api/v1/scan", () => {
        calls += 1;
        return calls === 1 ? undefined : HttpResponse.json(mocks.scan);
      }),
      scanHandler("422.rule.unknown_indicator"),
    );
    const user = userEvent.setup();
    renderWithQuery(<ScanWorkspace />);
    await screen.findByText(REJECTED_TEXT);
    await user.click(screen.getByRole("button", { name: "Run scan" }));
    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(calls).toBe(2);
  });

  it("links Backtest this rule to /backtest with the rule as it is now", async () => {
    const user = userEvent.setup();
    renderWithQuery(<ScanWorkspace />);
    await screen.findByLabelText("Template");
    const href = () =>
      new URL(
        screen.getByRole("link", { name: "Backtest this rule" }).getAttribute("href")!,
        "http://app.test",
      );
    expect(href().pathname).toBe("/backtest");
    expect(href().searchParams.get("template")).toBe("breakout_52w");
    expect(decodeRule(href().searchParams.get("r")!, NAMES)).toEqual(breakout.rule);

    await editRow3To(user, "7");
    expect(href().searchParams.get("template")).toBeNull();
    expect(decodeRule(href().searchParams.get("r")!, NAMES)?.conditions[2].right).toEqual({
      kind: "value",
      value: 7,
    });
  });

  it("is keyboard usable: Tab reaches every control in order and Enter runs the scan", async () => {
    const bodies = recordScans();
    const user = userEvent.setup();
    renderWithQuery(<ScanWorkspace />);
    await screen.findByRole("table");
    const run = screen.getByRole("button", { name: "Run scan" });
    const reached = new Set<Element | null>();
    for (let i = 0; i < 60 && document.activeElement !== run; i += 1) {
      await user.tab();
      reached.add(document.activeElement);
    }
    expect(document.activeElement).toBe(run);
    expect(reached).toContain(screen.getByLabelText("Template"));
    expect(reached).toContain(within(conditionRows()[2]).getByLabelText("Operator"));
    await user.keyboard("{Enter}");
    await waitFor(() => expect(bodies).toHaveLength(2));
  });

  it("treats a pasted rule as an edit: it waits for Run scan", async () => {
    const bodies = recordScans();
    const user = userEvent.setup();
    renderWithQuery(<ScanWorkspace />);
    await screen.findByRole("table");
    await user.click(screen.getByText("Rule as JSON"));
    const pasted = { ...pullback.rule, name: "Pasted" };
    await user.click(screen.getByLabelText("Paste a rule"));
    await user.paste(JSON.stringify(pasted));
    await user.click(screen.getByRole("button", { name: "Load rule" }));

    expect(conditionRows()).toHaveLength(pullback.rule.conditions.length);
    expect(screen.getByText(STALE_TEXT)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Run scan" }));
    await waitFor(() => expect(bodies.at(-1)).toEqual({ rule: pasted }));
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
