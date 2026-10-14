"use client";

// The exit lab table (spec 0009 AC-13 to AC-16): one row per config, every metric as an IS | OOS
// pair, then "Edge vs random". The best IS cell named by `best_is` carries a "Best IS" label as
// well as the accent fill, so the mark never relies on colour; OOS, random and edge cells are
// never marked. A "Random entries" row closes the table, and each config row can show its own
// random metrics. Every number goes through format.ts, so null reads "n/a".
import type { Schemas } from "@swing-scan/api-client";
import { ChevronDown, TriangleAlert } from "lucide-react";
import { Fragment, useId, useState, type ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatInt, formatNumber, formatPct, NOT_AVAILABLE } from "@/lib/format";
import { cn } from "@/lib/utils";

import {
  EDGE_COLUMNS,
  hasStop,
  METRIC_COLUMNS,
  type EdgeMetrics,
  type MetricColumn,
  type TradeMetrics,
  type ValueKind,
} from "./columns";

type TradeLabResult = Schemas["TradeLabResult"];
type Segment = "is" | "oos";
type Value = number | null | undefined;

const SEGMENTS: { key: Segment; label: string }[] = [
  { key: "is", label: "IS" },
  { key: "oos", label: "OOS" },
];

/** -1, 0 or 1 once `v` is rounded to `decimals`; 0 for a missing value. */
function signOf(v: Value, decimals: number): number {
  if (typeof v !== "number" || !Number.isFinite(v)) return 0;
  return Number(Math.abs(v).toFixed(decimals)) === 0 ? 0 : Math.sign(v);
}

/** Signed values get the gain or loss colour; the sign always carries the meaning too. */
function signed(text: string, sign: number): ReactNode {
  const tone = sign === 0 ? "text-foreground" : sign > 0 ? "text-positive" : "text-negative";
  return <span className={tone}>{text}</span>;
}

/** `0.42` → `+0.42R` or `+0.42 pts`; formatNumber already writes the minus. */
function signedNumber(v: Value, suffix: string): ReactNode {
  const text = formatNumber(v);
  if (text === NOT_AVAILABLE) return text;
  const sign = signOf(v, 2);
  return signed(`${sign > 0 ? "+" : ""}${text}${suffix}`, sign);
}

export function formatValue(kind: ValueKind, v: Value): ReactNode {
  switch (kind) {
    case "int":
      return formatInt(v);
    case "rate":
      return formatPct(v).replace(/^\+/, "");
    case "signed_pct":
      return signed(formatPct(v), signOf(v, 2));
    case "per_bar":
      return signed(formatPct(v, { decimals: 3 }), signOf(v, 3));
    case "r":
      return signedNumber(v, "R");
    case "pts":
      return signedNumber(v, " pts");
    case "number":
      return formatNumber(v);
    case "bars":
      return formatNumber(v, { decimals: 1 });
  }
}

/**
 * A term keeps its label and gains one plain line (doc 01 section 6.8): the line is the `abbr`
 * tooltip and, for anyone not hovering, a screen reader only sentence. No `aria-label` here: the
 * acceptance suite indexes the IS and OOS leaf headers by that attribute.
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

/** The footnote mark on an R cell of a config without a stop (X-4). */
function NoStopMark() {
  return (
    <sup aria-hidden="true" className="ml-0.5 text-muted-foreground">
      *
    </sup>
  );
}

function ValueCell({
  kind,
  value,
  noStop,
  best = false,
  segment,
  metric,
}: {
  kind: ValueKind;
  value: Value;
  noStop: boolean;
  best?: boolean;
  segment: Segment;
  metric: string;
}) {
  return (
    <TableCell
      data-segment={segment}
      data-metric={metric}
      data-best-is={best || undefined}
      className={cn("text-right", best && "bg-accent font-semibold")}
    >
      {formatValue(kind, value)}
      {kind === "r" && noStop ? <NoStopMark /> : null}
      {best ? (
        <>
          {" "}
          <span className="block text-xs font-medium text-foreground">Best IS</span>
        </>
      ) : null}
    </TableCell>
  );
}

/** The metric cells of one side (strategy or random) for one row, IS before OOS per metric. */
function metricCells(
  metrics: { is: TradeMetrics; oos: TradeMetrics },
  noStop: boolean,
  bestFor: (column: MetricColumn) => boolean,
) {
  return METRIC_COLUMNS.flatMap((column) =>
    SEGMENTS.map(({ key }) => (
      <ValueCell
        key={`${column.key}-${key}`}
        kind={column.kind}
        value={metrics[key][column.key]}
        noStop={noStop}
        best={key === "is" && bestFor(column)}
        segment={key}
        metric={column.key}
      />
    )),
  );
}

function edgeCells(edge: { is: EdgeMetrics; oos: EdgeMetrics }, noStop: boolean) {
  return EDGE_COLUMNS.flatMap((column) =>
    SEGMENTS.map(({ key }) => (
      <ValueCell
        key={`edge-${column.key}-${key}`}
        kind={column.kind}
        value={edge[key][column.key]}
        noStop={noStop}
        segment={key}
        metric={`edge_${column.key}`}
      />
    )),
  );
}

/** Random rows have no edge of their own: the edge is strategy minus them. */
function NoEdgeCell() {
  return (
    <TableCell colSpan={EDGE_COLUMNS.length * 2} className="text-muted-foreground">
      The edge is the strategy minus these
    </TableCell>
  );
}

