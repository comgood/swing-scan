"use client";

// The equity chart (spec 0007 AC-14, decision 12): strategy and benchmark from 100 as two
// Lightweight Charts lines, no overlays, with the OOS start marked on the strategy line and in
// the legend. The canvas is drawn in an effect (the library needs the DOM), loaded on demand so
// it stays out of the first bundle. Colours are the design.md chart tokens, read from the CSS
// variables and read again when the colour scheme flips. The chart is static (no pan or zoom),
// so it never traps touch scrolling at 375 px; screen readers get a one line summary.
import type { Schemas } from "@swing-scan/api-client";
import { useEffect, useRef } from "react";

import { formatDate, formatNumber } from "@/lib/format";

type Point = Schemas["Point"];

interface EquityChartProps {
  equity: Point[];
  benchmark: Point[];
  oosStart: string;
}

/** The chart's text alternative: where each line starts and ends, and where OOS begins. */
export function chartSummary({ equity, benchmark, oosStart }: EquityChartProps): string {
  const first = equity[0];
  const last = equity.at(-1);
  if (!first || !last) return "No equity curve to draw.";
  const end = (points: Point[]) => formatNumber(points.at(-1)?.value);
  return (
    `Strategy equity from 100 to ${end(equity)}, benchmark from 100 to ${end(benchmark)}, ` +
    `${formatDate(first.date)} to ${formatDate(last.date)}. ` +
    `Out of sample from ${formatDate(oosStart)}.`
  );
}

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
}

function colours() {
  return {
    equity: token("chart-equity"),
    benchmark: token("chart-benchmark"),
    oos: token("chart-oos"),
    background: token("background"),
    text: token("muted-foreground"),
    grid: token("border"),
  };
}

export function EquityChart({ equity, benchmark, oosStart }: EquityChartProps) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = box.current;
    if (!element || equity.length === 0) return;
    let dispose = () => {};
    let cancelled = false;

    void import("lightweight-charts").then((lib) => {
      if (cancelled) return;
      const chart = lib.createChart(element, {
        autoSize: true,
        handleScroll: false,
        handleScale: false,
        rightPriceScale: { borderVisible: false },
        timeScale: { borderVisible: false },
      });
      const strategy = chart.addSeries(lib.LineSeries, { lineWidth: 2, title: "Strategy" });
      const bench = chart.addSeries(lib.LineSeries, { lineWidth: 2, title: "Benchmark" });
      strategy.setData(equity.map((p) => ({ time: p.date, value: p.value })));
      bench.setData(benchmark.map((p) => ({ time: p.date, value: p.value })));
      // Markers need a time on the line: the first point on or after the OOS start.
      const oosPoint = equity.find((p) => p.date >= oosStart);
      const markers = lib.createSeriesMarkers(strategy, []);

      const paint = () => {
        const c = colours();
        chart.applyOptions({
          layout: { background: { color: c.background }, textColor: c.text },
          grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
        });
        strategy.applyOptions({ color: c.equity });
        bench.applyOptions({ color: c.benchmark });
        markers.setMarkers(
          oosPoint
            ? [
                {
                  time: oosPoint.date,
                  position: "aboveBar",
                  shape: "arrowDown",
                  color: c.oos,
                  text: "OOS",
                },
              ]
            : [],
        );
      };
      paint();
      chart.timeScale().fitContent();

      const scheme = window.matchMedia("(prefers-color-scheme: dark)");
      scheme.addEventListener("change", paint);
      dispose = () => {
        scheme.removeEventListener("change", paint);
        chart.remove();
      };
    });

    return () => {
      cancelled = true;
      dispose();
    };
  }, [equity, benchmark, oosStart]);

  return (
    <figure className="flex min-w-0 flex-col gap-3">
      <figcaption className="text-sm text-muted-foreground">
        Equity of the strategy and the benchmark, both starting at 100.
      </figcaption>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Chart legend">
        <li className="flex items-center gap-2">
          <span aria-hidden className="h-0.5 w-4 bg-chart-equity" />
          Strategy
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="h-0.5 w-4 bg-chart-benchmark" />
          Benchmark
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="size-2 rotate-45 bg-chart-oos" />
          Out of sample from {formatDate(oosStart)}
        </li>
      </ul>
      <div
        ref={box}
        role="img"
        aria-label={chartSummary({ equity, benchmark, oosStart })}
        className="h-64 w-full min-w-0 sm:h-80"
      />
    </figure>
  );
}
