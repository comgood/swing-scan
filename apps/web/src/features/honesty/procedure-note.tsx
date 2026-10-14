// The procedure note under the exit lab table (U-8, doc 02 §7.4). Feature 12 places it directly
// after the table. The copy is fixed by doc 01 U-8 and stays word for word; it spells IS and OOS
// out, because it is where the reader meets the pair. Honesty copy is body text, never fine
// print (design.md).
import { Info } from "lucide-react";

import { cn } from "@/lib/utils";

export const PROCEDURE_NOTE =
  "Trade mode isolates the exit effect: every config trades identical entries, so the exit is the only difference. Pick the exit on in sample (IS), read out of sample (OOS) once, then confirm with a single portfolio backtest.";

export function ProcedureNote({ className }: { className?: string }) {
  return (
    <p
      data-slot="procedure-note"
      className={cn("flex min-w-0 items-start gap-2 text-sm text-foreground", className)}
    >
      <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
      <span className="min-w-0 break-words">{PROCEDURE_NOTE}</span>
    </p>
  );
}
