import type { BacktestRequest, Schemas } from "@swing-scan/api-client";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { DEFAULT_CONFIGS } from "@/features/exit-lab";
import { memoryStores } from "@/features/honesty/memory-stores";
import { PROCEDURE_NOTE } from "@/features/honesty";
import { backtestHandler, mocks } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { expectNoAxeViolations } from "@/test/axe";
import { renderWithQuery } from "@/test/render";

import { BacktestReport } from "./backtest-report";
import { NOT_USED_TRADE } from "./assumption-labels";

type TradeLabResult = Schemas["TradeLabResult"];

function renderReport(query = "") {
  const user = userEvent.setup();
  const view = renderWithQuery(
    <BacktestReport initialParams={new URLSearchParams(query)} stores={memoryStores()} />,
  );
  return { user, ...view };
}

async function openLab(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByLabelText(/^Exit lab: compare 2 to 6/));
}

function recordBacktests(result: TradeLabResult = mocks.backtestTradeLab) {
  const bodies: BacktestRequest[] = [];
  server.use(
    http.post("*/api/v1/backtest", async ({ request }) => {
      bodies.push((await request.json()) as BacktestRequest);
      return HttpResponse.json(result);
    }),
  );
  return bodies;
}

const card = (legend: string) => screen.getByRole("group", { name: legend });

/** The header as term → value pairs. */
function headerPairs(): Record<string, string> {
  const header = screen.getByRole("region", { name: "Assumptions" });
  return Object.fromEntries(
    within(header)
      .getAllByRole("term")
      .map((dt) => [dt.textContent, dt.nextElementSibling?.textContent ?? ""]),
  );
}

