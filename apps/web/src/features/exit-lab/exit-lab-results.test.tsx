import { createClient, type Schemas } from "@swing-scan/api-client";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PROCEDURE_NOTE } from "@/features/honesty";
import { formatPct } from "@/lib/format";
import { mocks } from "@/mocks/handlers";
import { expectNoAxeViolations } from "@/test/axe";

import { DEFAULT_CONFIGS } from "./default-configs";
import { ExitLabResults } from "./exit-lab-results";
import { GUIDE_SOURCE } from "./guide-row";

type TradeLabResult = Schemas["TradeLabResult"];

/** The frozen mock, fetched through MSW the way the page will once it is wired (milestone 5). */
async function fetchLab(): Promise<TradeLabResult> {
  const api = createClient({ baseUrl: "http://api.test" });
  const { data } = await api.POST("/api/v1/backtest", {
    body: {
      rule: mocks.templates[0].rule,
      configs: [...DEFAULT_CONFIGS],
      sim: {
        max_positions: 10,
        slippage_bps: 10,
        horizon_bars: 60,
        seed: 42,
        start: null,
        end: null,
      },
    },
  });
  if (data?.mode !== "trade") throw new Error("expected the exit lab mock");
  return data;
}

const table = () => screen.getByRole("table");
const rowOf = (name: string) =>
  screen
    .getAllByRole("row")
    .find((r) => within(r).queryByRole("rowheader")?.textContent?.startsWith(name));
const cell = (row: HTMLElement, metric: string, segment: "is" | "oos") => {
  const found = row.querySelector(`td[data-metric="${metric}"][data-segment="${segment}"]`);
  if (!(found instanceof HTMLElement)) throw new Error(`no ${metric} ${segment} cell`);
  return found;
};

