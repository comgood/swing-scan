// The MAE and MFE guide row under the exit lab (spec 0009 AC-17, X-5): winner MAE p75 and p90
// (a stop guide) and the median MFE (a target guide), from the baseline config's IS trades only.
import type { Schemas } from "@swing-scan/api-client";

import { useId } from "react";

import { SignedValue } from "@/components/signed-value";

export const GUIDE_SOURCE = "from the baseline config's IS trades only";

const GUIDES: { field: keyof Schemas["Guides"]; label: string }[] = [
  { field: "winner_mae_p75_pct", label: "Winner MAE p75" },
  { field: "winner_mae_p90_pct", label: "Winner MAE p90" },
  { field: "mfe_median_pct", label: "Median MFE" },
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
        {GUIDES.map(({ field, label }) => (
          <div key={field} className="flex min-w-0 justify-between gap-4 sm:justify-start">
            <dt className="text-muted-foreground">{label}</dt>
            <dd>
              <SignedValue value={guides[field]} format="pct" />
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
