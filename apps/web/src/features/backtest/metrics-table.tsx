// IS and OOS side by side, never merged, with the benchmark's CAGR and max DD beside them
// (spec 0007 AC-13). Every number goes through format.ts, so null reads "n/a".
import type { Schemas } from "@swing-scan/api-client";
import type * as React from "react";

import { SignedValue } from "@/components/signed-value";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatInt, formatNumber, formatPct, NOT_AVAILABLE } from "@/lib/format";

import type { PortfolioResult } from "./queries";

type Metrics = Schemas["PortfolioMetrics"];
type Value = number | null;

interface MetricRow {
  key: keyof Metrics;
  label: string;
  show: (v: Value) => React.ReactNode;
  benchmark?: "cagr_pct" | "max_dd_pct";
  /** The one plain line beside the term, word for word from doc 01 section 6.8. */
  hint?: string;
}

/**
 * A term keeps its label and gains one plain line: the line is the `abbr` tooltip and, for
 * anyone not hovering, a screen reader only sentence (doc 01 section 6.8).
 */
function Explained({ label, hint }: { label: string; hint?: string }) {
  if (!hint) return label;
  return (
    <>
      <abbr title={hint} className="no-underline">
        {label}
      </abbr>
      <span className="sr-only">. {hint}</span>
    </>
  );
}

const signedPct = (v: Value) => <SignedValue value={v} format="pct" />;
const plainPct = (v: Value) => formatPct(v).replace(/^\+/, "");

const ROWS: MetricRow[] = [
  { key: "n_trades", label: "Trades", show: (v) => formatInt(v) },
  {
    key: "cagr_pct",
    label: "CAGR",
    show: signedPct,
    benchmark: "cagr_pct",
    hint: "The yearly growth rate the equity curve works out to.",
  },
  {
    key: "max_dd_pct",
    label: "Max drawdown",
    show: signedPct,
    benchmark: "max_dd_pct",
    hint: "The worst fall from a previous peak in equity.",
  },
  {
    key: "sharpe",
    label: "Sharpe",
    show: (v) => <SignedValue value={v} format="number" />,
    hint: "Return divided by how much it bounced around; higher is steadier.",
  },
  {
    key: "win_rate_pct",
    label: "Win rate",
    show: plainPct,
    hint: "The share of trades that ended in profit.",
  },
  { key: "avg_win_pct", label: "Average win", show: signedPct },
  { key: "avg_loss_pct", label: "Average loss", show: signedPct },
  {
    key: "expectancy_pct",
    label: "Expectancy",
    show: signedPct,
    hint: "What one average trade made or lost, in percent.",
  },
  {
    key: "expectancy_r",
    label: "Expectancy (R)",
    show: (v) => <SignedValue value={v} format="r" />,
    hint: "The same, counted in multiples of the risk you took (R = the distance to your stop).",
  },
  {
    key: "profit_factor",
    label: "Profit factor",
    show: (v) => formatNumber(v),
    hint: "Everything the winners made divided by everything the losers lost. Above 1 is a profit.",
  },
  {
    key: "avg_bars_held",
    label: "Average bars held",
    show: (v) => formatNumber(v, { decimals: 1 }),
  },
  {
    key: "exposure_pct",
    label: "Exposure",
    show: plainPct,
    hint: "The share of the test period with money in the market.",
  },
];

export function MetricsTable({ result }: { result: PortfolioResult }) {
  const { metrics, benchmark_metrics: bench } = result;
  const benchmarkCell = (row: MetricRow, segment: "is" | "oos") =>
    row.benchmark ? signedPct(bench[segment][row.benchmark]) : NOT_AVAILABLE;
  return (
    // A focusable scroll region, like DataTable's, so the five columns scroll by keyboard at 375 px.
    <div
      role="region"
      aria-label="Metrics, in sample beside out of sample"
      tabIndex={0}
      className="min-w-0 overflow-auto rounded-lg border"
    >
      <Table className="tabular-nums">
        <TableHeader>
          <TableRow>
            <TableHead scope="col">Metric</TableHead>
            <TableHead scope="col" className="text-right">
              In sample (IS)
            </TableHead>
            <TableHead scope="col" className="text-right">
              Out of sample (OOS)
            </TableHead>
            <TableHead scope="col" className="text-right">
              Benchmark IS
            </TableHead>
            <TableHead scope="col" className="text-right">
              Benchmark OOS
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {ROWS.map((row) => (
            <TableRow key={row.key}>
              <TableHead scope="row" className="font-normal">
                <Explained label={row.label} hint={row.hint} />
              </TableHead>
              <TableCell className="text-right">{row.show(metrics.is[row.key])}</TableCell>
              <TableCell className="text-right">{row.show(metrics.oos[row.key])}</TableCell>
              <TableCell className="text-right text-muted-foreground">
                {benchmarkCell(row, "is")}
              </TableCell>
              <TableCell className="text-right text-muted-foreground">
                {benchmarkCell(row, "oos")}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
