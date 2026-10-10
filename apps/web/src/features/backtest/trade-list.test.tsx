import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mocks } from "@/mocks/handlers";
import { expectNoAxeViolations } from "@/test/axe";

import { TradeList, TRADE_COLUMNS, type Trade } from "./trade-list";

const portfolio = mocks.backtestPortfolio;
const truncated = mocks.backtestTruncated;

function renderList(result = portfolio) {
  return render(
    <TradeList
      trades={result.trades}
      total={result.trades_total}
      truncated={result.trades_truncated}
      oosStart={result.oos_start}
    />,
  );
}

const bodyRows = () => within(screen.getByRole("table")).getAllByRole("row").slice(1);
const cellsOf = (row: HTMLElement) =>
  within(row)
    .getAllByRole("cell")
    .map((c) => c.textContent);

// covers: AC-15 against the frozen mocks
describe("TradeList", () => {
  it("has a column for every Trade field", () => {
    const fields = Object.keys(portfolio.trades[0]!).sort();
    expect(TRADE_COLUMNS.map((c) => c.id).sort()).toEqual(fields);
  });

  it("formats every field through format.ts and marks IS and OOS", () => {
    renderList();
    const headers = within(screen.getByRole("table"))
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    expect(headers).toEqual([
      "Ticker",
      "Sample",
      "Entry date",
      "Entry price",
      "Exit date",
      "Exit price",
      "Exit reason",
      "Return",
      "R multiple",
      "Bars held",
      "MAE",
      "MAE (R)",
      "MFE",
      "MFE (R)",
    ]);
    expect(cellsOf(bodyRows()[0]!)).toEqual([
      "SYN264",
      "IS",
      "2021-01-06",
      "128.30",
      "2021-02-03",
      "123.39",
      "Time",
      "-3.82%",
      "-0.48R",
      "20",
      "-4.97%",
      "-0.62R",
      "+3.80%",
      "+0.47R",
    ]);
  });

  it("marks out of sample trades, which sort above IS on the second click", async () => {
    const user = userEvent.setup();
    renderList();
    await user.click(screen.getByRole("button", { name: "Sample" }));
    expect(cellsOf(bodyRows()[0]!)[1]).toBe("IS");
    await user.click(screen.getByRole("button", { name: "Sample" }));
    expect(cellsOf(bodyRows()[0]!)[1]).toBe("OOS");
  });

  it("shows n/a for a missing R multiple", () => {
    const trade: Trade = { ...portfolio.trades[0]!, r_multiple: null, mae_r: null, mfe_r: null };
    render(<TradeList trades={[trade]} total={1} truncated={false} oosStart="2024-07-03" />);
    expect(cellsOf(bodyRows()[0]!).filter((t) => t === "n/a")).toHaveLength(3);
  });

  it("sorts by a column on click, largest return first", async () => {
    const user = userEvent.setup();
    renderList();
    await user.click(screen.getByRole("button", { name: "Return" }));
    const best = Math.max(...portfolio.trades.map((t) => t.return_pct));
    expect(cellsOf(bodyRows()[0]!)[7]).toBe(`+${best.toFixed(2)}%`);
    expect(screen.getByRole("columnheader", { name: "Return" })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
  });

  it("says showing 2,000 of N when truncated, and pages the rows", () => {
    renderList(truncated);
    expect(
      screen.getByText(/^Showing 120 of 2,600 trades, the latest by entry date/),
    ).toBeInTheDocument();
    expect(bodyRows()).toHaveLength(50);
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
  });

  it("states the total when nothing was cut", () => {
    renderList();
    expect(screen.getByText(/^150 trades\./)).toBeInTheDocument();
    expect(screen.queryByText(/^Showing/)).not.toBeInTheDocument();
  });

  it("passes axe", async () => {
    const { container } = renderList();
    await expectNoAxeViolations(container);
  });
});
