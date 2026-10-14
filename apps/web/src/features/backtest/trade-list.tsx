"use client";

// The report's trade list (spec 0007 AC-15): every `Trade` field, sortable, IS and OOS marked,
// and a "showing 2,000 of N" line when the server kept only the latest trades.
import type { Schemas } from "@swing-scan/api-client";

import { DataTable, DEFAULT_PAGE_SIZE, type DataTableColumn } from "@/components/data-table";
import { SignedValue } from "@/components/signed-value";
import { Badge } from "@/components/ui/badge";
import { formatDate, formatInt, formatPrice } from "@/lib/format";

export type Trade = Schemas["Trade"];

/** Exit reasons in plain words; the `Record` fails the typecheck when the contract adds one. */
export const EXIT_REASON_LABELS: Record<Trade["exit_reason"], string> = {
  stop_pct: "Stop (%)",
  stop_atr: "Stop (ATR)",
  trail_pct: "Trailing stop",
  target: "Target",
  time: "Time",
  ma: "Close below MA",
  delisted: "Delisted",
  horizon: "Horizon",
  end_of_test: "End of test",
};

const SEGMENT_LABELS = { is: "IS", oos: "OOS" } as const;

/**
 * A term keeps its header word and gains one plain line as the `abbr` tooltip (doc 01
 * section 6.8). The line is not repeated inside the header: these headers are sort buttons, and
 * the paragraph above the table already says the same thing for anyone not hovering.
 */
function explained(header: string, hint: string) {
  const Header = () => (
    <abbr title={hint} className="no-underline">
      {header}
    </abbr>
  );
  Header.displayName = `ExplainedHeader(${header})`;
  return Header;
}

const pct = (header: string, key: keyof Trade, hint?: string): DataTableColumn<Trade> => ({
  id: key,
  accessorKey: key,
  header: hint ? explained(header, hint) : header,
  meta: { numeric: true },
  cell: (info) => <SignedValue value={info.getValue<number | null>()} format="pct" />,
});

const r = (header: string, key: keyof Trade, hint?: string): DataTableColumn<Trade> => ({
  id: key,
  accessorKey: key,
  header: hint ? explained(header, hint) : header,
  meta: { numeric: true },
  cell: (info) => <SignedValue value={info.getValue<number | null>()} format="r" />,
});

const MAE = "MAE is the deepest a trade went against you before it closed.";
const MFE = "MFE is the furthest a trade went in your favour before it closed.";
const IN_R = "The same, counted in multiples of the risk you took (R = the distance to your stop).";

const price = (header: string, key: keyof Trade): DataTableColumn<Trade> => ({
  id: key,
  accessorKey: key,
  header,
  meta: { numeric: true },
  cell: (info) => formatPrice(info.getValue<number>()),
});

const date = (header: string, key: keyof Trade): DataTableColumn<Trade> => ({
  id: key,
  accessorKey: key,
  header,
  cell: (info) => <span className="whitespace-nowrap">{formatDate(info.getValue<string>())}</span>,
});

export const TRADE_COLUMNS: DataTableColumn<Trade>[] = [
  {
    id: "ticker",
    accessorKey: "ticker",
    header: "Ticker",
    cell: (info) => <span className="font-mono">{info.getValue<string>()}</span>,
  },
  {
    id: "segment",
    accessorKey: "segment",
    header: "Sample",
    cell: (info) => {
      const segment = info.getValue<Trade["segment"]>();
      return (
        <Badge variant={segment === "oos" ? "info" : "secondary"}>{SEGMENT_LABELS[segment]}</Badge>
      );
    },
  },
  date("Entry date", "entry_date"),
  price("Entry price", "entry_price"),
  date("Exit date", "exit_date"),
  price("Exit price", "exit_price"),
  {
    id: "exit_reason",
    accessorFn: (row) => EXIT_REASON_LABELS[row.exit_reason],
    header: "Exit reason",
  },
  pct("Return", "return_pct"),
  r(
    "R multiple",
    "r_multiple",
    "What the trade returned, counted in multiples of the risk you took (R = the distance to your stop).",
  ),
  {
    id: "bars_held",
    accessorKey: "bars_held",
    header: "Bars held",
    meta: { numeric: true },
    cell: (info) => formatInt(info.getValue<number>()),
  },
  pct("MAE", "mae_pct", MAE),
  r("MAE (R)", "mae_r", `${MAE} ${IN_R}`),
  pct("MFE", "mfe_pct", MFE),
  r("MFE (R)", "mfe_r", `${MFE} ${IN_R}`),
];

interface TradeListProps {
  trades: Trade[];
  /** Every trade the run made; larger than `trades.length` when truncated. */
  total: number;
  truncated: boolean;
  /** First out of sample session, `YYYY-MM-DD`. */
  oosStart: string;
  /** The table's accessible name; must be unique on the page. */
  caption?: string;
  /** Which trades a truncated list kept: the latest (portfolio) or an even spread (exit lab). */
  kept?: "latest" | "spread";
}

export function TradeList({
  trades,
  total,
  truncated,
  oosStart,
  caption = "Trade list, sortable by any column",
  kept = "latest",
}: TradeListProps) {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <p className="text-sm text-muted-foreground">
        {truncated
          ? `Showing ${formatInt(trades.length)} of ${formatInt(total)} trades, ${kept === "latest" ? "the latest" : "spread evenly"} by entry date; the metrics use every trade.`
          : `${formatInt(total)} trades.`}{" "}
        IS means in sample and OOS means out of sample, whose entries start on{" "}
        {formatDate(oosStart)}. {MAE} {MFE} The R columns count both in multiples of the risk you
        took, where R is the distance to your stop.
      </p>
      <DataTable
        columns={TRADE_COLUMNS}
        data={trades}
        getRowId={(trade) => `${trade.ticker}:${trade.entry_date}`}
        caption={caption}
        pageSize={DEFAULT_PAGE_SIZE}
      />
    </div>
  );
}
