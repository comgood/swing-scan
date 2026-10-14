import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, onTestFinished } from "vitest";

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

/** Replaces `matchMedia` with one whose "change" listeners a test can fire. */
function watchColourScheme() {
  const listeners: (() => void)[] = [];
  const original = window.matchMedia;
  window.matchMedia = ((query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener() {},
      removeListener() {},
      addEventListener: (_: string, listener: () => void) => listeners.push(listener),
      removeEventListener: (_: string, listener: () => void) => {
        listeners.splice(listeners.indexOf(listener), 1);
      },
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList) as typeof window.matchMedia;
  onTestFinished(() => {
    window.matchMedia = original;
    for (const name of TOKENS) document.documentElement.style.removeProperty(`--${name}`);
  });
  return { flip: () => listeners.forEach((listener) => listener()), listeners };
}

const TOKENS = ["chart-equity", "chart-benchmark", "chart-oos", "background", "muted-foreground"];

function setTokens(suffix: string) {
  for (const name of TOKENS)
    document.documentElement.style.setProperty(`--${name}`, `${name}-${suffix}`);
}

// covers: AC-14 (colours come from the design.md tokens, re-read when the scheme flips)
describe("EquityChart colours", () => {
  it("paints the lines and the marker from the CSS variables", async () => {
    const scheme = watchColourScheme();
    setTokens("light");
    renderChart();

    await waitFor(() => expect(charts[0]?.series[0]?.markers).toHaveLength(1));
    const [strategy, benchmark] = charts[0]!.series;
    expect(strategy!.options.color).toBe("chart-equity-light");
    expect(benchmark!.options.color).toBe("chart-benchmark-light");
    expect(strategy!.markers[0]!.color).toBe("chart-oos-light");
    expect(charts[0]!.options.layout).toMatchObject({
      background: { color: "background-light" },
      textColor: "muted-foreground-light",
    });
    expect(scheme.listeners).toHaveLength(1);
  });

  it("repaints when the colour scheme flips, and stops listening on unmount", async () => {
    const scheme = watchColourScheme();
    setTokens("light");
    const { unmount } = renderChart();
    await waitFor(() => expect(charts[0]?.series[0]?.markers).toHaveLength(1));

    setTokens("dark");
    scheme.flip();
    const [strategy, benchmark] = charts[0]!.series;
    expect(strategy!.options.color).toBe("chart-equity-dark");
    expect(benchmark!.options.color).toBe("chart-benchmark-dark");
    expect(strategy!.markers[0]!.color).toBe("chart-oos-dark");
    expect(charts[0]!.series[0]!.data).toHaveLength(result.equity.length); // the data is untouched

    unmount();
    expect(scheme.listeners).toHaveLength(0);
  });
});
