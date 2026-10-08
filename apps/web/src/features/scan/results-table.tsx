"use client";

// Today's hits for the selected rule (spec 0005 AC-11). The operand columns come from the
// response's `columns`, aligned with each row's `operands`.
import type { ScanResponse } from "@swing-scan/api-client";
import { useMemo } from "react";

import { DataTable, type DataTableColumn } from "@/components/data-table";
import { EmptyState } from "@/components/empty-state";
import { SignedValue } from "@/components/signed-value";
import { Badge } from "@/components/ui/badge";
import { formatDate, formatNumber, formatPrice } from "@/lib/format";

export type ScanRow = ScanResponse["rows"][number];

function buildColumns(labels: string[]): DataTableColumn<ScanRow>[] {
  return [
    {
      id: "ticker",
      accessorKey: "ticker",
      header: "Ticker",
      cell: (info) => <span className="font-mono">{String(info.getValue())}</span>,
    },
    {
      id: "close",
      accessorKey: "close",
      header: "Close",
      meta: { numeric: true },
      cell: (info) => formatPrice(info.getValue() as number),
    },
    {
      id: "chg_pct",
      accessorKey: "chg_pct",
      header: "% change",
      meta: { numeric: true },
      cell: (info) => <SignedValue value={info.getValue() as number | null} format="pct" />,
    },
    {
      id: "vol_ratio",
      accessorKey: "vol_ratio",
      header: "Volume ratio",
      meta: { numeric: true },
      cell: (info) => formatNumber(info.getValue() as number | null),
    },
    ...labels.map((label, index): DataTableColumn<ScanRow> => ({
      id: `operand_${index}`,
      accessorFn: (row) => row.operands[index] ?? null,
      header: label,
      meta: { numeric: true },
      cell: (info) => formatNumber(info.getValue() as number | null),
    })),
    {
      id: "new_today",
      // 1 sorts above 0, so the first click puts today's new entries on top.
      accessorFn: (row) => (row.new_today ? 1 : 0),
      header: "New",
      meta: { numeric: true },
      cell: (info) => (info.row.original.new_today ? <Badge variant="info">New</Badge> : null),
    },
  ];
}

export function ResultsTable({ result, caption }: { result: ScanResponse; caption: string }) {
  const columns = useMemo(() => buildColumns(result.columns), [result.columns]);
  return (
    <DataTable
      columns={columns}
      data={result.rows}
      getRowId={(row) => row.ticker}
      caption={caption}
      empty={
        <EmptyState
          title={`No hits on ${formatDate(result.as_of)}`}
          hint="Try the other template."
        />
      }
    />
  );
}
