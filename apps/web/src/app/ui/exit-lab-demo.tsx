"use client";

// The exit lab parts for the /ui gallery (spec 0009 FE task 4), on invented data: the table with
// its best IS marks, the n/a R cells and the horizon badge, then the procedure note, the guide
// row and the footnotes.
import { ExitLabResults } from "@/features/exit-lab";

import { SAMPLE_TRADE_LAB } from "./exit-lab-sample";

export function ExitLabDemo() {
  return <ExitLabResults result={SAMPLE_TRADE_LAB} />;
}
