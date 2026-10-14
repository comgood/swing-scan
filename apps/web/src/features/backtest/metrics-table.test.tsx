import type { Schemas } from "@swing-scan/api-client";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NOT_AVAILABLE } from "@/lib/format";
import { mocks } from "@/mocks/handlers";
import { expectNoAxeViolations } from "@/test/axe";

import { MetricsTable } from "./metrics-table";

const result = mocks.backtestPortfolio;

type Metrics = Schemas["PortfolioMetrics"];

/** Every metric undefined: what a segment with no trades and one session comes back as. */
const allNull: Metrics = {
  n_trades: 0,
  cagr_pct: null,
  max_dd_pct: null,
  sharpe: null,
  win_rate_pct: null,
  avg_win_pct: null,
  avg_loss_pct: null,
  expectancy_pct: null,
  expectancy_r: null,
  profit_factor: null,
  avg_bars_held: null,
  exposure_pct: null,
};

/**
 * The value cells of one metric row; a row's accessible name starts with its label, which an
 * explained term follows with its one plain line (doc 01 section 6.8).
 */
function cellsOf(label: string): (string | null)[] {
  const name = new RegExp(`^${label.replace(/[()]/g, "\\$&")}[.\\s]`);
  const row = within(screen.getByRole("table")).getByRole("row", { name });
  return within(row)
    .getAllByRole("cell")
    .map((cell) => cell.textContent);
}

// covers: AC-13 (IS beside OOS, the benchmark beside them, null reads "n/a")
describe("MetricsTable", () => {
  it("keeps in sample and out of sample in their own columns", () => {
    render(<MetricsTable result={result} />);
    expect(cellsOf("Trades")).toEqual([
      String(result.metrics.is.n_trades),
      String(result.metrics.oos.n_trades),
      NOT_AVAILABLE,
      NOT_AVAILABLE,
    ]);
    // The last two are the benchmark's own drawdowns, never merged into the strategy's.
    expect(cellsOf("Max drawdown")).toEqual(["-20.07%", "-16.91%", "-28.86%", "-12.95%"]);
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(13); // 12 + header
  });

  it("shows the benchmark only beside CAGR and max drawdown", () => {
    render(<MetricsTable result={result} />);
    for (const label of ["Sharpe", "Win rate", "Expectancy (R)", "Exposure", "Profit factor"]) {
      expect(cellsOf(label).slice(2)).toEqual([NOT_AVAILABLE, NOT_AVAILABLE]);
    }
  });

  it("reads every undefined number as n/a", async () => {
    const empty = {
      ...result,
      metrics: { is: allNull, oos: allNull },
      benchmark_metrics: {
        is: { cagr_pct: null, max_dd_pct: null },
        oos: { cagr_pct: null, max_dd_pct: null },
      },
    };
    const { container } = render(<MetricsTable result={empty} />);
    expect(cellsOf("Trades")).toEqual(["0", "0", NOT_AVAILABLE, NOT_AVAILABLE]);
    const values = within(screen.getByRole("table"))
      .getAllByRole("cell")
      .map((cell) => cell.textContent)
      .filter((text) => text !== "0"); // only the trade counts are defined
    expect(new Set(values)).toEqual(new Set([NOT_AVAILABLE]));
    await expectNoAxeViolations(container);
  });

  // covers: doc 01 section 6.8, every term keeps its label and gains one plain line
  it("explains each metric term without renaming it, on hover and for a screen reader", () => {
    render(<MetricsTable result={result} />);
    const sharpe = within(screen.getByRole("table")).getByRole("rowheader", { name: /^Sharpe\./ });
    expect(within(sharpe).getByTitle(/higher is steadier/).textContent).toBe("Sharpe");
    expect(sharpe).toHaveTextContent("Return divided by how much it bounced around");
    // The abbreviations are spelled out where they first appear (job 2).
    expect(screen.getByRole("columnheader", { name: "In sample (IS)" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "Out of sample (OOS)" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "Benchmark IS" })).toBeVisible();
  });

  it("scrolls by keyboard, so the five columns are reachable at 375 px", () => {
    render(<MetricsTable result={result} />);
    const region = screen.getByRole("region", { name: /in sample beside out of sample/ });
    expect(region).toHaveAttribute("tabindex", "0");
  });
});
