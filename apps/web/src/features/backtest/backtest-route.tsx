"use client";

// Reads the URL once for the report. `useSearchParams` makes this part client rendered, so the
// page wraps it in Suspense for the static export.
import { useSearchParams } from "next/navigation";

import { BacktestReport } from "./backtest-report";

export function BacktestRoute() {
  const params = useSearchParams();
  return <BacktestReport initialParams={new URLSearchParams(params.toString())} />;
}
