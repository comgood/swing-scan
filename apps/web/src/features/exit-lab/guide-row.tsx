// The MAE and MFE guide row under the exit lab (spec 0009 AC-17, X-5): winner MAE p75 and p90
// (a stop guide) and the median MFE (a target guide), from the baseline config's IS trades only.
import type { Schemas } from "@swing-scan/api-client";

import { useId } from "react";

import { SignedValue } from "@/components/signed-value";

export const GUIDE_SOURCE = "from the baseline config's IS trades only";

/** Each label keeps its term and gains one plain line (doc 01 section 6.8). */
const GUIDES: { field: keyof Schemas["Guides"]; label: string; hint: string }[] = [
  {
    field: "winner_mae_p75_pct",
    label: "Winner MAE p75",
    hint: "MAE is the deepest a trade went against you before it closed. Three winners in four went no deeper than this, so a stop inside it would have cut them short.",
  },
  {
    field: "winner_mae_p90_pct",
    label: "Winner MAE p90",
    hint: "The same, for nine winners in ten: the roomier of the two stop guides.",
  },
  {
    field: "mfe_median_pct",
    label: "Median MFE",
    hint: "MFE is the furthest a trade went in your favour before it closed. Half the trades reached at least this far, so it is a guide for a target.",
  },
];

export function GuideRow({ guides }: { guides: Schemas["Guides"] }) {
  const id = useId();
  return (
    <div
      role="group"
      aria-labelledby={id}
      className="flex min-w-0 flex-col gap-2 rounded-lg border p-3"
    >
      <p id={id} className="text-sm">
        <span className="font-medium">Stop and target guides</span>,{" "}
        <span className="text-muted-foreground">{GUIDE_SOURCE}</span>
      </p>
      <dl className="grid min-w-0 grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
        {GUIDES.map(({ field, label, hint }) => (
          <div key={field} className="flex min-w-0 justify-between gap-4 sm:justify-start">
            <dt className="text-muted-foreground">
              <abbr title={hint} className="no-underline">
                {label}
              </abbr>
              <span className="sr-only">. {hint}</span>
            </dt>
            <dd>
              <SignedValue value={guides[field]} format="pct" />
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
