"use client";

// The newer data notice (spec 0013 AC-4): it says the dataset moved on and leaves the results
// you are reading exactly as they are. A poll may change a notice; it may never change a number.
//
// Built from `Alert` directly rather than from `Banner`: `Banner`'s three variants are static
// page content with no live role, bar `danger`, which is `role="alert"` and reserved for errors.
// This notice appears while you are reading and is not an error, so it needs `role="status"`,
// which is none of those three (spec 0013, Feature design).
import { Database } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

import { useMeta } from "./shell/use-meta";

/** Fixed copy: it tells you to reload and promises nothing re-runs until you do (AC-4, AC-5). */
export const NEWER_DATA_TEXT =
  "Newer market data is available. Reload the page to work with it; these results stay as they are until you do.";

/** True only when the poll names a later session than the one the result was computed on. */
export function isNewerThan(dataEnd: string, latestEnd: string | null | undefined): boolean {
  // ISO dates compare correctly as strings. A null dataset is the absence of data, not a
  // change (AC-8), and an undefined one means no poll has landed yet.
  return latestEnd != null && latestEnd > dataEnd;
}

/** Presentational, so the `/ui` gallery can show both states without a request (AC-13). */
export function NewerDataNotice({ newer, className }: { newer: boolean; className?: string }) {
  if (!newer) return null;
  return (
    <Alert
      variant="info"
      role="status"
      data-slot="newer-data-notice"
      className={cn("min-w-0", className)}
    >
      <Database aria-hidden="true" />
      <AlertDescription>{NEWER_DATA_TEXT}</AlertDescription>
    </Alert>
  );
}

/**
 * The notice for a result on screen. `dataEnd` is read straight off that result, never off the
 * poll, so a tick landing between a request and its response cannot make this wrong (AC-2).
 */
export function ResultNewerDataNotice({
  dataEnd,
  className,
}: {
  dataEnd: string;
  className?: string;
}) {
  const meta = useMeta();
  return (
    <NewerDataNotice newer={isNewerThan(dataEnd, meta.data?.data?.end)} className={className} />
  );
}
