// covers: spec 0005 AC-11 (columns, formats by kind, New badge, n/a, sorting, pages of 50)
import type { Rule, ScanResponse } from "@swing-scan/api-client";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { expectNoAxeViolations } from "@/test/axe";

import { formatOperand } from "./formats";
import { type IndOperand, operandColumns, operandLabel } from "./operands";
import { ResultsTable } from "./results-table";

function ind(partial: Partial<IndOperand> & Pick<IndOperand, "ind">): IndOperand {
  return { kind: "ind", n: null, offset: 0, mult: 1, ...partial };
}

const RULE: Rule = {
  name: "mixed",
  conditions: [
    { left: ind({ ind: "close" }), op: ">", right: ind({ ind: "sma", n: 50 }) },
    { left: ind({ ind: "volume" }), op: ">", right: ind({ ind: "avg_volume", n: 50, mult: 1.5 }) },
    { left: ind({ ind: "rsi", n: 14 }), op: "<", right: { kind: "value", value: 70 } },
    { left: ind({ ind: "ret", n: 20 }), op: ">", right: ind({ ind: "rs", n: 126 }) },
  ],
};
const OPERANDS = operandColumns(RULE);
const COLUMNS = OPERANDS.map(operandLabel);

function makeResult(count: number): ScanResponse {
  return {
    as_of: "2025-12-31",
    columns: COLUMNS,
    rows: Array.from({ length: count }, (_, i) => ({
      ticker: `T${String(i).padStart(3, "0")}`,
      close: 100 + i,
      chg_pct: i === 0 ? null : 1.5,
      vol_ratio: i === 0 ? null : 2,
      // close, sma(50), volume, 1.5×avg_volume(50), rsi(14), ret(20), rs(126)
      operands: [100 + i, 95.5, 1234567.8, 1000000.4, 55.123, 0.0345, 87],
      new_today: i % 3 === 0,
    })),
  };
}

describe("formatOperand", () => {
  it.each([
    [ind({ ind: "sma", n: 50 }), 95.456, "95.46"],
    [ind({ ind: "volume" }), 1234567.8, "1,234,568"],
    [ind({ ind: "avg_volume", n: 50, mult: 1.5 }), 1000000.4, "1,000,000"],
    [ind({ ind: "rs", n: 126 }), 87, "87"],
    [ind({ ind: "rsi", n: 14 }), 55.123, "55.12"],
    [ind({ ind: "ret", n: 20 }), 0.0345, "+3.45%"],
    [ind({ ind: "atr", n: 14 }), null, "n/a"],
    [undefined, 1.234, "1.23"],
  ])("formats %j with %s as %s", (op, value, text) => {
    expect(formatOperand(op, value)).toBe(text);
  });
});

describe("ResultsTable", () => {
  it("shows the fixed columns, one per operand except close, and New last", () => {
    render(<ResultsTable result={makeResult(3)} operands={OPERANDS} caption="Hits" />);
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toEqual([
      "Ticker",
      "Close",
      "% change",
      "Volume ratio",
      "sma(50)",
      "volume",
      "1.5×avg_volume(50)",
      "rsi(14)",
      "ret(20)",
      "rs(126)",
      "New",
    ]);
  });

  it("formats each cell by kind and shows n/a for nulls", () => {
    render(<ResultsTable result={makeResult(2)} operands={OPERANDS} caption="Hits" />);
    const [, first, second] = screen.getAllByRole("row");
    const cells = within(second)
      .getAllByRole("cell")
      .map((c) => c.textContent);
    expect(cells).toEqual([
      "T001",
      "101.00",
      "+1.50%",
      "2.00",
      "95.50",
      "1,234,568",
      "1,000,000",
      "55.12",
      "+3.45%",
      "87",
      "",
    ]);
    const firstCells = within(first)
      .getAllByRole("cell")
      .map((c) => c.textContent);
    expect(firstCells.slice(2, 4)).toEqual(["n/a", "n/a"]);
    expect(firstCells.at(-1)).toBe("New");
  });

  it("pages at 50 rows and returns to page 1 when you sort", async () => {
    const user = userEvent.setup();
    render(<ResultsTable result={makeResult(120)} operands={OPERANDS} caption="Hits" />);
    expect(screen.getAllByRole("row")).toHaveLength(51);
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Page 2 of 3")).toBeInTheDocument();
    expect(within(screen.getAllByRole("row")[1]).getAllByRole("cell")[0]).toHaveTextContent("T050");

    await user.click(screen.getByRole("button", { name: /% change/ }));
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
  });

  it("sorts nulls last and puts new entries first on the New column", async () => {
    const user = userEvent.setup();
    render(<ResultsTable result={makeResult(4)} operands={OPERANDS} caption="Hits" />);
    const tickers = () =>
      screen
        .getAllByRole("row")
        .slice(1)
        .map((r) => within(r).getAllByRole("cell")[0].textContent);

    const change = screen.getByRole("button", { name: /% change/ });
    await user.click(change);
    expect(tickers().at(-1)).toBe("T000");
    await user.click(change);
    expect(tickers().at(-1)).toBe("T000");

    await user.click(screen.getByRole("button", { name: /New/ }));
    expect(tickers()).toEqual(["T000", "T003", "T001", "T002"]);
  });

  it("formats plainly when the kinds do not line up with the columns", () => {
    render(<ResultsTable result={makeResult(1)} operands={[]} caption="Hits" />);
    const cells = within(screen.getAllByRole("row")[1])
      .getAllByRole("cell")
      .map((c) => c.textContent);
    expect(cells[5]).toBe("1,234,567.80");
  });

  it("has no axe violations", async () => {
    const { container } = render(
      <ResultsTable result={makeResult(60)} operands={OPERANDS} caption="Hits" />,
    );
    await expectNoAxeViolations(container);
  });
});
