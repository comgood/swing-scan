"use client";

// A sortable, optionally paged table on TanStack Table and the shadcn Table markup
// (spec 0003 AC-8). Sorting is ours, not the library's, because the rules are specific:
// numeric columns start descending, nulls sort last both ways, and ties keep input order.
import {
  tableFeatures,
  useTable,
  type CellData,
  type ColumnDef,
  type Row,
  type RowData,
  type TableFeatures,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { NOT_AVAILABLE } from "@/lib/format";
import { cn } from "@/lib/utils";

// The augmentation must repeat every type parameter, used or not.
/* eslint-disable @typescript-eslint/no-unused-vars */
declare module "@tanstack/react-table" {
  interface ColumnMeta<
    TFeatures extends TableFeatures,
    TData extends RowData,
    TValue extends CellData,
  > {
    /** Right aligned, tabular numbers, first click sorts descending. */
    numeric?: boolean;
    /** Paints the cell with the accent fill, e.g. the "best IS" marker. */
    highlight?: (row: TData) => boolean;
    /** Set false for a column that should not sort. */
    sortable?: boolean;
  }
}
/* eslint-enable @typescript-eslint/no-unused-vars */

const features = tableFeatures({});
type Features = typeof features;

/** Column definitions for DataTable rows of type T. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type DataTableColumn<T extends RowData> = ColumnDef<Features, T, any>;

/** Columns without their own `cell` show the raw value, or `n/a` when it is missing. */
const DEFAULT_COLUMN: Partial<DataTableColumn<RowData>> = {
  cell: (info) => {
    const value = info.getValue();
    return isMissing(value) ? NOT_AVAILABLE : String(value);
  },
};

/** A sensible page size for long tables (pass it as `pageSize`). */
export const DEFAULT_PAGE_SIZE = 50;

export interface SortState {
  id: string;
  desc: boolean;
}

export interface DataTableProps<T extends RowData> {
  columns: DataTableColumn<T>[];
  data: T[];
  getRowId: (row: T) => string;
  caption: string;
  captionVisible?: boolean;
  initialSort?: SortState;
  /** Unset means no pagination. */
  pageSize?: number;
  empty?: ReactNode;
  className?: string;
}

function isMissing(value: unknown): boolean {
  return (
    value === null || value === undefined || (typeof value === "number" && Number.isNaN(value))
  );
}

function compareValues(a: unknown, b: unknown, numeric: boolean): number {
  if (numeric) return Number(a) - Number(b);
  return String(a).localeCompare(String(b), "en-US", { sensitivity: "base" });
}

/** Stable sort: nulls last in both directions, ties keep input order. */
function sortRows<T extends RowData>(
  rows: Row<Features, T>[],
  sort: SortState | null,
  numeric: boolean,
): Row<Features, T>[] {
  if (!sort) return rows;
  const indexed = rows.map((row, index) => ({ row, index, value: row.getValue(sort.id) }));
  indexed.sort((a, b) => {
    const aMissing = isMissing(a.value);
    const bMissing = isMissing(b.value);
    if (aMissing || bMissing) {
      if (aMissing && bMissing) return a.index - b.index;
      return aMissing ? 1 : -1;
    }
    const order = compareValues(a.value, b.value, numeric);
    if (order !== 0) return sort.desc ? -order : order;
    return a.index - b.index;
  });
  return indexed.map(({ row }) => row);
}

/** none → first direction → reversed → none. Numeric columns start descending. */
function nextSort(current: SortState | null, id: string, numeric: boolean): SortState | null {
  if (current?.id !== id) return { id, desc: numeric };
  if (current.desc === numeric) return { id, desc: !numeric };
  return null;
}

export function DataTable<T extends RowData>({
  columns,
  data,
  getRowId,
  caption,
  captionVisible = false,
  initialSort,
  pageSize,
  empty,
  className,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<SortState | null>(initialSort ?? null);
  const [page, setPage] = useState(0);
  const [lastData, setLastData] = useState(data);

  // New data starts again on page 1.
  if (data !== lastData) {
    setLastData(data);
    setPage(0);
  }

  const table = useTable({
    features,
    columns,
    data,
    getRowId: (row: T) => getRowId(row),
    defaultColumn: DEFAULT_COLUMN as DataTableColumn<T>,
  });

  const sortedColumn = sort ? table.getColumn(sort.id) : undefined;
  const coreRows = table.getRowModel().rows;
  const sortedRows = useMemo(
    () => sortRows(coreRows, sort, Boolean(sortedColumn?.columnDef.meta?.numeric)),
    [coreRows, sort, sortedColumn],
  );

  const pageCount = pageSize ? Math.max(1, Math.ceil(sortedRows.length / pageSize)) : 1;
  const currentPage = Math.min(page, pageCount - 1);
  const visibleRows = pageSize
    ? sortedRows.slice(currentPage * pageSize, (currentPage + 1) * pageSize)
    : sortedRows;
  const columnCount = table.getAllLeafColumns().length;

  const onSort = (id: string, numeric: boolean) => {
    setSort((current) => nextSort(current, id, numeric));
    setPage(0);
  };

  return (
    <div className={cn("flex min-w-0 flex-col gap-2", className)}>
      <div
        role="region"
        aria-label={caption}
        tabIndex={0}
        className="max-h-[70vh] w-full min-w-0 overflow-auto rounded-lg border"
      >
        <Table>
          <TableCaption className={cn(captionVisible ? "caption-top mt-0 mb-2" : "sr-only")}>
            {caption}
          </TableCaption>
          <TableHeader>
            {table.getHeaderGroups().map((group) => (
              <TableRow key={group.id} className="hover:bg-transparent">
                {group.headers.map((header) => {
                  const meta = header.column.columnDef.meta;
                  const numeric = Boolean(meta?.numeric);
                  const sortable = !header.isPlaceholder && meta?.sortable !== false;
                  const direction =
                    sort?.id === header.column.id
                      ? sort.desc
                        ? "descending"
                        : "ascending"
                      : "none";
                  const Icon =
                    direction === "ascending"
                      ? ArrowUp
                      : direction === "descending"
                        ? ArrowDown
                        : ArrowUpDown;
                  const label = header.isPlaceholder ? null : <table.FlexRender header={header} />;
                  return (
                    <TableHead
                      key={header.id}
                      colSpan={header.colSpan}
                      aria-sort={sortable ? direction : undefined}
                      className={cn("sticky top-0 z-10 bg-muted", numeric && "text-right")}
                    >
                      {sortable ? (
                        <button
                          type="button"
                          onClick={() => onSort(header.column.id, numeric)}
                          className={cn(
                            "inline-flex min-h-8 items-center gap-1 rounded-sm font-medium",
                            numeric && "flex-row-reverse",
                            direction !== "none" && "text-primary",
                          )}
                        >
                          {label}
                          <Icon aria-hidden="true" className="size-3.5 shrink-0" />
                        </button>
                      ) : (
                        label
                      )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {visibleRows.length === 0 ? (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={columnCount} className="whitespace-normal">
                  {empty ?? "No rows."}
                </TableCell>
              </TableRow>
            ) : (
              visibleRows.map((row) => (
                <TableRow key={row.id}>
                  {row.getAllCells().map((cell) => {
                    const meta = cell.column.columnDef.meta;
                    return (
                      <TableCell
                        key={cell.id}
                        className={cn(
                          meta?.numeric && "text-right tabular-nums",
                          meta?.highlight?.(row.original) && "bg-accent",
                        )}
                      >
                        <table.FlexRender cell={cell} />
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
      {pageCount > 1 && (
        <nav aria-label={`${caption} pages`} className="flex items-center justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={currentPage === 0}
            onClick={() => setPage(currentPage - 1)}
          >
            Previous
          </Button>
          <span className="text-sm tabular-nums" aria-live="polite">
            Page {currentPage + 1} of {pageCount}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={currentPage === pageCount - 1}
            onClick={() => setPage(currentPage + 1)}
          >
            Next
          </Button>
        </nav>
      )}
    </div>
  );
}
