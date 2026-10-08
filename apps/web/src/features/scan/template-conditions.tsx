// The selected template's conditions as read only text (spec 0005 AC-9, AC-13). Every condition
// shows, the `close > 5` price filter included, so nothing about the scan is hidden (R-10).
import type { Rule } from "@swing-scan/api-client";

import { conditionText } from "./operands";

export function TemplateConditions({ rule }: { rule: Rule }) {
  return (
    <section aria-labelledby="scan-conditions" className="flex min-w-0 flex-col gap-2">
      <h2 id="scan-conditions" className="text-lg font-semibold">
        Conditions
      </h2>
      <p className="text-sm text-muted-foreground">A ticker is a hit when all of these hold.</p>
      <ol className="flex flex-col gap-1">
        {rule.conditions.map((condition, index) => (
          <li key={index} className="font-mono text-sm break-words">
            {conditionText(condition)}
          </li>
        ))}
      </ol>
    </section>
  );
}
