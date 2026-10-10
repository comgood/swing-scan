// covers: AC-17 (the warm up and error states the page can land in, and axe on each)
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { memoryStores } from "@/features/honesty/memory-stores";
import { backtestHandler, mocks } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { expectNoAxeViolations } from "@/test/axe";
import { renderWithQuery } from "@/test/render";

import { BacktestReport } from "./backtest-report";

const WARMUP_TEXT = "Warming up the engine…";

function renderReport() {
  const user = userEvent.setup();
  const view = renderWithQuery(
    <BacktestReport initialParams={new URLSearchParams()} stores={memoryStores()} />,
  );
  return { user, ...view };
}

async function runIt(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: "Run backtest" }));
}

describe("BacktestReport states", () => {
  it("says the engine is warming up once a run passes 1.5 s", async () => {
    server.use(backtestHandler("auto", { delayMs: "infinite" }));
    const { user } = renderReport();
    await runIt(user);

    expect(screen.queryByText(WARMUP_TEXT)).not.toBeInTheDocument();
    expect(await screen.findByText(WARMUP_TEXT, {}, { timeout: 2500 })).toBeVisible();
    expect(screen.getByText("Running the backtest…")).toBeInTheDocument();
  });

  it("warms up while the templates are still loading, before any run", async () => {
    server.use(http.get("*/api/v1/templates", () => new Promise(() => {})));
    renderReport();

    expect(await screen.findByText(WARMUP_TEXT, {}, { timeout: 2500 })).toBeVisible();
    expect(screen.getByText("Loading templates…")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run backtest" })).not.toBeInTheDocument();
  });

  it("offers Try again after a failed run, and it sends the same request again", async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post("*/api/v1/backtest", async ({ request }) => {
        bodies.push(await request.json());
        return bodies.length === 1
          ? HttpResponse.json({ detail: "boom" }, { status: 500 })
          : HttpResponse.json(mocks.backtestPortfolio);
      }),
    );
    const { user, container } = renderReport();
    await runIt(user);

    expect(await screen.findByText("Something went wrong")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Assumptions" })).not.toBeInTheDocument();
    await expectNoAxeViolations(container);

    await user.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByRole("heading", { name: "Assumptions" });
    expect(bodies).toHaveLength(2);
    expect(bodies[1]).toEqual(bodies[0]);
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });

  it("cannot be reached when the engine is down, and retries the templates", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v1/templates", () => {
        calls += 1;
        return calls === 1 ? HttpResponse.error() : HttpResponse.json(mocks.templates);
      }),
    );
    const { user, container } = renderReport();

    expect(await screen.findByText("Can't reach the engine")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run backtest" })).not.toBeInTheDocument();
    await expectNoAxeViolations(container);

    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("button", { name: "Run backtest" })).toBeInTheDocument();
    expect(calls).toBe(2);
  });
});
