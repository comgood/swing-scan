import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mocks } from "@/mocks/handlers";
import { expectNoAxeViolations } from "@/test/axe";
import { charts } from "@/test/lightweight-charts-fake";

import { chartSummary, EquityChart } from "./equity-chart";

const result = mocks.backtestPortfolio;

function renderChart() {
  return render(
    <EquityChart equity={result.equity} benchmark={result.benchmark} oosStart={result.oos_start} />,
  );
}

// covers: AC-14 (strategy and benchmark from 100, OOS start marked)
describe("EquityChart", () => {
  it("draws two lines, strategy then benchmark, both from 100", async () => {
    renderChart();
    await waitFor(() => expect(charts).toHaveLength(1));
    const [strategy, benchmark] = charts[0]!.series;
    expect(charts[0]!.series).toHaveLength(2);
    expect(strategy!.options.title).toBe("Strategy");
    expect(benchmark!.options.title).toBe("Benchmark");
    expect(strategy!.data[0]).toEqual({ time: result.equity[0]!.date, value: 100 });
    expect(benchmark!.data[0]!.value).toBe(100);
    expect(strategy!.data).toHaveLength(result.equity.length);
  });

  it("marks the first point on or after the OOS start", async () => {
    renderChart();
    await waitFor(() => expect(charts[0]?.series[0]?.markers).toHaveLength(1));
    const marker = charts[0]!.series[0]!.markers[0]!;
    const first = result.equity.find((p) => p.date >= result.oos_start)!;
    expect(marker).toMatchObject({ time: first.date, text: "OOS" });
    expect(screen.getByText(/^Out of sample from/)).toBeInTheDocument();
  });

  it("describes the chart in words and removes it on unmount", async () => {
    const { unmount, container } = renderChart();
    const img = screen.getByRole("img");
    expect(img).toHaveAccessibleName(chartSummary({ ...result, oosStart: result.oos_start }));
    expect(img.getAttribute("aria-label")).toMatch(/^Strategy equity from 100 to 104\.24/);
    await expectNoAxeViolations(container);
    await waitFor(() => expect(charts).toHaveLength(1));
    unmount();
    expect(charts[0]!.removed).toBe(true);
  });

  it("draws nothing for an empty curve", async () => {
    render(<EquityChart equity={[]} benchmark={[]} oosStart="2024-07-03" />);
    expect(screen.getByRole("img")).toHaveAccessibleName("No equity curve to draw.");
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(charts).toHaveLength(0);
  });
});