describe("exit lab table on the trade lab mock", () => {
  it("shows one row per config with every metric as an IS | OOS pair (AC-13)", async () => {
    const result = await fetchLab();
    render(<ExitLabResults result={result} />);
    for (const row of result.rows) expect(rowOf(row.name)).toBeDefined();
    expect(screen.getByRole("columnheader", { name: "Win rate IS" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Win rate OOS" })).toBeInTheDocument();
    const baseline = rowOf("Baseline");
    if (!baseline) throw new Error("no baseline row");
    expect(cell(baseline, "win_rate_pct", "is")).toHaveTextContent("52.46%");
    expect(cell(baseline, "win_rate_pct", "oos")).toHaveTextContent("62.07%");
    // No portfolio metrics in trade mode (X-8).
    expect(within(table()).queryByText(/CAGR|Sharpe|drawdown/i)).not.toBeInTheDocument();
  });

  it("marks exactly the best_is cells, in IS columns only, with a text label (AC-13)", async () => {
    const result = await fetchLab();
    render(<ExitLabResults result={result} />);
    const marked = Array.from(table().querySelectorAll("td[data-best-is]"));
    const expected = Object.entries(result.best_is).filter(([, i]) => i !== null);
    expect(marked).toHaveLength(expected.length);
    for (const [metric, index] of expected) {
      const row = rowOf(result.rows[index as number].name);
      if (!row) throw new Error("missing row");
      const best = cell(row, metric, "is");
      expect(best).toHaveAttribute("data-best-is");
      expect(within(best).getByText("Best IS")).toBeVisible();
    }
    for (const td of marked) expect(td).toHaveAttribute("data-segment", "is");
    expect(table().querySelectorAll('td[data-segment="oos"][data-best-is]')).toHaveLength(0);
    expect(table().querySelectorAll('td[data-metric^="edge_"][data-best-is]')).toHaveLength(0);
  });

  it("reads n/a in R cells of a stopless config, with the footnote (AC-14)", async () => {
    const result = await fetchLab();
    render(<ExitLabResults result={result} />);
    const ma = rowOf("MA exit, no stop");
    if (!ma) throw new Error("no MA row");
    expect(cell(ma, "expectancy_r", "is")).toHaveTextContent(/^n\/a\*$/);
    expect(cell(ma, "edge_expectancy_r", "oos")).toHaveTextContent(/^n\/a\*$/);
    expect(cell(ma, "expectancy_pct", "is")).toHaveTextContent("+1.85%");
    const baseline = rowOf("Baseline");
    if (!baseline) throw new Error("no baseline row");
    expect(cell(baseline, "expectancy_r", "is")).toHaveTextContent(/^\+0\.07R$/);
    expect(
      screen.getByText(
        /^\* R needs a stop\. "MA exit, no stop" and "Wide target, no stop" have no stop/,
      ),
    ).toBeVisible();
  });

  it("puts the horizon badge and message on the warned row only (AC-15)", async () => {
    const result = await fetchLab();
    render(<ExitLabResults result={result} />);
    const warned = rowOf("Wide target, no stop");
    if (!warned) throw new Error("no warned row");
    expect(within(warned).getByText("Horizon over 10%")).toBeVisible();
    expect(within(warned).getByText(result.warnings[0].message)).toBeVisible();
    expect(screen.getAllByText("Horizon over 10%")).toHaveLength(1);
  });

  it("shows edge vs random, the Random entries row and each row's own random metrics (AC-16)", async () => {
    const user = userEvent.setup();
    const result = await fetchLab();
    render(<ExitLabResults result={result} />);
    expect(screen.getByRole("columnheader", { name: "Edge vs random" })).toBeInTheDocument();
    const baseline = rowOf("Baseline");
    if (!baseline) throw new Error("no baseline row");
    expect(cell(baseline, "edge_expectancy_pct", "is")).toHaveTextContent("+1.50%");
    expect(cell(baseline, "edge_win_rate_pct", "oos")).toHaveTextContent("+8.62 pts");

    const bottom = rowOf("Random entries");
    if (!bottom) throw new Error("no Random entries row");
    expect(cell(bottom, "win_rate_pct", "is")).toHaveTextContent("46.72%");

    const toggle = screen.getByRole("button", { name: "Random entries for Trailing 10%" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(rowOf("Random entries, Trailing 10%")).toBeUndefined();
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const own = rowOf("Random entries, Trailing 10%");
    if (!own) throw new Error("no disclosed row");
    expect(cell(own, "expectancy_pct", "is")).toHaveTextContent(
      formatPct(result.rows[3].random.is.expectancy_pct),
    );
    expect(own.querySelectorAll("td[data-best-is]")).toHaveLength(0);
    await user.click(toggle);
    expect(rowOf("Random entries, Trailing 10%")).toBeUndefined();
  });

  it("puts the procedure note directly under the table, then the guide row (AC-17, AC-18)", async () => {
    const result = await fetchLab();
    const { container } = render(<ExitLabResults result={result} />);
    const region = screen.getByRole("region", { name: /Exit lab/ });
    const note = screen.getByText(PROCEDURE_NOTE).closest("[data-slot=procedure-note]");
    expect(region.nextElementSibling).toBe(note);
    const guides = screen.getByRole("group", { name: /Stop and target guides/ });
    expect(note?.nextElementSibling).toBe(guides);
    expect(guides).toHaveTextContent(GUIDE_SOURCE);
    expect(within(guides).getByText("-2.54%")).toBeVisible();
    expect(within(guides).getByText("+7.51%")).toBeVisible();
    await expectNoAxeViolations(container);
  }, 20_000);

  it("reads n/a for null guides and metrics, with no highlight (no entries)", () => {
    const empty: TradeLabResult = structuredClone(mocks.backtestTradeLab);
    empty.guides_is = { winner_mae_p75_pct: null, winner_mae_p90_pct: null, mfe_median_pct: null };
    for (const key of Object.keys(empty.best_is)) {
      empty.best_is[key as keyof typeof empty.best_is] = null;
    }
    render(<ExitLabResults result={empty} />);
    const guides = screen.getByRole("group", { name: /Stop and target guides/ });
    expect(within(guides).getAllByText("n/a")).toHaveLength(3);
    expect(table().querySelectorAll("td[data-best-is]")).toHaveLength(0);
  });

  it("scrolls inside its own focusable region, so the page never does at 375 px (U-6)", async () => {
    const result = await fetchLab();
    render(<ExitLabResults result={result} />);
    const region = screen.getByRole("region", { name: /Exit lab/ });
    expect(region).toHaveAttribute("tabindex", "0");
    expect(region.className).toMatch(/overflow-auto/);
    expect(region.className).toMatch(/min-w-0/);
    expect(screen.getByRole("rowheader", { name: /^Baseline/ }).className).toMatch(/sticky/);
  });
});

describe("default configs", () => {
  it("are the five configs of backtest.trade_lab.json (decision 10)", () => {
    expect(DEFAULT_CONFIGS).toEqual(mocks.backtestTradeLab.assumptions.configs);
  });
});
