import type { BacktestRequest } from "@swing-scan/api-client";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { memoryStores } from "@/features/honesty/memory-stores";
import { backtestHandler, mocks } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { expectNoAxeViolations } from "@/test/axe";
import { renderWithQuery } from "@/test/render";

import { BacktestReport } from "./backtest-report";

function renderReport(query = "") {
  const user = userEvent.setup();
  const view = renderWithQuery(
    <BacktestReport initialParams={new URLSearchParams(query)} stores={memoryStores()} />,
  );
  return { user, ...view };
}

async function runIt(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: "Run backtest" }));
}

function recordBacktests() {
  const bodies: BacktestRequest[] = [];
  server.use(
    http.post("*/api/v1/backtest", async ({ request }) => {
      bodies.push((await request.json()) as BacktestRequest);
      return HttpResponse.json(mocks.backtestPortfolio);
    }),
  );
  return bodies;
}

// covers: AC-12, AC-13, AC-16, AC-17 against the frozen mocks
describe("BacktestReport", () => {
  it("prefills from the URL and runs only on submit", async () => {
    const bodies = recordBacktests();
    const { user } = renderReport("template=pullback_ema21&max_positions=5");

    expect(await screen.findByLabelText("Template")).toHaveValue("pullback_ema21");
    expect(screen.getByLabelText("Max positions")).toHaveValue("5");
    expect(bodies).toHaveLength(0);

    await runIt(user);
    await screen.findByRole("heading", { name: "Assumptions" });
    expect(bodies).toHaveLength(1);
    expect(bodies[0]!.sim?.max_positions).toBe(5);
    expect(window.location.search).toContain("template=pullback_ema21");
  });

  it("shows the assumptions, the trial counter and IS beside OOS", async () => {
    const { user, container } = renderReport();
    await runIt(user);

    const header = await screen.findByRole("region", { name: "Assumptions" });
    expect(within(header).getByText("Out of sample from")).toBeInTheDocument();
    expect(within(header).getAllByText("not used in portfolio mode")).toHaveLength(2);
    expect(
      await within(header).findByText(/^Trial #1 for this rule structure/),
    ).toBeInTheDocument();

    const table = within(screen.getByRole("region", { name: "Results" })).getByRole("table");
    const columns = within(table)
      .getAllByRole("columnheader")
      .map((c) => c.textContent);
    expect(columns).toEqual([
      "Metric",
      "In sample",
      "Out of sample",
      "Benchmark IS",
      "Benchmark OOS",
    ]);
    const cagr = within(table).getByRole("row", { name: /CAGR/ });
    expect(
      within(cagr)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["+3.32%", "-6.25%", "+22.76%", "+32.78%"]);
    await expectNoAxeViolations(container);
  });

  it("shows the empty state when the rule never entered", async () => {
    server.use(backtestHandler("no_entries"));
    const { user } = renderReport();
    await runIt(user);

    expect(await screen.findByText("No trades")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Assumptions" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Trades" })).not.toBeInTheDocument();
  });

  it("says when the trade list is truncated", async () => {
    server.use(backtestHandler("truncated"));
    const { user } = renderReport();
    await runIt(user);

    expect(
      await screen.findByText(mocks.backtestTruncated.warnings[0]!.message),
    ).toBeInTheDocument();
    const trades = screen.getByRole("region", { name: "Trades" });
    expect(within(trades).getByText(/^Showing 2,000 of 2,600 trades/)).toBeInTheDocument();
  });

  it("puts a 422 on the field it belongs to", async () => {
    server.use(backtestHandler("422.sim.out_of_range"));
    const { user, container } = renderReport();
    await runIt(user);

    expect(await screen.findByText("Must be between 1 and 20")).toBeInTheDocument();
    expect(screen.getByLabelText("Max positions")).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByRole("heading", { name: "Assumptions" })).not.toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("says a 501 is not built yet, with no retry", async () => {
    server.use(
      http.post("*/api/v1/backtest", () =>
        HttpResponse.json({ detail: "Exit lab arrives with feature 12." }, { status: 501 }),
      ),
    );
    const { user } = renderReport();
    await runIt(user);

    expect(await screen.findByText("Not built yet")).toBeInTheDocument();
    expect(screen.getByText(/feature 12/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("disables the button and holds the report's place while the run is in flight", async () => {
    server.use(backtestHandler("auto", { delayMs: "infinite" }));
    const { user } = renderReport();
    await runIt(user);

    expect(await screen.findByRole("button", { name: "Running…" })).toBeDisabled();
    expect(screen.getByText("Running the backtest…")).toBeInTheDocument();
  });

  it("draws the equity chart between the results and the trades", async () => {
    const { user, container } = renderReport();
    await runIt(user);

    const equity = await screen.findByRole("region", { name: "Equity" });
    expect(within(equity).getByRole("img")).toHaveAccessibleName(/^Strategy equity from 100/);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings.slice(-3)).toEqual(["Results", "Equity", "Trades"]);
    await expectNoAxeViolations(container);
  });
});