const STICKY = "sticky left-0 z-10 min-w-44 max-w-56 bg-card whitespace-normal";

export function ExitLabTable({ result }: { result: TradeLabResult }) {
  const id = useId();
  const [open, setOpen] = useState<ReadonlySet<number>>(() => new Set());
  const configs = result.assumptions.configs;
  const horizon = new Map(
    result.warnings
      .filter((w) => w.code === "horizon_exits_over_10pct" && w.config_index !== null)
      .map((w) => [w.config_index, w.message] as const),
  );
  const toggle = (i: number) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  const baseline = result.rows[0];
  const baselineNoStop = !hasStop(configs[0]);

  return (
    // A focusable scroll region, so the wide table scrolls by keyboard at 375 px; the config
    // column stays put while you scroll.
    <div
      role="region"
      aria-label="Exit lab, in sample beside out of sample"
      tabIndex={0}
      className="min-w-0 overflow-auto rounded-lg border"
    >
      <Table className="tabular-nums">
        <TableHeader>
          <TableRow>
            <TableHead scope="col" rowSpan={3} className={cn(STICKY, "z-20 bg-muted align-bottom")}>
              Exit config
            </TableHead>
            <TableHead scope="colgroup" colSpan={METRIC_COLUMNS.length * 2} className="text-center">
              Per trade metrics, in sample (IS) and out of sample (OOS)
            </TableHead>
            <TableHead
              scope="colgroup"
              colSpan={EDGE_COLUMNS.length * 2}
              className="border-l text-center"
            >
              <Explained
                label="Edge vs random"
                hint="This config's value minus the same config run on random entries."
              />
            </TableHead>
          </TableRow>
          <TableRow>
            {METRIC_COLUMNS.map((column) => (
              <TableHead key={column.key} scope="colgroup" colSpan={2} className="text-center">
                <Explained label={column.label} hint={column.hint} />
              </TableHead>
            ))}
            {EDGE_COLUMNS.map((column, i) => (
              <TableHead
                key={column.key}
                scope="colgroup"
                colSpan={2}
                className={cn("text-center", i === 0 && "border-l")}
              >
                <Explained label={column.label} hint={column.hint} />
              </TableHead>
            ))}
          </TableRow>
          <TableRow>
            {METRIC_COLUMNS.flatMap((column) =>
              SEGMENTS.map(({ key, label }) => (
                <TableHead
                  key={`${column.key}-${key}`}
                  scope="col"
                  aria-label={`${column.label} ${label}`}
                  className="text-right"
                >
                  {label}
                </TableHead>
              )),
            )}
            {EDGE_COLUMNS.flatMap((column, i) =>
              SEGMENTS.map(({ key, label }) => (
                <TableHead
                  key={`edge-${column.key}-${key}`}
                  scope="col"
                  aria-label={`Edge ${column.label} ${label}`}
                  className={cn("text-right", i === 0 && key === "is" && "border-l")}
                >
                  {label}
                </TableHead>
              )),
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {result.rows.map((row, i) => {
            const noStop = !hasStop(configs[i]);
            const warning = horizon.get(i);
            const expanded = open.has(i);
            const randomId = `${id}-random-${i}`;
            return (
              <Fragment key={i}>
                <TableRow>
                  <TableHead scope="row" className={cn(STICKY, "py-1.5 font-medium")}>
                    <div className="flex flex-col items-start gap-1">
                      <span>{row.name}</span>
                      {warning ? (
                        <>
                          <Badge variant="warning">
                            <TriangleAlert aria-hidden="true" />
                            Horizon over 10%
                          </Badge>
                          <span className="text-xs font-normal">{warning}</span>
                        </>
                      ) : null}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-ml-2 h-7 px-2 text-xs font-normal"
                        aria-label={`Random entries for ${row.name}`}
                        aria-expanded={expanded}
                        aria-controls={expanded ? randomId : undefined}
                        onClick={() => toggle(i)}
                      >
                        <ChevronDown
                          aria-hidden="true"
                          className={cn("transition-transform", expanded && "rotate-180")}
                        />
                        Random entries
                      </Button>
                    </div>
                  </TableHead>
                  {metricCells(row.strategy, noStop, (column) => {
                    if (!column.ranked) return false;
                    return result.best_is[column.key as keyof typeof result.best_is] === i;
                  })}
                  {edgeCells(row.edge, noStop)}
                </TableRow>
                {expanded ? (
                  <TableRow id={randomId} className="bg-muted/40">
                    <TableHead scope="row" className={cn(STICKY, "bg-muted font-normal")}>
                      Random entries, {row.name}
                    </TableHead>
                    {metricCells(row.random, noStop, () => false)}
                    <NoEdgeCell />
                  </TableRow>
                ) : null}
              </Fragment>
            );
          })}
          {baseline ? (
            <TableRow className="bg-muted/40">
              <TableHead scope="row" className={cn(STICKY, "bg-muted font-medium")}>
                <span className="block">Random entries</span>
                <span className="block text-xs font-normal text-muted-foreground">
                  Through the exits of {baseline.name}
                </span>
              </TableHead>
              {metricCells(baseline.random, baselineNoStop, () => false)}
              <NoEdgeCell />
            </TableRow>
          ) : null}
        </TableBody>
      </Table>
    </div>
  );
}
