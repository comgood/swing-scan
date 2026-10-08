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
}

const signedPct = (v: Value) => <SignedValue value={v} format="pct" />;
const plainPct = (v: Value) => formatPct(v).replace(/^\+/, "");

const ROWS: MetricRow[] = [
  { key: "n_trades", label: "Trades", show: (v) => formatInt(v) },
  { key: "cagr_pct", label: "CAGR", show: signedPct, benchmark: "cagr_pct" },
  { key: "max_dd_pct", label: "Max drawdown", show: signedPct, benchmark: "max_dd_pct" },
  { key: "sharpe", label: "Sharpe", show: (v) => <SignedValue value={v} format="number" /> },
  { key: "win_rate_pct", label: "Win rate", show: plainPct },
  { key: "avg_win_pct", label: "Average win", show: signedPct },
  { key: "avg_loss_pct", label: "Average loss", show: signedPct },
  { key: "expectancy_pct", label: "Expectancy", show: signedPct },
  {
    key: "expectancy_r",
    label: "Expectancy (R)",
    show: (v) => <SignedValue value={v} format="r" />,
  },
  { key: "profit_factor", label: "Profit factor", show: (v) => formatNumber(v) },
  {
    key: "avg_bars_held",
    label: "Average bars held",
    show: (v) => formatNumber(v, { decimals: 1 }),
  },
  { key: "exposure_pct", label: "Exposure", show: plainPct },
];

export function MetricsTable({ result }: { result: PortfolioResult }) {
  const { metrics, benchmark_metrics: bench } = result;
  const benchmarkCell = (row: MetricRow, segment: "is" | "oos") =>
    row.benchmark ? signedPct(bench[segment][row.benchmark]) : NOT_AVAILABLE;
  return (
    <div className="min-w-0 overflow-x-auto rounded-lg border">
      <Table className="tabular-nums">
        <TableHeader>
          <TableRow>
            <TableHead scope="col">Metric</TableHead>
            <TableHead scope="col" className="text-right">
              In sample
            </TableHead>
            <TableHead scope="col" className="text-right">
              Out of sample
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
                {row.label}
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