// covers: spec 0009 AC-18 (counter half), AC-19, AC-20 against the frozen mocks
// Each test renders the whole lab form and table; the CI runner takes about 5 s for the
// heaviest, past Vitest's 5 s default, so this file gets the gallery's 20 s budget.
describe("exit lab on /backtest", { timeout: 20_000 }, () => {
  it("opens with the five default configs, config 1 the baseline", async () => {
    const { user, container } = renderReport();
    await openLab(user);

    const names = DEFAULT_CONFIGS.map((_, i) =>
      within(card(`Config ${String(i + 1)}${i === 0 ? " (baseline)" : ""}`)).getByLabelText("Name"),
    );
    expect(names.map((n) => (n as HTMLInputElement).value)).toEqual(
      DEFAULT_CONFIGS.map((c) => c.name),
    );
    expect(screen.queryByLabelText("Max positions")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Horizon (bars)")).toHaveValue("60");
    await expectNoAxeViolations(container);
  });

  it("disables add at 6 configs and remove at 2", async () => {
    const { user } = renderReport();
    await openLab(user);
    const add = screen.getByRole("button", { name: "Add config" });

    await user.click(add);
    expect(within(card("Config 6")).getByLabelText("Name")).toHaveValue("Config 6");
    expect(add).toBeDisabled();
    expect(screen.getByText("6 of 6 configs")).toBeInTheDocument();

    for (let i = 0; i < 4; i += 1) {
      await user.click(screen.getByRole("button", { name: "Remove Config 2" }));
    }
    expect(screen.getByText("2 of 6 configs")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove Config 2" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Remove Config 1 (baseline)" })).toBeDisabled();
    expect(add).toHaveFocus();
  });

  it("sends every config, keeps them in ?x= and shows the lab with header and counter", async () => {
    const bodies = recordBacktests();
    const { user, container } = renderReport();
    await openLab(user);
    await user.click(screen.getByRole("button", { name: "Run exit lab" }));

    expect(await screen.findByRole("heading", { name: "Exit lab" })).toBeInTheDocument();
    expect(bodies[0]!.configs).toEqual(DEFAULT_CONFIGS);
    const x = JSON.parse(new URLSearchParams(window.location.search).get("x")!) as unknown;
    expect(x).toEqual({ configs: DEFAULT_CONFIGS });

    // AC-19: every field, null as "not used in trade mode", horizon, seed and overlap stated.
    const pairs = headerPairs();
    expect(Object.keys(pairs)).toHaveLength(Object.keys(mocks.backtestTradeLab.assumptions).length);
    expect(pairs["Max positions"]).toBe(NOT_USED_TRADE);
    expect(pairs.Horizon).toMatch(/^60 bars/);
    expect(pairs["Random seed"]).toBe("42");
    expect(pairs["Overlapping trades in one ticker"]).toMatch(/same ticker trades may overlap/);
    for (const config of DEFAULT_CONFIGS) expect(pairs["Exit rules"]).toContain(config.name);

    // AC-18: one pair per config recorded, beside the header.
    const header = screen.getByRole("region", { name: "Assumptions" });
    expect(
      await within(header).findByText("Trial #5 for this rule structure · 5 this session"),
    ).toBeInTheDocument();

    // The table, the procedure note under it, then the baseline trades.
    expect(screen.getByRole("region", { name: /^Exit lab, in sample/ })).toBeInTheDocument();
    expect(screen.getByText(PROCEDURE_NOTE)).toBeInTheDocument();
    const trades = screen.getByRole("region", { name: "Baseline trades" });
    expect(within(trades).getByText(/"Baseline"/)).toBeInTheDocument();
    // The horizon warning is a row badge, not a page banner.
    const horizon = mocks.backtestTradeLab.warnings[0]!.message;
    expect(screen.queryByRole("status", { name: horizon })).not.toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("opens straight into the lab from a ?x= configs link", async () => {
    const x = JSON.stringify({ configs: DEFAULT_CONFIGS.slice(1, 4) });
    const bodies = recordBacktests();
    const { user } = renderReport(`template=breakout_52w&x=${encodeURIComponent(x)}`);

    expect(await screen.findByLabelText(/^Exit lab: compare/)).toBeChecked();
    expect(within(card("Config 1 (baseline)")).getByLabelText("Name")).toHaveValue(
      "ATR stop and target",
    );
    await user.click(screen.getByRole("button", { name: "Run exit lab" }));
    await screen.findByRole("heading", { name: "Exit lab" });
    expect(bodies[0]!.configs).toEqual(DEFAULT_CONFIGS.slice(1, 4));
  });

  it("keeps your lab edits when you switch to one config and back", async () => {
    const { user } = renderReport();
    await openLab(user);
    const name = within(card("Config 2")).getByLabelText("Name");
    await user.clear(name);
    await user.type(name, "Mine");
    await user.click(screen.getByLabelText(/^One exit config/));
    expect(screen.getByLabelText("Max positions")).toBeInTheDocument();
    await openLab(user);
    expect(within(card("Config 2")).getByLabelText("Name")).toHaveValue("Mine");
  });

  it("puts a 422 on the exact config and exit field", async () => {
    server.use(
      http.post("*/api/v1/backtest", () =>
        HttpResponse.json(
          {
            detail: [
              {
                loc: ["body", "configs", 1, "exits", 0, "stop_atr", "n"],
                msg: "must be at least 2",
              },
              { loc: ["body", "configs", 3, "name"], msg: "duplicate config name" },
            ],
          },
          { status: 422 },
        ),
      ),
    );
    const { user, container } = renderReport();
    await openLab(user);
    await user.click(screen.getByRole("button", { name: "Run exit lab" }));

    const second = card("Config 2");
    expect(await within(second).findByText("Must be at least 2")).toBeInTheDocument();
    expect(within(second).getByLabelText("ATR length (bars)")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(
      within(card("Config 1 (baseline)")).getByLabelText("ATR length (bars)"),
    ).not.toHaveAttribute("aria-invalid");
    expect(within(card("Config 4")).getByLabelText("Name")).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByRole("heading", { name: "Exit lab" })).not.toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("shows the empty state when the rule never entered", async () => {
    const message = "No entries: the rule never produced a signal in this window.";
    recordBacktests({
      ...mocks.backtestTradeLab,
      warnings: [{ code: "no_entries", config_index: null, message }],
    });
    const { user } = renderReport();
    await openLab(user);
    await user.click(screen.getByRole("button", { name: "Run exit lab" }));

    expect(await screen.findByText("No trades")).toBeInTheDocument();
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Assumptions" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Exit lab" })).not.toBeInTheDocument();
  });

  it("holds the report's place while the run is in flight", async () => {
    server.use(backtestHandler("auto", { delayMs: "infinite" }));
    const { user } = renderReport();
    await openLab(user);
    await user.click(screen.getByRole("button", { name: "Run exit lab" }));

    expect(await screen.findByRole("button", { name: "Running…" })).toBeDisabled();
    expect(screen.getByText("Running the backtest…")).toBeInTheDocument();
  });

  it("shows a server error with a retry", async () => {
    server.use(
      http.post("*/api/v1/backtest", () => HttpResponse.json({ detail: "boom" }, { status: 500 })),
    );
    const { user } = renderReport();
    await openLab(user);
    await user.click(screen.getByRole("button", { name: "Run exit lab" }));

    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Assumptions" })).not.toBeInTheDocument();
  });
});
