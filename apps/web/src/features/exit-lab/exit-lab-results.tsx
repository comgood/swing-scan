"use client";

// The exit lab results in the order spec 0009 fixes (decision 9, spec 0004): the table, the
// procedure note directly under it, then the guide row, then the footnotes.
import type { Schemas } from "@swing-scan/api-client";

import { ProcedureNote } from "@/features/honesty";
import { formatInt } from "@/lib/format";

import { hasStop } from "./columns";
import { ExitLabTable } from "./exit-lab-table";
import { GuideRow } from "./guide-row";

type TradeLabResult = Schemas["TradeLabResult"];

/** The names of the configs without a stop, whose R cells read "n/a" (X-4). */
export function stoplessNames(result: TradeLabResult): string[] {
  return result.rows
    .filter((_, i) => !hasStop(result.assumptions.configs[i]))
    .map((row) => row.name);
}

export function ExitLabFootnotes({ result }: { result: TradeLabResult }) {
  const noStop = stoplessNames(result);
  const { entries, assumptions } = result;
  return (
    <ul className="flex min-w-0 flex-col gap-1 text-sm break-words">
      {noStop.length > 0 ? (
        <li>
          * R needs a stop. {new Intl.ListFormat("en-US").format(noStop.map((n) => `"${n}"`))}{" "}
          {noStop.length === 1 ? "has" : "have"} no stop, ATR stop or trailing stop, so{" "}
          {noStop.length === 1 ? "its" : "their"} R values read n/a; compare{" "}
          {noStop.length === 1 ? "it" : "them"} on expectancy in %.
        </li>
      ) : null}
      <li>
        Best IS marks the best in sample value of each metric. Out of sample, random and edge values
        are never ranked, so pick on IS and read OOS once.
      </li>
      <li>
        Every config trades the same {formatInt(entries.count)} entries (
        {formatInt(entries.is_count)} IS, {formatInt(entries.oos_count)} OOS), one unit notional
        trade each, and same ticker trades may overlap. A trade still open after{" "}
        {assumptions.horizon_bars === null
          ? "the horizon"
          : `${formatInt(assumptions.horizon_bars)} bars`}{" "}
        exits at that close.
      </li>
      <li>
        Edge vs random is the strategy value minus the random entries value under the same config
        and segment; the win rate edge is in percentage points. Random entries are drawn with seed{" "}
        {assumptions.seed === null ? "n/a" : String(assumptions.seed)} in the same market and go
        through the same exits.
      </li>
    </ul>
  );
}

export function ExitLabResults({ result }: { result: TradeLabResult }) {
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <ExitLabTable result={result} />
      <ProcedureNote />
      <GuideRow guides={result.guides_is} />
      <ExitLabFootnotes result={result} />
    </div>
  );
}
