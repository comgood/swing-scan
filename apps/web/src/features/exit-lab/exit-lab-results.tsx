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
          {noStop.length === 1 ? "has" : "have"} no stop, no ATR stop and no trailing stop, so R
          cannot be measured for {noStop.length === 1 ? "it" : "them"} and every R cell in{" "}
          {noStop.length === 1 ? "that row" : "those rows"} reads n/a. Compare{" "}
          {noStop.length === 1 ? "it" : "them"} on Expectancy (%) instead.
        </li>
      ) : null}
      <li>
        The &ldquo;Best IS&rdquo; mark sits on the best in sample (IS) value of each metric. Out of
        sample (OOS), random and edge values are never marked, because ranking them would invite you
        to pick on them. Choose a config on IS, then read its OOS numbers once.
      </li>
      <li>
        Every config trades the same {formatInt(entries.count)} entries (
        {formatInt(entries.is_count)} IS and {formatInt(entries.oos_count)} OOS), and each entry is
        one trade of one unit notional, so the exit is the only difference between the rows. Two
        trades on the same ticker may overlap. A trade still open after{" "}
        {assumptions.horizon_bars === null
          ? "the horizon"
          : `${formatInt(assumptions.horizon_bars)} bars`}{" "}
        is closed at that bar&rsquo;s close.
      </li>
      <li>
        Edge vs random is this config&rsquo;s value minus the value the same config scored on random
        entries, in the same segment. For Win rate (pts) that difference is in percentage points.
        The random entries are drawn with seed{" "}
        {assumptions.seed === null ? "n/a" : String(assumptions.seed)} from the same market and run
        through the same exits, so they differ from the strategy only in where they entered.
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
